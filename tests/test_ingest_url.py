import json
import base64
import pytest

VALID_AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:test-password').decode()}


# --- Endpoint integration tests ---

def test_url_no_auth(client):
    """POST /admin/ingest/url without auth -> 401."""
    response = client.post('/admin/ingest/url',
                           json={'url': 'https://example.com'},
                           content_type='application/json')
    assert response.status_code == 401


def test_url_missing_url_field(client):
    """POST JSON without 'url' key -> 400 with error."""
    response = client.post('/admin/ingest/url',
                           json={},
                           content_type='application/json',
                           headers=VALID_AUTH)
    assert response.status_code == 400
    body = json.loads(response.data)
    assert 'error' in body


def test_url_success(client, mocker):
    """Valid URL -> 200 with doc_id, chunk_count > 0, status=ready."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url',
                 return_value='<html><body>content</body></html>')
    mocker.patch('app.ingest.parser.trafilatura.extract',
                 return_value='This is the main article content. ' * 30)
    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.json.return_value = {
        'data': [{'embedding': [0.1] * 1536, 'index': 0}]
    }
    mock_post.return_value.raise_for_status = lambda: None

    response = client.post('/admin/ingest/url',
                           json={'url': 'https://example.com'},
                           content_type='application/json',
                           headers=VALID_AUTH)
    assert response.status_code == 200
    body = json.loads(response.data)
    assert 'doc_id' in body
    assert body['chunk_count'] > 0
    assert body['status'] == 'ready'


def test_url_fetch_fails(client, mocker):
    """trafilatura.fetch_url returns None -> 422 with error."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url', return_value=None)
    response = client.post('/admin/ingest/url',
                           json={'url': 'https://unreachable.example.com'},
                           content_type='application/json',
                           headers=VALID_AUTH)
    assert response.status_code == 422
    body = json.loads(response.data)
    assert 'error' in body
    assert 'Traceback' not in response.data.decode()


def test_url_empty_content(client, mocker):
    """trafilatura.extract returns None (JS-only page) -> 422 with error."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url',
                 return_value='<html><body></body></html>')
    mocker.patch('app.ingest.parser.trafilatura.extract', return_value=None)
    response = client.post('/admin/ingest/url',
                           json={'url': 'https://js-only.example.com'},
                           content_type='application/json',
                           headers=VALID_AUTH)
    assert response.status_code == 422
    body = json.loads(response.data)
    assert 'error' in body


# --- Unit tests for fetch_and_extract_url ---

def test_fetch_and_extract_url_success(mocker):
    """Happy path: fetch_url returns HTML, extract returns text -> text returned."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url',
                 return_value='<html><body>Article content here.</body></html>')
    mocker.patch('app.ingest.parser.trafilatura.extract',
                 return_value='Article content here.')
    from app.ingest.parser import fetch_and_extract_url
    result = fetch_and_extract_url('https://example.com')
    assert 'Article content' in result


def test_fetch_and_extract_url_fetch_failure(mocker):
    """fetch_url returns None -> ValueError raised."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url', return_value=None)
    from app.ingest.parser import fetch_and_extract_url
    with pytest.raises(ValueError, match='Failed to fetch URL'):
        fetch_and_extract_url('https://example.com')


def test_fetch_and_extract_url_empty_extract(mocker):
    """extract returns None -> ValueError raised."""
    mocker.patch('app.ingest.parser.trafilatura.fetch_url',
                 return_value='<html></html>')
    mocker.patch('app.ingest.parser.trafilatura.extract', return_value=None)
    from app.ingest.parser import fetch_and_extract_url
    with pytest.raises(ValueError, match='No extractable text'):
        fetch_and_extract_url('https://example.com')
