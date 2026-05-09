"""Admin UI test suite — covers ADMIN-01 through ADMIN-06 requirements."""
import base64
import io
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


def auth_header(password='test-password'):
    """Return Authorization header dict for HTTP Basic Auth."""
    creds = base64.b64encode(f'admin:{password}'.encode()).decode()
    return {'Authorization': f'Basic {creds}'}


# ── ADMIN-01: Auth protection ──────────────────────────────────────────────

def test_admin_docs_requires_auth(client):
    """GET /dochat/admin/docs without credentials → 401."""
    resp = client.get('/dochat/admin/docs')
    assert resp.status_code == 401


def test_admin_leads_requires_auth(client):
    """GET /dochat/admin/leads without credentials → 401."""
    resp = client.get('/dochat/admin/leads')
    assert resp.status_code == 401


def test_admin_upload_requires_auth(client):
    """POST /dochat/admin/ingest/upload without credentials → 401."""
    resp = client.post('/dochat/admin/ingest/upload')
    assert resp.status_code == 401


def test_admin_delete_requires_auth(client):
    """DELETE /dochat/admin/docs/some-id without credentials → 401."""
    resp = client.delete('/dochat/admin/docs/some-id')
    assert resp.status_code == 401


def test_admin_root_redirects(client):
    """GET /dochat/admin with credentials → 302 redirect to /dochat/admin/docs."""
    resp = client.get('/dochat/admin', headers=auth_header())
    assert resp.status_code == 302
    assert '/dochat/admin/docs' in resp.headers.get('Location', '')


# ── ADMIN-02: File upload ──────────────────────────────────────────────────

def test_admin_upload_no_file(client):
    """POST upload with no 'file' field → 400 with error key."""
    resp = client.post('/dochat/admin/ingest/upload', headers=auth_header())
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data


