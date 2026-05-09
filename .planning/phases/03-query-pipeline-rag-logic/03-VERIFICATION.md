---
phase: 03-query-pipeline-rag-logic
verified: 2026-05-09T00:00:00Z
status: passed
score: 19/19 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 3: Query Pipeline & RAG Logic Verification Report

**Phase Goal:** Build the query pipeline and RAG logic — embed visitor queries, vector-search the indexed document store, gate on similarity, call the LLM with context, and return sourced answers via a public /chat HTTP endpoint. Session history persisted in SQLite; expired sessions archived to MySQL by a cron script.
**Verified:** 2026-05-09T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Step 0: Previous Verification

No previous VERIFICATION.md found. Proceeding with initial mode.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Visitor query is embedded via embed_query() | VERIFIED | `app/ingest/embedder.py` line 56-62: `def embed_query(text: str) -> list[float]: return embed_chunks([text])[0]` |
| 2 | Vector search against sqlite-vec top-4 chunks (QUERY-01) | VERIFIED | `app/services/query.py` lines 105-121: `_vector_search()` uses KNN syntax `WHERE embedding MATCH ? AND k = ?` with `TOP_K = 4` |
| 3 | Similarity gate blocks LLM call when distance > 0.65 (QUERY-02) | VERIFIED | `query.py` lines 163-170: `distance_threshold = 1.0 - SIMILARITY_THRESHOLD` (default 0.65); gate fires if `not hits or hits[0][1] > distance_threshold` |
| 4 | LLM system prompt restricts to indexed context only (QUERY-03) | VERIFIED | `query.py` lines 202-208: hardcoded "Answer ONLY using the context provided below… Do not use any outside knowledge." — not configurable |
| 5 | Session history trimmed to last 10 turns before LLM call (QUERY-04) | VERIFIED | `query.py` lines 197-199: `max_messages = MAX_HISTORY_TURNS * 2` (20); trimmed via `history[-max_messages:]` |
| 6 | Primary LLM 429/error triggers fallback model (QUERY-05) | VERIFIED | `query.py` lines 53-62: `_call_llm_with_retry()` iterates `(PRIMARY_MODEL, FALLBACK_MODEL)`; catches `requests.RequestException`; returns `None` if both fail |
| 7 | Public POST /chat endpoint returns answer/session_id/fallback/sources | VERIFIED | `app/routes/chat.py` lines 33-69: route defined, calls `handle_chat()`, returns JSON with all 4 fields |
| 8 | POST /chat validates message field and returns 400 on empty/missing | VERIFIED | `chat.py` lines 50-54: `message = (data.get('message') or '').strip(); if not message: return jsonify({'error': ...}), 400` |
| 9 | CORS: allowed origin gets Access-Control-Allow-Origin header (D-08) | VERIFIED | `chat.py` lines 18-30: `_cors_headers()` exact-match against `_ALLOWED_ORIGINS`; returns full CORS dict |
| 10 | CORS: unlisted origin gets no Access-Control-Allow-Origin header | VERIFIED | `_cors_headers()` returns `{}` for non-allowlisted origins; confirmed by passing test |
| 11 | OPTIONS preflight returns 204 with CORS headers | VERIFIED | `chat.py` line 44-45: `if request.method == 'OPTIONS': return ('', 204, cors)` |
| 12 | New session_id (UUID) generated when none provided | VERIFIED | `query.py` lines 138-140: `if is_new_session: session_id = str(uuid.uuid4())` |
| 13 | Session persisted to SQLite after every successful exchange | VERIFIED | `query.py` lines 224-233: `_save_session()` called after LLM answer; uses INSERT ... ON CONFLICT upsert; manual BEGIN/COMMIT/ROLLBACK |
| 14 | sessions table created on app startup via init_session_tables() | VERIFIED | `app/db.py` lines 85-100: `def init_session_tables(conn)` with 4-column DDL; called in `init_db()` line 118 |
| 15 | scripts/archive_sessions.py: expired sessions (24h) archived to MySQL then deleted from SQLite | VERIFIED | `scripts/archive_sessions.py` lines 85-91: `WHERE last_active < datetime('now', '-24 hours')`; lines 155-173: INSERT to MySQL then DELETE from SQLite; `continue` on MySQL failure (D-20) |
| 16 | On MySQL error, session retained in SQLite (D-20) | VERIFIED | `archive_sessions.py` lines 167-173: `except Exception: logger.error(...); skipped += 1; continue` — SQLite DELETE skipped |
| 17 | PyMySQL declared in requirements.txt | VERIFIED | `requirements.txt` line 12: `PyMySQL>=1.1.0` |
| 18 | .env.example documents all Phase 3 env vars | VERIFIED | `.env.example` contains ALLOWED_ORIGINS, FALLBACK_MESSAGE, SIMILARITY_THRESHOLD, ASSISTANT_NAME, ASSISTANT_PERSONA, MYSQL_URL, and .htaccess RewriteRule comment |
| 19 | Full test suite: 12 chat tests + 50 pre-existing = 62 all passing | VERIFIED | `pytest tests/ -v` output: 62 passed, 0 failed |

