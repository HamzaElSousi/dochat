"""Tests for chips field in POST /chat response — WIDGET-03."""
from unittest.mock import patch

import pytest


# ── Happy path: chips parse successfully ──────────────────────────────────────

def test_chat_response_includes_chips_field(client):
    """POST /chat with valid message → response JSON has chips field."""
    mock_answer = 'Here is the answer.\n{"chips": ["Q1?", "Q2?", "Q3?"]}'
    with patch('app.routes.chat.handle_chat') as mock_handle:
        mock_handle.return_value = {
            'answer': 'Here is the answer.',
            'session_id': 'test-session-1',
            'fallback': False,
            'sources': [],
            'chips': ['Q1?', 'Q2?', 'Q3?'],
        }
        resp = client.post(
            '/chat',
            json={'message': 'What services do you offer?'},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'chips' in data
    assert data['chips'] == ['Q1?', 'Q2?', 'Q3?']


def test_chat_chips_are_list_of_three(client):
    """chips field is always a list; exactly 3 items on success."""
    with patch('app.routes.chat.handle_chat') as mock_handle:
        mock_handle.return_value = {
            'answer': 'Answer text.',
            'session_id': 'test-session-2',
            'fallback': False,
            'sources': [],
            'chips': ['Follow-up A?', 'Follow-up B?', 'Follow-up C?'],
        }
        resp = client.post('/chat', json={'message': 'Tell me more.'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data['chips'], list)
    assert len(data['chips']) == 3


# ── Fallback / parse failure: chips is empty list ────────────────────────────

def test_chat_chips_empty_on_fallback(client):
    """When fallback=True, chips is [] (no LLM call was made)."""
    with patch('app.routes.chat.handle_chat') as mock_handle:
        mock_handle.return_value = {
            'answer': "I don't have information on that yet.",
            'session_id': 'test-session-3',
            'fallback': True,
            'sources': [],
            'chips': [],
        }
        resp = client.post('/chat', json={'message': 'Unknown topic.'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['chips'] == []
    assert data['fallback'] is True


def test_chat_chips_empty_on_parse_failure(client):
    """When LLM returns no parseable chip JSON, chips is [] (D-07 silent fail)."""
    with patch('app.routes.chat.handle_chat') as mock_handle:
        mock_handle.return_value = {
            'answer': 'Answer without chips.',
            'session_id': 'test-session-4',
            'fallback': False,
            'sources': [],
            'chips': [],
        }
        resp = client.post('/chat', json={'message': 'Some question.'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['chips'] == []


# ── Unit tests for _parse_chips() ────────────────────────────────────────────

def test_parse_chips_valid():
    """_parse_chips extracts 3 chips and strips JSON from answer text."""
    from app.services.query import _parse_chips
    raw = 'This is the answer.\n{"chips": ["Why A?", "What B?", "How C?"]}'
    answer, chips = _parse_chips(raw)
    assert chips == ['Why A?', 'What B?', 'How C?']
    assert 'chips' not in answer
    assert 'Why A?' not in answer
    assert answer.strip() == 'This is the answer.'


def test_parse_chips_no_json():
    """_parse_chips returns (raw, []) when no JSON block present."""
    from app.services.query import _parse_chips
    raw = 'Plain answer with no chips block.'
    answer, chips = _parse_chips(raw)
    assert chips == []
    assert answer == raw


def test_parse_chips_wrong_count():
    """_parse_chips returns [] when chips list has != 3 items."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["Only one"]}'
    _, chips = _parse_chips(raw)
    assert chips == []


def test_parse_chips_four_items():
    """_parse_chips returns [] when chips list has > 3 items."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["A?", "B?", "C?", "D?"]}'
    _, chips = _parse_chips(raw)
    assert chips == []


def test_parse_chips_empty_string_item():
    """_parse_chips returns [] when any chip is an empty string after strip."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["Q1?", "", "Q3?"]}'
    _, chips = _parse_chips(raw)
    assert chips == []


def test_parse_chips_malformed_json():
    """_parse_chips returns (raw, []) on malformed JSON."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["Q1?", "Q2?", broken]}'
    answer, chips = _parse_chips(raw)
    assert chips == []
    assert answer == raw
