import os
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app

from ..auth import require_auth
from ..services.ingestion import ingest_file, ingest_url, _delete_document
from ..routes.ingest import _validate_url
from ..services.email import send_lead_notification

admin_api_bp = Blueprint('admin_api', __name__)

# DEBUG: temporary endpoint to diagnose DB read issues
@admin_api_bp.route('/dochat/api/settings/debug')
def settings_debug():
    """Debug endpoint — return raw DB state."""
    conn = current_app.config.get('DB_CONN')
    if not conn:
        return jsonify({"error": "no DB_CONN"}), 500

    # Force a fresh read
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    row = conn.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({"rows": [{"k": r[0], "v": r[1]} for r in row]}), 200

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB (matches ingest.py T-02-08)

# CORS allowlist for public widget endpoints — same pattern as chat.py (D-01)
_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get('ALLOWED_ORIGINS', '').split(',')
    if o.strip()
]


def _cors_headers_leads(origin: str) -> dict:
    """CORS headers for public widget endpoints (/api/leads, /api/settings)."""
    if origin in _ALLOWED_ORIGINS:
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    return {}


@admin_api_bp.route('/dochat/admin/ingest/upload', methods=['POST'])
@require_auth
def admin_upload():
    """Accept multipart file upload, ingest it, return full doc metadata for JS row append.

    Field name: 'file' (multipart/form-data).
    Returns JSON: {doc_id, filename, type, upload_date, status, chunk_count}
    Errors: 400 (no file), 413 (>10 MB), 422 (parse/embed failure), 500 (unexpected)
    """
    conn = current_app.config.get('DB_CONN')
    storage_path = current_app.config.get('STORAGE_PATH')

    file = request.files.get('file')
    if file is None:
        return jsonify({"error": "No file field in request"}), 400

    # os.path.basename prevents path traversal — never use raw file.filename in paths
    filename = os.path.basename(file.filename or 'unknown')

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        return jsonify({
            "error": f"File exceeds 10 MB limit ({len(file_bytes) / (1024*1024):.1f} MB received)",
            "filename": filename,
        }), 413

    try:
        result = ingest_file(conn, storage_path, file_bytes, filename)
    except ValueError as e:
        return jsonify({"error": str(e), "filename": filename}), 422
    except Exception:
        return jsonify({"error": "Internal server error during ingestion", "filename": filename}), 500

    # ingest_file() returns {doc_id, filename, chunk_count, status} — missing type + upload_date.
    # Fetch from DB so JS appendDocRow() has all fields for the new table row.
    doc_row = conn.execute(
        "SELECT filetype, uploaded_at FROM documents WHERE id = ?",
        [result['doc_id']]
    ).fetchone()
    if doc_row:
        result['type'] = doc_row[0]
        result['upload_date'] = doc_row[1]
    else:
        result['type'] = ''
        result['upload_date'] = ''

    return jsonify(result), 200


@admin_api_bp.route('/dochat/admin/ingest/url', methods=['POST'])
@require_auth
def admin_url_ingest():
    """Accept JSON {"url": "..."}, crawl the URL, index content.

    Returns JSON: {doc_id, filename, type, upload_date, status, chunk_count}
    Errors: 400 (missing url), 422 (fetch/parse/SSRF failure), 500 (unexpected)
    """
    conn = current_app.config.get('DB_CONN')
    storage_path = current_app.config.get('STORAGE_PATH')

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({"error": "Missing required field: 'url'"}), 400

    try:
        _validate_url(url)
        result = ingest_url(conn, storage_path, url)
    except ValueError as e:
        return jsonify({"error": str(e), "url": url}), 422
    except Exception:
        return jsonify({"error": "Internal server error during URL ingestion", "url": url}), 500

    # Same pattern as admin_upload: fetch type + upload_date from DB
    doc_row = conn.execute(
        "SELECT filetype, uploaded_at FROM documents WHERE id = ?",
        [result['doc_id']]
    ).fetchone()
    if doc_row:
        result['type'] = doc_row[0]
        result['upload_date'] = doc_row[1]
    else:
        result['type'] = ''
        result['upload_date'] = ''

    return jsonify(result), 200