**Score:** 19/19 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/db.py` | init_session_tables() + call in init_db() | VERIFIED | Lines 85-100 (function), line 118 (call after init_document_tables) |
| `app/ingest/embedder.py` | embed_query() wrapper | VERIFIED | Lines 56-62; delegates to embed_chunks([text])[0] |
| `app/__init__.py` | chat_bp import + register_blueprint | VERIFIED | Lines 6 and 20 |
| `app/routes/chat.py` | Full POST /chat with CORS | VERIFIED | 70 lines; not a stub; contains def chat(), _cors_headers(), route decorator |
| `app/services/query.py` | handle_chat() + all helpers | VERIFIED | 241 lines; contains handle_chat, _call_llm, _call_llm_with_retry, _load_session, _save_session, _vector_search |
| `scripts/archive_sessions.py` | Standalone cron archival | VERIFIED | 195 lines; syntax valid; contains main(), all helper functions |
| `tests/test_chat.py` | 12-test suite | VERIFIED | 12 test functions covering all QUERY requirements |
| `requirements.txt` | PyMySQL dependency | VERIFIED | PyMySQL>=1.1.0 present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app/db.py init_db() | sessions table | init_session_tables(conn) | WIRED | Line 118: `init_session_tables(conn)` called after init_document_tables |
| app/ingest/embedder.py embed_query() | embed_chunks() | return embed_chunks([text])[0] | WIRED | Line 62: confirmed |
| app/__init__.py | chat_bp | from .routes.chat import chat_bp | WIRED | Line 6 import + line 20 register_blueprint |
| app/routes/chat.py chat() | handle_chat() | from ..services.query import handle_chat | WIRED | Line 4 import; line 60 call |
| app/services/query.py handle_chat() | embed_query() | from app.ingest.embedder import embed_query | WIRED | Line 9 import; line 145 call |
| handle_chat() | vec_items cosine search | conn.execute('SELECT ... FROM vec_items ...') | WIRED | Lines 112-119 in _vector_search(); KNN syntax confirmed |
| handle_chat() | OpenRouter /chat/completions | requests.post('https://openrouter.ai/api/v1/chat/completions', ...) | WIRED | Lines 33-40 in _call_llm() |
| handle_chat() | sessions table | _save_session() with manual BEGIN/COMMIT/ROLLBACK | WIRED | Lines 77-100 (_save_session); line 230 (call in handle_chat) |
| scripts/archive_sessions.py | app.db._open_db() | sys.path.insert + from app.db import _open_db | WIRED | Lines 28-30 |
| scripts/archive_sessions.py | MySQL dochat_conversations | pymysql.connect() parsed from MYSQL_URL | WIRED | Lines 157-166 in main(); _parse_mysql_url() validates URL |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| app/services/query.py handle_chat() | query_vec | embed_query(message) → OpenRouter API | Yes (mocked in tests; real in production) | FLOWING |
| handle_chat() | hits | _vector_search(conn, query_vec) → sqlite-vec KNN | Yes — real DB query against vec_items | FLOWING |
| handle_chat() | context_text | conn.execute(SELECT ... FROM chunks JOIN documents) | Yes — real DB query with chunk_ids from hits | FLOWING |
| handle_chat() | history | _load_session(conn, session_id) → sessions table | Yes — real SELECT against sessions table | FLOWING |
| handle_chat() | answer | _call_llm_with_retry(llm_messages) → OpenRouter LLM | Yes (mocked in tests; real in production) | FLOWING |
| archive_sessions.py | expired | _fetch_expired_sessions(conn) → sessions WHERE last_active < NOW()-24h | Yes — real TTL query | FLOWING |

No static/empty returns or hollow props found. All data paths use real queries or mocked equivalents in tests.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 12 chat endpoint tests pass | python3 -m pytest tests/test_chat.py -v | 12 passed in 1.66s | PASS |
| Full suite (62 tests) passes without regression | python3 -m pytest tests/ -v | 62 passed in 4.29s | PASS |
| archive_sessions.py syntax valid | python3 -c "import ast; ast.parse(open('scripts/archive_sessions.py').read())" | syntax OK | PASS |
| No actual `with conn:` usage in query.py | grep -n "with conn:" app/services/query.py | Line 83: docstring comment only ("never 'with conn:'") — no executable usage | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QUERY-01 | 03-02, 03-03, 03-05 | Embed + top-4 vector search | SATISFIED | _vector_search() TOP_K=4; confirmed by test_chat_valid_message and test_chat_below_threshold |
| QUERY-02 | 03-02, 03-03, 03-05 | Similarity gate ~0.35 cosine | SATISFIED | distance_threshold = 1.0 - 0.35 = 0.65; gate in handle_chat(); confirmed by test_chat_below_threshold |
| QUERY-03 | 03-02, 03-03, 03-05 | Context-only LLM system prompt | SATISFIED | Hardcoded "Answer ONLY using the context" text in system_prompt; not overridable; confirmed by test_chat_valid_message |
| QUERY-04 | 03-02, 03-03, 03-04, 03-05 | 10-turn session history + archival | SATISFIED | MAX_HISTORY_TURNS=10; _load_session/_save_session in query.py; archive_sessions.py for 24h TTL; confirmed by test_chat_multiturn_session and test_chat_history_trimming |
| QUERY-05 | 03-02, 03-03, 03-05 | Primary→fallback LLM retry | SATISFIED | _call_llm_with_retry() iterates PRIMARY_MODEL then FALLBACK_MODEL; confirmed by test_chat_primary_llm_429_uses_fallback and test_chat_both_llms_fail_returns_fallback |

No orphaned requirements: all QUERY-01 through QUERY-05 are claimed in plan frontmatter and verified in codebase.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| app/services/query.py | 83 | "with conn:" in docstring string | Info | Docstring only — no actual `with conn:` usage. The string warns against it. Not a bug. |

No other TODO/FIXME/placeholder/stub patterns found in Phase 3 files. The `with conn:` grep returns 1 because of the docstring comment on line 83; all actual transaction code uses manual BEGIN/COMMIT/ROLLBACK correctly.

---

## Human Verification Required

None. All must-haves are verified programmatically via code inspection and passing test suite.

The following items would be human-verified during deployment, but are not blockers for phase goal achievement:

1. **Actual OpenRouter API integration** — tests mock embed_query and _call_llm. Real API calls require valid OPENROUTER_API_KEY in production.
2. **MySQL cron archival end-to-end** — requires live MySQL instance; script exits cleanly with "No expired sessions" when DB is empty but cannot be fully exercised without MySQL.
3. **.htaccess deployment** — the RewriteRule is documented in .env.example as a comment (manual deployment step).

---

## Gaps Summary

No gaps found. All 19 must-haves verified. All 5 QUERY requirements (QUERY-01 through QUERY-05) satisfied with substantive implementation and passing tests.

---

_Verified: 2026-05-09T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
