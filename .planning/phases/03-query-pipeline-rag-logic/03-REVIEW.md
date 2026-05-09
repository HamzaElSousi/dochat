---
phase: 03-query-pipeline-rag-logic
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .env.example
  - app/__init__.py
  - app/db.py
  - app/ingest/embedder.py
  - app/routes/chat.py
  - app/services/query.py
  - requirements.txt
  - scripts/archive_sessions.py
  - tests/test_chat.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

The Phase 03 query pipeline implementation (chat endpoint, session management, vector search, LLM retry, archival cron) is structurally sound. The layered fallback design and parameterized queries are correct. However, one blocker exists: non-HTTP exceptions from malformed LLM API responses bypass the graceful-degradation path and surface as 500 errors rather than FALLBACK_MESSAGE. Additionally, four warnings cover a test that does not actually exercise the code path it claims to test, a MySQL driver mismatch between the documentation and the runtime code, an unvalidated client-supplied `session_id`, and missing input length enforcement on the chat message.

---

## Critical Issues

### CR-01: Malformed LLM response bypasses graceful degradation, returns 500

**File:** `app/services/query.py:42` and `app/services/query.py:52`

**Issue:** `_call_llm` parses the response with a chained key access:

```python
return response.json()['choices'][0]['message']['content']
```

If OpenRouter returns HTTP 200 with a body that lacks `choices`, has an empty list, or has `content: null` (which can happen on content-filter refusals, streaming errors, or model overload), this raises `KeyError`, `IndexError`, or `TypeError`. These are **not** subclasses of `requests.RequestException`, so `_call_llm_with_retry`'s except clause does not catch them:

```python
except (requests.exceptions.Timeout, requests.HTTPError, requests.RequestException):
    continue   # KeyError / IndexError / TypeError fall through
```

The uncaught exception propagates out of `_call_llm_with_retry` (returning neither a string nor `None`), skips the `if answer is None` fallback at line 207, and continues unhandled until it reaches the bare `except Exception` in `chat.py:64`, which returns HTTP 500. The declared invariant — "Never raises to caller — all LLM/embed failures degrade to fallback message (D-14)" — is violated.

**Fix:** Broaden the except in `_call_llm_with_retry`, or guard the key access in `_call_llm`:

```python
# Option A — broaden exception catch in _call_llm_with_retry
except (requests.exceptions.Timeout, requests.HTTPError,
        requests.RequestException, KeyError, IndexError, TypeError, ValueError):
    continue

# Option B — safe access in _call_llm
choices = response.json().get('choices') or []
if not choices:
    raise ValueError(f"Empty choices in LLM response for model {model!r}")
content = choices[0].get('message', {}).get('content')
if content is None:
    raise ValueError(f"Null content in LLM response for model {model!r}")
return content
```

Option B is preferred because it surfaces a clear error message in logs and lets the retry logic handle the fallback model correctly.

---

## Warnings

### WR-01: test_chat_history_trimming never executes the trim branch

**File:** `tests/test_chat.py:177-199`

**Issue:** The test comment says "After 11 turns stored, 12th call sends at most last 10 turns." But the loop runs exactly 11 iterations (`range(11)`), so the _last_ call checked by `mock_llm.call_args_list[-1]` is the **11th turn**. At that point, the stored history has 20 messages (10 completed turns × 2). The trim guard is `if len(history) > max_messages` (strictly greater than 20), which is `20 > 20 = False`. The trim branch is never entered. The assertion `len(non_system) <= 21` passes vacuously — it would pass even if the trim code were deleted entirely.

**Fix:** Run 12 iterations so that on the 12th call the stored history (22 messages) exceeds `max_messages` and the trim branch fires. Then assert that `non_system` contains exactly 21 messages (not merely ≤ 21), confirming that trimming capped the history correctly:

```python
for i in range(12):   # was range(11)
    ...

last_call_messages = mock_llm.call_args_list[-1][0][0]
non_system = [m for m in last_call_messages if m['role'] != 'system']
assert len(non_system) == 21  # exactly MAX_HISTORY_TURNS*2 history + 1 current
```

### WR-02: Client-supplied `session_id` is accepted without format validation

**File:** `app/routes/chat.py:57` / `app/services/query.py:121-132`

