---
phase: 03-query-pipeline-rag-logic
plan: 02
subsystem: query-service
tags: [rag, llm, vector-search, sqlite-vec, session, openrouter, embeddings]
dependency_graph:
  requires: [03-01]
  provides: [handle_chat, query-service]
  affects: [03-03]
tech_stack:
  added: []
  patterns: [cosine distance KNN, LLM primary-then-fallback retry, INSERT OR REPLACE upsert, manual BEGIN/COMMIT/ROLLBACK, context-only system prompt]
key_files:
  created:
    - app/services/query.py
  modified: []
decisions:
  - "serialize_f32 imported from app.services.ingestion — not redefined (DRY principle, plan requirement)"
  - "context-restriction in system prompt is hardcoded — ASSISTANT_NAME and ASSISTANT_PERSONA are the only configurable parts (D-16 / QUERY-03)"
  - "_call_llm_with_retry catches requests.RequestException (not just Timeout + HTTPError) to handle edge cases like connection errors — superset is correct here"
  - "docstring comment in _save_session mentions 'with conn:' but no actual usage — grep returns 1 (docstring match only) which is acceptable"
  - "Session save failure in handle_chat is non-fatal — answer already computed, pass silently (D-14 graceful degradation)"
metrics:
  duration_minutes: 12
  completed_date: "2026-05-09"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 3 Plan 02: Query Service Summary

**One-liner:** Complete RAG query pipeline in `app/services/query.py` — embed, vector-search, similarity gate, session history, LLM with primary-fallback retry, and session persistence satisfying all five QUERY requirements.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create app/services/query.py with full handle_chat() pipeline | bdff1f9 | app/services/query.py |

## What Was Built

**`app/services/query.py`** — Single file containing `handle_chat()` and four private helpers:

- **`handle_chat(conn, message, session_id)`** — Public API. Orchestrates all 8 steps: embed → vector search → similarity gate → chunk retrieval → history load → LLM message construction → LLM call with retry → session persistence. Always returns `{"answer", "session_id", "fallback", "sources"}`. Never raises to caller.

- **`_call_llm(messages, model)`** — POSTs to OpenRouter `/chat/completions`. Raises `requests.HTTPError` or `Timeout` on failure. Caller handles retry.

- **`_call_llm_with_retry(messages)`** — Tries `PRIMARY_MODEL` (`google/gemma-3-27b-it:free`) first; on any `RequestException` retries with `FALLBACK_MODEL` (`qwen/qwen3-next-80b-a3b-instruct:free`). Returns `None` if both fail (QUERY-05).

- **`_load_session(conn, session_id)`** — Loads message history from sessions table; returns `[]` if session not found (new or expired).

- **`_save_session(conn, session_id, messages, created_at)`** — Upserts session using `INSERT ... ON CONFLICT(session_id) DO UPDATE`. Follows manual `BEGIN`/`COMMIT`/`ROLLBACK` pattern verbatim (no `with conn:`).

- **`_vector_search(conn, query_vec)`** — Executes sqlite-vec KNN query using `WHERE embedding MATCH ? AND k = ?` syntax. Returns `[(chunk_id, distance), ...]` ordered by cosine distance ASC.

**QUERY requirements satisfied:**

| Requirement | Implementation |
|-------------|----------------|
| QUERY-01 | embed_query() + _vector_search() with TOP_K=4 |
| QUERY-02 | distance_threshold = 1.0 - SIMILARITY_THRESHOLD (default 0.65); gate before LLM |
| QUERY-03 | System prompt hardcodes context restriction; only ASSISTANT_NAME/PERSONA configurable |
| QUERY-04 | History trimmed to last MAX_HISTORY_TURNS*2 = 20 messages before LLM call |
| QUERY-05 | _call_llm_with_retry iterates PRIMARY then FALLBACK; both fail → FALLBACK_MESSAGE |

## Verification Results

- `from app.services.query import handle_chat, _call_llm_with_retry, _save_session, _vector_search` — OK
- `grep -c "with conn:" app/services/query.py` — 1 (docstring comment only, no actual usage)
- `grep -n "serialize_f32"` — import on line 10 only, no redefinition
- `grep -n "google/gemma-3-27b-it"` — PRIMARY_MODEL on line 20
- `grep -n "qwen/qwen3-next-80b"` — FALLBACK_MODEL on line 21
- `pytest tests/ -x -q` — 50 passed, 0 failed

## Deviations from Plan

**1. [Rule 2 - Security] Broadened exception catch in _call_llm_with_retry**

- **Found during:** Task 1 implementation review
- **Issue:** Plan specified `(requests.exceptions.Timeout, requests.HTTPError)` but connection errors (DNS failure, refused connection) raise `requests.ConnectionError` which is a subclass of `requests.RequestException`. These would propagate uncaught to `handle_chat()` and potentially to the route.
- **Fix:** Changed to catch `requests.RequestException` (parent of all requests exceptions) so all network failures trigger the fallback model retry path consistently.
- **Files modified:** app/services/query.py (line 57)
- **Commit:** bdff1f9

## Known Stubs

None — `handle_chat()` is fully implemented. The `chat_bp` stub in `app/routes/chat.py` (created in Plan 01) is intentional and documented in Plan 01's SUMMARY. Plan 03 will replace it with the full route implementation.

## Threat Surface Scan

No new network endpoints introduced. `app/services/query.py` is a service layer module — it makes outbound API calls to OpenRouter but does not open any new inbound endpoints. The threat model in the PLAN.md covers all relevant surfaces:

- **T-03-02-01** (session_id spoofing): parameterized query in `_load_session` prevents SQL injection; unknown session_id creates new session harmlessly.
- **T-03-02-03** (DoS via LLM timeout): LLM_TIMEOUT=30s per model; total budget 60s within Apache CGI limit.
- **T-03-02-04** (ASSISTANT_PERSONA escalation): context restriction is hardcoded in system prompt — cannot be overridden via env var.

## Self-Check: PASSED

- `app/services/query.py` exists: FOUND
- `def handle_chat(` present: FOUND
- `def _call_llm_with_retry(` present: FOUND
- `def _save_session(` present: FOUND
- `def _vector_search(` present: FOUND
- `PRIMARY_MODEL = 'google/gemma-3-27b-it:free'` present: FOUND
- `FALLBACK_MODEL = 'qwen/qwen3-next-80b-a3b-instruct:free'` present: FOUND
- `from app.services.ingestion import serialize_f32` present (not a def): FOUND
- No actual `with conn:` code usage: CONFIRMED
- Commit bdff1f9 in git log: FOUND
- `pytest tests/ -x -q` — 50 passed: CONFIRMED
