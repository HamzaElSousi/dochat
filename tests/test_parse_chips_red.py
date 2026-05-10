"""TDD RED: Failing tests for _parse_chips() before implementation — Task 1, Phase 05-01."""
import pytest


def test_parse_chips_red_valid():
    """_parse_chips extracts 3 chips and strips JSON from answer text."""
    from app.services.query import _parse_chips
    raw = 'This is the answer.\n{"chips": ["Why A?", "What B?", "How C?"]}'
    answer, chips = _parse_chips(raw)
    assert chips == ['Why A?', 'What B?', 'How C?']
    assert answer.strip() == 'This is the answer.'


def test_parse_chips_red_no_json():
    """_parse_chips returns (raw, []) when no JSON block present."""
    from app.services.query import _parse_chips
    raw = 'Plain answer with no chips block.'
    answer, chips = _parse_chips(raw)
    assert chips == []
    assert answer == raw


def test_parse_chips_red_wrong_count():
    """_parse_chips returns [] when chips list has != 3 items."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["Only one"]}'
    _, chips = _parse_chips(raw)
    assert chips == []


def test_parse_chips_red_four_items():
    """_parse_chips returns [] when chips list has > 3 items."""
    from app.services.query import _parse_chips
    raw = 'Answer.\n{"chips": ["A?", "B?", "C?", "D?"]}'
    _, chips = _parse_chips(raw)
    assert chips == []