**Issue:** The `session_id` field in the POST body is accepted as-is and passed directly to `_load_session` and `_save_session`. Any arbitrary string (including very long strings or strings that look like other users' UUIDs) is stored as a primary key in the sessions table. A client that guesses or enumerates a valid UUID for another session can read and append to that session's history, since there is no authentication check on `session_id`.

This is an intentional design trade-off (the endpoint is public and unauthenticated per D-04), but the absence of even basic format validation means:
1. Arbitrarily long strings are persisted unchecked (DoS via DB bloat).
2. The API surface implicitly relies on UUID unguessability for session isolation, but this is never enforced — a 1-character `session_id` would be silently accepted.

**Fix:** Validate that `session_id`, when provided, matches UUID4 format before passing to the service layer:

```python
import re
_UUID4_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

session_id = data.get('session_id') or None
if session_id is not None and not _UUID4_RE.match(session_id):
    session_id = None  # treat invalid format as new session
```

### WR-03: No maximum length enforced on incoming `message`

**File:** `app/routes/chat.py:50`

**Issue:** The message field is only checked for non-emptiness after stripping. There is no upper bound. A client can POST a multi-megabyte string as `message`, which is then:
- Sent verbatim to the embedding API (EMBED_TIMEOUT=30s; large payloads risk timeout and inflate API cost)
- Appended directly into the LLM system prompt alongside the retrieved context (can push the context over model token limits, causing API errors)
- Stored as-is in the sessions table for every turn

The embedding and LLM API errors that result from an oversized message are caught by the existing exception handlers, so the failure mode is a FALLBACK_MESSAGE response rather than a crash — but the unnecessary API call and storage cost remain.

**Fix:** Add a length cap before processing. A conservative limit for a RAG query is 2,000 characters:

```python
MAX_MESSAGE_LEN = 2000
message = (data.get('message') or '').strip()
if not message:
    return jsonify({'error': "Missing required field: 'message'"}), 400
if len(message) > MAX_MESSAGE_LEN:
    resp = jsonify({'error': f"Message exceeds maximum length of {MAX_MESSAGE_LEN} characters"})
    resp.headers.update(cors)
    return resp, 400
```

### WR-04: MySQL driver mismatch — URL scheme implies `mysql-connector-python` but `pymysql` is used

**File:** `scripts/archive_sessions.py:16,48,55,130` / `.env.example:9`

**Issue:** The `.env.example` example URL is `mysql+mysqlconnector://user:pass@host/dbname` and the `_parse_mysql_url` docstring says it parses into `pymysql.connect()` kwargs. The `mysql+mysqlconnector` dialect prefix is the SQLAlchemy identifier for `mysql-connector-python` (a different package), not PyMySQL. The `requirements.txt` lists only `PyMySQL>=1.1.0`. An operator who reads the `.env.example` comment may attempt to install `mysql-connector-python` (the wrong driver), or set a URL using a different prefix that the strip logic does not handle:

```python
plain = url.replace('mysql+mysqlconnector://', 'mysql://', 1)
# If URL is "mysql+pymysql://..." or bare "mysql://...", this replace is a no-op
# and urlparse still works — but the intent is obscured
```

**Fix:** Update `.env.example` to use the PyMySQL dialect prefix and update the docstring to match:

```
# .env.example
MYSQL_URL=mysql+pymysql://user:pass@host/dbname
```

```python
def _parse_mysql_url(url: str) -> dict:
    """Parse mysql+pymysql://user:pass@host/db into pymysql.connect() kwargs."""
    ...
    plain = url.replace('mysql+pymysql://', 'mysql://', 1)
```

---

## Info

### IN-01: `sources` list can contain duplicate entries for the same document

**File:** `app/services/query.py:181-184`

**Issue:** When multiple top-K chunks come from the same document (common for long documents), the `sources` list in the response will contain repeated `{'filename': ..., 'doc_id': ...}` entries. For example, if all 4 retrieved chunks are from `manual.pdf`, the client receives `sources` with 4 identical objects. The client must deduplicate before displaying attribution.

**Fix:** Deduplicate by `doc_id` while preserving retrieval order:

```python
seen_doc_ids: set[str] = set()
sources = []
for row in ordered_chunks:
    if row[2] not in seen_doc_ids:
        seen_doc_ids.add(row[2])
        sources.append({'filename': row[3], 'doc_id': row[2]})
```

### IN-02: Module-level env var reads in `query.py` are frozen at first import

**File:** `app/services/query.py:13-19`

**Issue:** `SIMILARITY_THRESHOLD`, `FALLBACK_MESSAGE`, `ASSISTANT_NAME`, and `ASSISTANT_PERSONA` are read from `os.environ` once at module import time. In the CGI/Passenger deployment model this is harmless (each request spawns a new process), but it makes the values invisible to tests that set these env vars after the module has been imported. The test suite currently mocks `_vector_search` and `_call_llm` directly rather than relying on these constants, so no tests are broken today. However, any future test that sets `SIMILARITY_THRESHOLD` via `monkeypatch.setenv` will see the cached default value instead, leading to confusing test failures.

**Fix:** Either read the values inside `handle_chat` (per-request) or document the limitation explicitly in a comment so future test authors know to patch the module attribute rather than the env var:

```python
# In tests, patch app.services.query.SIMILARITY_THRESHOLD directly:
# mocker.patch.object(query_module, 'SIMILARITY_THRESHOLD', 0.9)
```

---

_Reviewed: 2026-05-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
