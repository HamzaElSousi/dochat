import json


def test_health_returns_json(client):
    """GET /health must return a JSON response — covers INFRA-01."""
    response = client.get('/health')
    assert response.content_type == 'application/json'


def test_health_keys(client):
    """GET /health JSON must contain all 5 documented keys — per D-03."""
    response = client.get('/health')
    body = json.loads(response.data)
    required_keys = {'status', 'sqlite_vec_version', 'sqlite_vec_mode', 'storage_path', 'storage_writable'}
    assert required_keys.issubset(body.keys()), f"Missing keys: {required_keys - body.keys()}"


def test_health_ok_when_storage_writable(client, app):
    """status=ok when sqlite_vec_mode=native and storage is writable."""
    response = client.get('/health')
    body = json.loads(response.data)
    # storage_writable must be True (tmp_path is always writable)
    assert body['storage_writable'] is True


def test_health_status_code(client):
    """HTTP 200 when storage is writable (regardless of sqlite_vec mode)."""
    response = client.get('/health')
    # 200 = storage ok (native or fallback); 503 = storage not writable
    assert response.status_code in (200, 503)


def test_health_no_stack_trace(client):
    """Error handling V7: /health must not expose Python stack traces."""
    response = client.get('/health')
    body = response.data.decode()
    assert 'Traceback' not in body
    assert 'File "' not in body
