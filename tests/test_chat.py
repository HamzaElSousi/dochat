"""Tests for the public chat endpoint (POST /chat).

Covers all QUERY requirements (01-05) and implementation decisions D-01 to D-16.
All external HTTP calls (embed_query, _call_llm) are mocked — tests run offline.
"""
import json
import struct
import uuid

import pytest
from unittest.mock import MagicMock


FAKE_EMBEDDING = [0.1] * 1536
FAKE_ANSWER = "This is a test answer from the LLM."


def _pack_f32(vec: list) -> bytes:
    """Pack float list into sqlite-vec binary format (little-endian float32)."""
    return struct.pack(f"{len(vec)}f", *vec)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_db(app):
    """Insert one document + one chunk + one vec_items row into the test DB.

    Returns dict with chunk_id, doc_id, filename for test assertions.
    Inherits DB isolation from conftest `app` fixture (scope=function, tmp_path).
    """
    conn = app.config['DB_CONN']
    doc_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    now = "2026-01-01T00:00:00+00:00"

    # Guard against any in-flight implicit transaction (matches established pattern)
    if conn.in_transaction:
        conn.execute('ROLLBACK')

    conn.execute('BEGIN')
    try:
        conn.execute(
            "INSERT INTO documents (id, filename, filetype, uploaded_at, status, chunk_count, filepath) "
            "VALUES (?, 'test.txt', 'txt', ?, 'ready', 1, NULL)",
            [doc_id, now],
        )
        conn.execute(
            "INSERT INTO chunks (id, doc_id, content, chunk_index) VALUES (?, ?, 'Test chunk content', 0)",
            [chunk_id, doc_id],
        )
        result = conn.execute(
            "INSERT INTO vec_items(embedding) VALUES (?)",
            [_pack_f32(FAKE_EMBEDDING)],
        )
        vec_rowid = result.lastrowid
        conn.execute(
            "INSERT INTO chunk_embeddings (chunk_id, vec_rowid) VALUES (?, ?)",
            [chunk_id, vec_rowid],
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    return {"chunk_id": chunk_id, "doc_id": doc_id, "filename": "test.txt"}


# ── Basic endpoint tests ──────────────────────────────────────────────────────

def test_chat_valid_message(client, seeded_db, mocker):
    """POST /chat with valid message → 200, all 4 response fields present (D-06)."""
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)

    response = client.post('/chat', json={'message': 'What is in the document?'})
    assert response.status_code == 200
    body = response.get_json()
    assert 'answer' in body
    assert 'session_id' in body
    assert 'fallback' in body
    assert 'sources' in body
    assert body['fallback'] is False
    assert body['answer'] == FAKE_ANSWER
    assert isinstance(body['session_id'], str)
    assert len(body['session_id']) == 36  # UUID4 format


def test_chat_missing_message(client):
    """POST /chat with no message field → 400 with error key (D-05)."""
    response = client.post('/chat', json={})
    assert response.status_code == 400
    body = response.get_json()
    assert 'error' in body


def test_chat_empty_message(client):
    """POST /chat with whitespace-only message → 400 (D-05)."""
    response = client.post('/chat', json={'message': '   '})
    assert response.status_code == 400
    body = response.get_json()
    assert 'error' in body


# ── Similarity gate test ──────────────────────────────────────────────────────

