"""Tests for widget.js static file delivery — WIDGET-08."""


def test_widget_js_route_exists(client):
    """GET /dochat/widget.js returns 200."""
    resp = client.get('/dochat/widget.js')
    assert resp.status_code == 200


def test_widget_js_content_type(client):
    """GET /dochat/widget.js returns application/javascript content type."""
    resp = client.get('/dochat/widget.js')
    assert 'javascript' in resp.content_type


def test_widget_js_contains_shadow_dom(client):
    """widget.js response body contains Shadow DOM setup code."""
    resp = client.get('/dochat/widget.js')
    assert b'attachShadow' in resp.data


def test_widget_js_contains_dochat_session_key(client):
    """widget.js response body references the sessionStorage key."""
    resp = client.get('/dochat/widget.js')
    assert b'dochat_session_id' in resp.data


def test_widget_js_no_import_statements(client):
    """widget.js is self-contained — no ES module import or require statements."""
    resp = client.get('/dochat/widget.js')
    body = resp.data.decode('utf-8')
    import re
    # Look for bare 'import ' keyword (ES module) or 'require(' (CJS)
    # Allow the word 'import' in comments only — but simplest check:
    assert 'require(' not in body
    # ES module import at start of statement (not inside a string or comment):
    assert not re.search(r'(?m)^\s*import\s', body), \
        "widget.js must not contain ES module import statements"
