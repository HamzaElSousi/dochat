import os
from flask import Blueprint, request, jsonify, current_app

from ..auth import require_auth
from ..services.ingestion import ingest_file, ingest_url

ingest_bp = Blueprint('ingest', __name__)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB — enforced before any processing (T-02-08)


@ingest_bp.route('/admin/ingest/upload', methods=['POST'])
@require_auth
def upload():
    """Accept multipart file upload, ingest it, return doc_id + chunk_count.

    Field name: 'file' (multipart/form-data).
    Returns JSON: {"doc_id": str, "filename": str, "chunk_count": int, "status": "ready"}
    Errors: 400 (no file), 413 (>10 MB), 422 (parse/embed failure), 500 (unexpected)
    """
    conn = current_app.config.get('DB_CONN')
    storage_path = current_app.config.get('STORAGE_PATH')

    file = request.files.get('file')
    if file is None:
        return jsonify({"error": "No file field in request"}), 400

    # Read filename for metadata only — NEVER use directly in file paths (path traversal risk T-02-04)
    filename = os.path.basename(file.filename or 'unknown')

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        return jsonify({
            "error": f"File exceeds 10 MB limit ({len(file_bytes) / (1024*1024):.1f} MB received)",
            "filename": filename,
        }), 413

    try:
        result = ingest_file(conn, storage_path, file_bytes, filename)
        return jsonify(result), 200
    except ValueError as e:
        # ValueError includes unsupported type (detect_file_type) and parse failures
        return jsonify({"error": str(e), "filename": filename}), 422
    except Exception:
        # Never expose stack traces to the client (T-02-06)
        return jsonify({"error": "Internal server error during ingestion", "filename": filename}), 500


@ingest_bp.route('/admin/ingest/url', methods=['POST'])
@require_auth
def url_ingest():
    """Accept JSON {"url": "..."}, crawl the URL, index content.

    Returns JSON: {"doc_id": str, "filename": str, "chunk_count": int, "status": "ready"}
    Errors: 400 (missing url field), 422 (fetch/parse failure), 500 (unexpected)
    """
    conn = current_app.config.get('DB_CONN')
    storage_path = current_app.config.get('STORAGE_PATH')

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({"error": "Missing required field: 'url'"}), 400

    try:
        result = ingest_url(conn, storage_path, url)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e), "url": url}), 422
    except Exception:
        return jsonify({"error": "Internal server error during URL ingestion", "url": url}), 500