def test_admin_upload_too_large(client):
    """POST upload with file > 10 MB → 413."""
    big_bytes = b'x' * (10 * 1024 * 1024 + 1)
    resp = client.post(
        '/dochat/admin/ingest/upload',
        headers=auth_header(),
        data={'file': (io.BytesIO(big_bytes), 'large.pdf')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 413


def test_admin_upload_success(client, app):
    """POST upload with valid PDF bytes → 200 JSON with all required fields.

    ADMIN-02 + ADMIN-04: ingest_file is mocked; we pre-insert the document row
    so the route's SELECT filetype/uploaded_at finds it.
    """
    doc_id = 'test-doc-id-123'
    mock_ingest_result = {
        'doc_id': doc_id,
        'filename': 'test.pdf',
        'chunk_count': 3,
        'status': 'ready',
    }

    # Pre-insert the document row before the mocked ingest call so the route's
    # subsequent SELECT finds the filetype and uploaded_at fields.
    with app.app_context():
        conn = app.config['DB_CONN']
        now_iso = datetime.now(timezone.utc).isoformat()
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        conn.execute(
            "INSERT OR REPLACE INTO documents "
            "(id, filename, filetype, uploaded_at, status, chunk_count, filepath) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [doc_id, 'test.pdf', 'pdf', now_iso, 'ready', 3, None]
        )
        conn.execute("COMMIT")

    with patch('app.routes.admin_api.ingest_file', return_value=mock_ingest_result):
        resp = client.post(
            '/dochat/admin/ingest/upload',
            headers=auth_header(),
            data={'file': (io.BytesIO(b'%PDF-1.4 fake pdf'), 'test.pdf')},
            content_type='multipart/form-data',
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['doc_id'] == doc_id
    assert data['filename'] == 'test.pdf'
    assert data['chunk_count'] == 3
    assert data['status'] == 'ready'
    assert 'type' in data
    assert 'upload_date' in data


# ── ADMIN-03: URL ingestion ────────────────────────────────────────────────

def test_admin_url_ingest_missing(client):
    """POST /dochat/admin/ingest/url with no url field → 400.

    ADMIN-03: missing required URL field returns 400 with error key.
    """
    resp = client.post(
        '/dochat/admin/ingest/url',
        headers={**auth_header(), 'Content-Type': 'application/json'},
        json={},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data


def test_admin_url_ingest_success(client, app):
    """POST /dochat/admin/ingest/url with valid URL → 200 JSON with doc_id.

    ADMIN-03: ingest_url is mocked; pre-insert row for the SELECT to find.
    """
    doc_id = str(uuid.uuid4())
    mock_ingest_result = {
        'doc_id': doc_id,
        'filename': 'example.com',
        'chunk_count': 2,
        'status': 'ready',
    }

    with app.app_context():
        conn = app.config['DB_CONN']
        now_iso = datetime.now(timezone.utc).isoformat()
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        conn.execute(
            "INSERT OR REPLACE INTO documents "
            "(id, filename, filetype, uploaded_at, status, chunk_count, filepath) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [doc_id, 'example.com', 'url', now_iso, 'ready', 2, None]
        )
        conn.execute("COMMIT")

    with patch('app.routes.admin_api.ingest_url', return_value=mock_ingest_result):
        resp = client.post(
            '/dochat/admin/ingest/url',
            headers={**auth_header(), 'Content-Type': 'application/json'},
            json={'url': 'https://example.com'},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['doc_id'] == doc_id
    assert 'type' in data
    assert 'upload_date' in data


# ── ADMIN-04: Docs page renders ────────────────────────────────────────────

def test_admin_docs_page_renders(client):
    """GET /dochat/admin/docs → 200 HTML containing drop zone and table.

    ADMIN-04: docs page includes required UI elements for file upload and listing.
    """
    resp = client.get('/dochat/admin/docs', headers=auth_header())
    assert resp.status_code == 200
    assert b'drop-zone' in resp.data
    assert b'doc-table-body' in resp.data
    assert 'Indexed Documents'.encode() in resp.data


# ── ADMIN-05: Delete ───────────────────────────────────────────────────────

def test_admin_delete_not_found(client):
    """DELETE /dochat/admin/docs/<nonexistent-id> → 404 with error key.

    ADMIN-05: delete on unknown doc_id returns 404.
    """
    resp = client.delete(
        '/dochat/admin/docs/nonexistent-doc-id',
        headers=auth_header(),
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert 'error' in data


def test_admin_delete_success(client, app):
    """DELETE /dochat/admin/docs/<existing-id> → 200 {deleted: True}.

    ADMIN-05: delete on known doc_id removes the row and returns 200.
    Inserts document row directly (no chunks/vectors) — _delete_document()
    handles empty chunk sets gracefully.
    """
    doc_id = str(uuid.uuid4())
    with app.app_context():
        conn = app.config['DB_CONN']
        now_iso = datetime.now(timezone.utc).isoformat()
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO documents "
            "(id, filename, filetype, uploaded_at, status, chunk_count, filepath) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [doc_id, 'delete-me.pdf', 'pdf', now_iso, 'ready', 1, None]
        )
        conn.execute("COMMIT")

    resp = client.delete(
        f'/dochat/admin/docs/{doc_id}',
        headers=auth_header(),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['deleted'] is True
    assert data['doc_id'] == doc_id

    # Verify the document row is gone from the DB
    with app.app_context():
        conn = app.config['DB_CONN']
        row = conn.execute(
            "SELECT id FROM documents WHERE id = ?", [doc_id]
        ).fetchone()
    assert row is None


# ── ADMIN-06: Leads page renders ───────────────────────────────────────────

def test_admin_leads_page_renders(client):
    """GET /dochat/admin/leads → 200 HTML containing leads table and empty state.

    ADMIN-06: leads page renders correctly even when leads table is empty.
    """
    resp = client.get('/dochat/admin/leads', headers=auth_header())
    assert resp.status_code == 200
    assert 'Captured Leads'.encode() in resp.data
    assert b'No leads captured yet' in resp.data