@admin_api_bp.route('/dochat/admin/docs/<doc_id>', methods=['DELETE'])
@require_auth
def admin_delete_doc(doc_id):
    """Delete a document, its file from disk, and all associated vectors.

    Returns 200 {"deleted": true, "doc_id": doc_id} on success.
    Returns 404 {"error": "Document not found"} if doc_id not in documents table.
    Returns 500 on unexpected error.

    Transaction pattern: manual BEGIN/COMMIT/ROLLBACK — never 'with conn:'.
    """
    conn = current_app.config.get('DB_CONN')

    # Fetch filepath BEFORE deletion — _delete_document() removes the documents row,
    # so re-fetching after is impossible. Same pattern as ingest_file() (Phase 2 State).
    row = conn.execute(
        "SELECT filepath FROM documents WHERE id = ?", [doc_id]
    ).fetchone()
    if row is None:
        return jsonify({"error": "Document not found"}), 404

    filepath = row[0]

    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        _delete_document(conn, doc_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        return jsonify({"error": "Internal server error during deletion"}), 500

    # Remove file from disk after successful DB commit (non-fatal if file already gone)
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass  # Orphaned file is acceptable — DB state is authoritative

    return jsonify({"deleted": True, "doc_id": doc_id}), 200


@admin_api_bp.route('/dochat/admin/settings', methods=['POST'])
@require_auth
def admin_settings_save():
    """Save settings to the settings table.

    POST body: JSON {"book_call_url": "https://..."} or form data.
    Returns: {"saved": true, "book_call_url": "..."}
    Protected by @require_auth (D-11).
    """
    conn = current_app.config.get('DB_CONN')

    # Accept both JSON and form submissions
    if request.is_json:
        data = request.get_json(silent=True) or {}
        book_call_url = data.get('book_call_url', '').strip()
    else:
        book_call_url = (request.form.get('book_call_url') or '').strip()

    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ['book_call_url', book_call_url]
        )
        conn.execute("COMMIT")
        # Force WAL checkpoint so other CGI processes see the write (Passenger/CGI snapshot issue)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        conn.execute("ROLLBACK")
        return jsonify({"error": "Failed to save settings"}), 500

    return jsonify({"saved": True, "book_call_url": book_call_url}), 200


@admin_api_bp.route('/dochat/api/leads', methods=['POST', 'OPTIONS'])
def public_leads():
    """Public lead capture endpoint — no auth (widget-facing).

    POST body: {"name": "...", "email": "...", "phone": "...", "question": "..."}
    Response: {"saved": true, "id": "<uuid>"}
    Saves lead to DB then sends SMTP email (D-06). Email failure non-fatal (D-08).
    CORS: same ALLOWED_ORIGINS allowlist as /chat (D-01).
    Input lengths bounded: name<=200, email<=254, phone<=30, question<=2000 (T-06-07).
    """
    origin = request.headers.get('Origin', '')
    cors = _cors_headers_leads(origin)

    if request.method == 'OPTIONS':
        return ('', 204, cors)

    conn = current_app.config.get('DB_CONN')
    data = request.get_json(silent=True) or {}

    name     = (data.get('name') or '').strip()[:200]
    email    = (data.get('email') or '').strip()[:254]
    phone    = (data.get('phone') or '').strip()[:30]
    question = (data.get('question') or '').strip()[:2000]

    # Re-check required fields after stripping (slice does not introduce empty from valid input)
    if not (data.get('name') or '').strip() or not (data.get('email') or '').strip():
        resp = jsonify({"error": "Missing required fields: name and email"})
        resp.headers.update(cors)
        return resp, 400

    lead_id   = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO leads (id, name, email, phone, question, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [lead_id, name, email, phone, question, timestamp]
        )
        conn.execute("COMMIT")
        # Force WAL checkpoint so other CGI processes see the write
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        conn.execute("ROLLBACK")
        resp = jsonify({"error": "Failed to save lead"})
        resp.headers.update(cors)
        return resp, 500

    # Send email notification — failure is non-fatal (D-08)
    send_lead_notification(name, email, phone, question, timestamp)

    resp = jsonify({"saved": True, "id": lead_id})
    resp.headers.update(cors)
    return resp, 200


@admin_api_bp.route('/dochat/api/settings', methods=['GET', 'OPTIONS'])
def public_settings():
    """Public settings endpoint — no auth (widget-facing).

    Returns: {"book_call_url": "..."} — empty string if not configured.
    Widget fetches this once on init to get the CTA URL (D-12).
    """
    origin = request.headers.get('Origin', '')
    cors = _cors_headers_leads(origin)

    if request.method == 'OPTIONS':
        return ('', 204, cors)

    conn = current_app.config.get('DB_CONN')
    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", ['book_call_url']
    ).fetchone()
    book_call_url = row[0] if row else ''

    resp = jsonify({"book_call_url": book_call_url})
    resp.headers.update(cors)
    return resp, 200
