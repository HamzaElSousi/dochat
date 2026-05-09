---
phase: 03-query-pipeline-rag-logic
plan: "05"
subsystem: testing
tags: [tests, chat, rag, cors, session, llm-retry]
dependency_graph:
  requires:
    - "03-02"  # query.py (handle_chat, _vector_search, _call_llm)
    - "03-03"  # chat.py (CORS logic, route)
  provides:
    - "tests/test_chat.py — full coverage of POST /chat endpoint"
  affects: []
tech_stack:
  added: []
  patterns:
    - "mocker.patch targeting app.services.query.* for offline LLM/embed mocking"
    - "seeded_db fixture: real sqlite-vec insert with manual BEGIN/COMMIT/ROLLBACK guard"
    - "monkeypatch.setattr(chat_mod, '_ALLOWED_ORIGINS', [...]) for CORS list patching"
key_files:
  created:
    - tests/test_chat.py
  modified: []
decisions:
  - "Mock _vector_search at service layer to avoid sqlite-vec KNN complexity in tests (plan guidance)"
  - "seeded_db inserts real rows into test DB for end-to-end fidelity on chunk content retrieval"
  - "Patch _ALLOWED_ORIGINS module attribute directly (not env var) to avoid reload complexity"
  - "Added conn.in_transaction guard in seeded_db fixture consistent with ingestion service pattern"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-09"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 3 Plan 05: Chat Endpoint Test Suite Summary

**One-liner:** 12-test suite covering POST /chat with mocked embed_query, _vector_search, and _call_llm for fully offline RAG endpoint verification.

## What Was Built

`tests/test_chat.py` — the complete test suite for the public chat endpoint, verifying all QUERY requirements (01-05) and implementation decisions D-01 to D-16.

**Test inventory (12 tests):**

| Test | Requirement | Decision |
|------|-------------|---------|
| `test_chat_valid_message` | QUERY-01, QUERY-03 | D-06 (response shape) |
| `test_chat_missing_message` | — | D-05 (request validation) |
| `test_chat_empty_message` | — | D-05 (whitespace strip) |
| `test_chat_below_threshold` | QUERY-02 | D-09, D-12 (similarity gate, fallback flag) |
| `test_chat_new_session_id_returned` | — | D-02 (UUID generation) |
| `test_chat_multiturn_session` | QUERY-04 | D-01 (session history in LLM call) |
| `test_chat_history_trimming` | QUERY-04 | MAX_HISTORY_TURNS=10 cap |
| `test_chat_primary_llm_429_uses_fallback` | QUERY-05 | D-13 (model retry) |
| `test_chat_both_llms_fail_returns_fallback` | QUERY-05 | D-14 (graceful degradation) |
| `test_cors_allowed_origin` | — | D-08 (CORS allowlist) |
| `test_cors_unlisted_origin` | — | D-08 (CORS blocked) |
| `test_cors_preflight_options` | — | D-08 (OPTIONS 204) |

**Key fixtures:**
- `seeded_db` (local): inserts one document + chunk + vec_items row into the test DB using manual BEGIN/COMMIT with `conn.in_transaction` guard; provides `chunk_id`, `doc_id`, `filename` for test assertions.

**Mock strategy:**
- `app.services.query.embed_query` → returns `[0.1] * 1536` (no OpenRouter HTTP call)
- `app.services.query._vector_search` → returns controlled `(chunk_id, distance)` pairs
- `app.services.query._call_llm` → returns `FAKE_ANSWER` or raises `HTTPError`
- `app.routes.chat._ALLOWED_ORIGINS` → patched via `monkeypatch.setattr` per CORS test

## Results

- `pytest tests/test_chat.py -v`: **12/12 PASSED**
- `pytest tests/ -v`: **62/62 PASSED** (50 existing + 12 new — zero regressions)
- `grep -c "def test_" tests/test_chat.py`: **12** (requirement: >= 10)
- `grep -c "seeded_db" tests/test_chat.py`: **17** (requirement: >= 5)

## Deviations from Plan

None — plan executed exactly as written.

The `seeded_db` fixture code in the plan was complete and correct. One minor hardening addition: the `conn.in_transaction` guard before `BEGIN` in `seeded_db`, which is the established pattern from `app/services/ingestion.py` and is mentioned as a guard in the plan's code comments (CR-04 pattern). This is aligned with the threat model mitigation T-03-05-01 (test DB isolation).

## Known Stubs

None. All tests exercise real code paths; no stubs in `tests/test_chat.py`.

## Threat Flags

None. `tests/test_chat.py` is a test-only file — it introduces no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- [x] `tests/test_chat.py` exists at expected path
- [x] Commit `b71c74a` exists in git log
- [x] 12 test functions present (`grep -c "def test_" tests/test_chat.py` = 12)
- [x] 17 `seeded_db` references (`grep -c "seeded_db" tests/test_chat.py` = 17)
- [x] Full suite 62/62 passing — no regressions