def test_chat_below_threshold(client, seeded_db, mocker):
    """Vector search returns distance > threshold → fallback=True, no LLM call (QUERY-02, D-09).

    Default SIMILARITY_THRESHOLD=0.35 → distance_threshold=0.65.
    A distance of 0.8 exceeds the threshold → fallback triggered.
    """
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mock_llm = mocker.patch('app.services.query._call_llm')
    # Return a distance above the cosine distance threshold (0.65)
    mocker.patch('app.services.query._vector_search', return_value=[('chunk-1', 0.8)])

    response = client.post('/chat', json={'message': 'Totally unrelated question'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['fallback'] is True
    mock_llm.assert_not_called()


# ── Session continuity tests ──────────────────────────────────────────────────

def test_chat_new_session_id_returned(client, seeded_db, mocker):
    """POST /chat without session_id → response contains a new UUID session_id (D-02)."""
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    response = client.post('/chat', json={'message': 'New session question'})
    assert response.status_code == 200
    body = response.get_json()
    assert 'session_id' in body
    sid = body['session_id']
    # UUID4 format: 8-4-4-4-12 hex chars separated by hyphens
    parts = sid.split('-')
    assert len(parts) == 5
    assert len(sid) == 36


def test_chat_multiturn_session(client, seeded_db, mocker):
    """Two turns with same session_id → second LLM call includes prior turn in messages (QUERY-04, D-01)."""
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mock_llm = mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    # First turn — no session_id provided
    r1 = client.post('/chat', json={'message': 'First question'})
    assert r1.status_code == 200
    session_id = r1.get_json()['session_id']
    assert session_id is not None

    # Second turn — use same session_id (multi-turn continuation)
    r2 = client.post('/chat', json={'message': 'Follow-up question', 'session_id': session_id})
    assert r2.status_code == 200
    # Same session_id echoed back
    assert r2.get_json()['session_id'] == session_id

    # _call_llm should have been called twice (once per turn)
    assert mock_llm.call_count == 2

    # The second _call_llm invocation's messages list should contain the prior user turn
    # _call_llm signature: _call_llm(messages: list[dict], model: str)
    second_call_messages = mock_llm.call_args_list[1][0][0]  # first positional arg
    message_roles = [m['role'] for m in second_call_messages]
    assert 'system' in message_roles
    message_contents = [m['content'] for m in second_call_messages]
    # Prior turn's user message should appear in the second call's message list
    assert any('First question' in c for c in message_contents)


def test_chat_history_trimming(client, seeded_db, mocker):
    """After 11 turns stored, 12th call sends at most last 10 turns to LLM (QUERY-04, MAX_HISTORY_TURNS=10)."""
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mock_llm = mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    # Build up 11 turns in the same session
    session_id = None
    for i in range(11):
        payload = {'message': f'Question number {i}'}
        if session_id:
            payload['session_id'] = session_id
        r = client.post('/chat', json=payload)
        assert r.status_code == 200
        session_id = r.get_json()['session_id']

    # 12th turn: LLM messages should include at most MAX_HISTORY_TURNS * 2 = 20 history messages
    last_call_messages = mock_llm.call_args_list[-1][0][0]
    # Exclude the system prompt; remaining messages = history + current user message
    non_system = [m for m in last_call_messages if m['role'] != 'system']
    # MAX_HISTORY_TURNS=10 → max 20 history messages + 1 current user message = 21 total
    assert len(non_system) <= 21


# ── LLM retry tests ───────────────────────────────────────────────────────────

def test_chat_primary_llm_429_uses_fallback(client, seeded_db, mocker):
    """Primary model returns 429 → fallback model used → answer returned (QUERY-05, D-13)."""
    import requests as req_lib
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    # First call raises 429 HTTPError; second call (fallback model) returns the answer
    http_429 = req_lib.HTTPError(response=MagicMock(status_code=429))
    mock_llm = mocker.patch(
        'app.services.query._call_llm',
        side_effect=[http_429, FAKE_ANSWER],
    )

    response = client.post('/chat', json={'message': 'Test retry behaviour'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['fallback'] is False
    assert body['answer'] == FAKE_ANSWER
    assert mock_llm.call_count == 2  # primary tried then fallback model tried


def test_chat_both_llms_fail_returns_fallback(client, seeded_db, mocker):
    """Both primary and fallback models fail → fallback=True, FALLBACK_MESSAGE returned (D-14)."""
    import requests as req_lib
    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    http_error = req_lib.HTTPError(response=MagicMock(status_code=500))
    mocker.patch(
        'app.services.query._call_llm',
        side_effect=[http_error, http_error],
    )

    response = client.post('/chat', json={'message': 'Test double LLM failure'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['fallback'] is True
    # answer must be the fallback message: non-empty string, no stack trace
    assert isinstance(body['answer'], str)
    assert len(body['answer']) > 0
    assert 'Traceback' not in body['answer']
    assert 'Exception' not in body['answer']


# ── CORS tests ────────────────────────────────────────────────────────────────

def test_cors_allowed_origin(client, seeded_db, monkeypatch, mocker):
    """POST /chat from allowed origin → Access-Control-Allow-Origin header returned (D-08)."""
    import app.routes.chat as chat_mod
    # Patch module-level list directly — avoids env var reload complexity
    monkeypatch.setattr(chat_mod, '_ALLOWED_ORIGINS', ['https://allowed.example.com'])

    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    response = client.post(
        '/chat',
        json={'message': 'Hello from allowed origin'},
        headers={'Origin': 'https://allowed.example.com'},
    )
    assert response.status_code == 200
    assert 'Access-Control-Allow-Origin' in response.headers
    assert response.headers['Access-Control-Allow-Origin'] == 'https://allowed.example.com'


def test_cors_unlisted_origin(client, seeded_db, monkeypatch, mocker):
    """POST /chat from unlisted origin → no Access-Control-Allow-Origin header (D-08)."""
    import app.routes.chat as chat_mod
    monkeypatch.setattr(chat_mod, '_ALLOWED_ORIGINS', ['https://allowed.example.com'])

    mocker.patch('app.services.query.embed_query', return_value=FAKE_EMBEDDING)
    mocker.patch('app.services.query._call_llm', return_value=FAKE_ANSWER)
    mocker.patch('app.services.query._vector_search',
                 return_value=[(seeded_db['chunk_id'], 0.2)])

    response = client.post(
        '/chat',
        json={'message': 'Hello from evil origin'},
        headers={'Origin': 'https://evil.example.com'},
    )
    assert response.status_code == 200
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_cors_preflight_options(client, monkeypatch):
    """OPTIONS /chat from allowed origin → 204 with CORS headers (D-08)."""
    import app.routes.chat as chat_mod
    monkeypatch.setattr(chat_mod, '_ALLOWED_ORIGINS', ['https://allowed.example.com'])

    response = client.options(
        '/chat',
        headers={
            'Origin': 'https://allowed.example.com',
            'Access-Control-Request-Method': 'POST',
        },
    )
    assert response.status_code == 204
    assert 'Access-Control-Allow-Origin' in response.headers
    assert response.headers['Access-Control-Allow-Origin'] == 'https://allowed.example.com'
