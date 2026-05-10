"""Lead capture test suite — covers LEADS-01 through LEADS-04."""
import base64
import os
import pytest
from unittest.mock import patch


def auth_header(password='test-password'):
    creds = base64.b64encode(f'admin:{password}'.encode()).decode()
    return {'Authorization': f'Basic {creds}'}


# ── LEADS-04: DB storage ────────────────────────────────────────────────────

def test_leads_save_to_db(client):
    """POST /dochat/api/leads saves lead with name, email, phone, question."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=True):
        r = client.post('/dochat/api/leads', json={
            'name': 'Alice', 'email': 'alice@example.com',
            'phone': '555-1234', 'question': 'What is your pricing?'
        })
    assert r.status_code == 200
    d = r.get_json()
    assert d.get('saved') is True
    assert 'id' in d


def test_leads_db_row_has_phone(client, app):
    """Lead row in DB contains the phone value submitted in the form (D-04)."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=True):
        r = client.post('/dochat/api/leads', json={
            'name': 'Bob', 'email': 'bob@example.com',
            'phone': '999-888-7777', 'question': 'Do you offer trials?'
        })
    assert r.status_code == 200
    lead_id = r.get_json()['id']
    conn = app.config['DB_CONN']
    row = conn.execute(
        "SELECT name, email, phone, question FROM leads WHERE id = ?", [lead_id]
    ).fetchone()
    assert row is not None
    assert row[0] == 'Bob'
    assert row[1] == 'bob@example.com'
    assert row[2] == '999-888-7777'
    assert row[3] == 'Do you offer trials?'


def test_leads_save_without_phone(client):
    """Phone is optional — omitting it still returns 200 and saves lead."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=True):
        r = client.post('/dochat/api/leads', json={
            'name': 'Carol', 'email': 'carol@example.com', 'question': 'Help?'
        })
    assert r.status_code == 200
    assert r.get_json().get('saved') is True


def test_leads_missing_name_returns_400(client):
    """POST without name → 400."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=True):
        r = client.post('/dochat/api/leads', json={
            'email': 'x@example.com', 'question': 'q'
        })
    assert r.status_code == 400
    assert 'error' in r.get_json()


def test_leads_missing_email_returns_400(client):
    """POST without email → 400."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=True):
        r = client.post('/dochat/api/leads', json={
            'name': 'Dave', 'question': 'q'
        })
    assert r.status_code == 400
    assert 'error' in r.get_json()


def test_leads_empty_body_returns_400(client):
    """POST with empty JSON body → 400."""
    r = client.post('/dochat/api/leads', json={})
    assert r.status_code == 400


# ── LEADS-03: Email notification ────────────────────────────────────────────

def test_leads_email_sent_on_capture(client, monkeypatch):
    """POST /dochat/api/leads triggers send_lead_notification() (D-06)."""
    calls = []
    def fake_notify(name, email, phone, question, timestamp):
        calls.append({'name': name, 'email': email, 'phone': phone})
        return True

    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    # Patch the reference in admin_api (where it was imported into), not the source module
    with patch('app.routes.admin_api.send_lead_notification', side_effect=fake_notify):
        r = client.post('/dochat/api/leads', json={
            'name': 'Eve', 'email': 'eve@example.com',
            'phone': '111', 'question': 'How to start?'
        })
    assert r.status_code == 200
    assert len(calls) == 1
    assert calls[0]['name'] == 'Eve'
    assert calls[0]['phone'] == '111'


def test_leads_smtp_failure_nonfatal(client):
    """SMTP failure does not prevent 200 response or DB save (D-08)."""
    with patch('app.routes.admin_api.send_lead_notification', return_value=False):
        r = client.post('/dochat/api/leads', json={
            'name': 'Frank', 'email': 'frank@example.com',
            'phone': '', 'question': 'Emergency?'
        })
    assert r.status_code == 200
    assert r.get_json().get('saved') is True


def test_email_subject_truncated_to_60_chars(monkeypatch):
    """send_lead_notification subject is 'New DocChat Lead: ' + first 60 chars (D-07)."""
    import smtplib
    from unittest.mock import MagicMock

    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_USER', 'user@example.com')
    monkeypatch.setenv('SMTP_PASS', 'pass')
    monkeypatch.setenv('ADMIN_EMAIL', 'admin@example.com')

    captured = []
    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): captured.append(msg)

    with patch('smtplib.SMTP', FakeSMTP):
        from app.services.email import send_lead_notification
        long_q = 'X' * 80
        result = send_lead_notification('G', 'g@g.com', '', long_q, '2026-05-10T00:00:00Z')

    assert result is True
    assert len(captured) == 1
    subj = captured[0]['Subject']
    expected = 'New DocChat Lead: ' + 'X' * 60
    assert subj == expected, f'Subject mismatch: {subj!r}'


# ── LEADS-01: Widget trigger (settings endpoint) ─────────────────────────────

def test_settings_get_public_no_auth(client):
    """GET /dochat/api/settings requires no auth — returns 200 (D-12)."""
    r = client.get('/dochat/api/settings')
    assert r.status_code == 200
    d = r.get_json()
    assert 'book_call_url' in d


def test_settings_default_empty_string(client):
    """GET /dochat/api/settings returns empty string when no setting saved."""
    r = client.get('/dochat/api/settings')
    d = r.get_json()
    assert d['book_call_url'] == ''


def test_settings_save_and_fetch(client):
    """POST /dochat/admin/settings → GET /dochat/api/settings returns saved URL."""
    r = client.post('/dochat/admin/settings',
                    json={'book_call_url': 'https://calendly.com/test'},
                    headers=auth_header())
    assert r.status_code == 200
    assert r.get_json().get('saved') is True

    r2 = client.get('/dochat/api/settings')
    assert r2.get_json()['book_call_url'] == 'https://calendly.com/test'


# ── LEADS-02: Admin Settings UI routes ──────────────────────────────────────

def test_admin_settings_requires_auth(client):
    """GET /dochat/admin/settings without credentials → 401 (D-11)."""
    r = client.get('/dochat/admin/settings')
    assert r.status_code == 401


def test_admin_settings_page_renders(client):
    """GET /dochat/admin/settings with auth → 200 HTML response."""
    r = client.get('/dochat/admin/settings', headers=auth_header())
    assert r.status_code == 200
    assert b'book_call_url' in r.data or b'book-call-url' in r.data


def test_admin_settings_post_requires_auth(client):
    """POST /dochat/admin/settings without credentials → 401."""
    r = client.post('/dochat/admin/settings', json={'book_call_url': 'https://x.com'})
    assert r.status_code == 401


def test_leads_options_preflight(client):
    """OPTIONS /dochat/api/leads → 204 (CORS preflight)."""
    r = client.options('/dochat/api/leads',
                       headers={'Origin': 'https://example.com',
                                'Access-Control-Request-Method': 'POST'})
    assert r.status_code == 204
