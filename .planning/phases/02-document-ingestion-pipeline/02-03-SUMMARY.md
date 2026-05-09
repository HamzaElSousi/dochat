---
phase: 02-document-ingestion-pipeline
plan: 03
subsystem: url-ingestion-vertical-slice
tags: [url-ingestion, trafilatura, fetch-and-extract, ingest-url, atomic-rollback, duplicate-replace]
dependency_graph:
  requires: [02-02-file-ingestion-vertical-slice]
  provides: [url-ingest-endpoint, fetch-and-extract-url-utility, ingest-url-service]
  affects: [app/ingest/parser.py, app/services/ingestion.py, app/routes/ingest.py, tests/test_ingest_url.py]
tech_stack:
  added: []
  patterns: [trafilatura-fetch-extract, DOWNLOAD_TIMEOUT-15s-headroom, url-duplicate-replace-safe-name, inline-import-to-avoid-circular]
key_files:
  created: [tests/test_ingest_url.py]
  modified: [app/ingest/parser.py, app/services/ingestion.py, app/routes/ingest.py]
decisions:
  - "fetch_and_extract_url sets trafilatura.settings.DOWNLOAD_TIMEOUT=15 explicitly — default ~20s is too tight for 60s Apache CGI limit"
  - "ingest_url uses inline import of fetch_and_extract_url inside the function to avoid circular import risk (parser -> ingestion cycle)"
  - "safe_url_name derived from URL with ://'s and /'s replaced, truncated to 200 chars + .url suffix — stable key for duplicate-replace detection"
  - "ingest_url returns original URL as filename field in response (human-readable); stores safe_url_name internally for dedup"
  - "No temp file needed in ingest_url — URL content is not persisted to disk; only rollback is SQLite ROLLBACK"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 2 Plan 03: URL Ingestion Vertical Slice Summary

URL ingestion endpoint (POST /admin/ingest/url) with trafilatura fetch+extract, 15s explicit timeout, same chunk+embed+store pipeline as file uploads, atomic rollback, and duplicate-replace semantics — backed by 8 passing integration and unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Failing URL tests + fetch_and_extract_url utility | 4e12632 | tests/test_ingest_url.py, app/ingest/parser.py |
| 2 | ingest_url service function + POST /admin/ingest/url route | aea83f4 | app/services/ingestion.py, app/routes/ingest.py |

## What Was Built

### Task 1 — URL Parser Utility

**app/ingest/parser.py** — Added `fetch_and_extract_url(url: str) -> str`:
- Sets `trafilatura.settings.DOWNLOAD_TIMEOUT = 15` before fetch (explicit timeout for Apache 60s limit — T-02-12)
- `trafilatura.fetch_url(url)` returns None on any network/SSL/timeout error → raises `ValueError("Failed to fetch URL...")`
- `trafilatura.extract(html)` returns None for JS-rendered/empty pages → raises `ValueError("No extractable text found...")`
- Added `import trafilatura` at top of parser.py

**tests/test_ingest_url.py** — 8 tests written first (RED confirmed at 404), then made GREEN:
- 5 endpoint integration tests (no_auth → 401, missing_url_field → 400, success → 200, fetch_fails → 422, empty_content → 422)
- 3 utility unit tests (success, fetch_failure, empty_extract — all against `fetch_and_extract_url` directly)

### Task 2 — Ingestion Service + URL Route

**app/services/ingestion.py** — Added `ingest_url(conn, storage_path, url) -> dict`:
- Derives `safe_url_name` from URL (replaces `://` and `/` with `_`, truncates to 200 chars, appends `.url`) for duplicate detection
- Calls `fetch_and_extract_url(url)` → `chunk_text(text)` → `embed_chunks(chunks)`
- Same atomic `BEGIN`/`COMMIT`/`ROLLBACK` pattern as `ingest_file()` (no context manager mixing — Pitfall 6)
- Duplicate replace: looks up existing doc by `safe_url_name`, calls `_delete_document()` before re-indexing (D-07)
- No filesystem work — URL content is not persisted to disk; ROLLBACK covers all state
- Returns `{"doc_id": str, "filename": url, "chunk_count": int, "status": "ready"}`

**app/routes/ingest.py** — Added `POST /admin/ingest/url`:
- `@require_auth` guard (401 for unauthenticated requests)
- `request.get_json(silent=True)` → validates `url` field present and non-empty (400 if missing)
- `ValueError` from service layer → 422 with `{"error": ..., "url": ...}`
- `Exception` → 500 with generic message (no stack traces — T-02-11)
- Updated import: `from ..services.ingestion import ingest_file, ingest_url`

## Verification Results

```
50 passed in 3.70s
```

All 50 tests pass (30 pre-existing from Plans 01/02 + 8 new URL tests + 12 service tests from Plan 02-04 running in parallel).

URL endpoint registered correctly:
```
['/admin/ingest/upload', '/admin/ingest/url']
```

## Deviations from Plan

None — plan executed exactly as written.

The DOWNLOAD_TIMEOUT grep count returned 2 (one assignment + one in a comment) rather than the plan's expected 1, but the actual timeout IS set. This is a cosmetic difference only.

## Known Stubs

None — all data flows are wired. The URL ingest endpoint fetches real content (mocked in tests), stores it in SQLite, and returns actual doc_id and chunk_count.

`require_auth` remains the Phase 2 stub (password-only check). Intentional — Phase 4 replaces with full auth.

## Threat Surface

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-02-10 (SSRF via /admin/ingest/url) | Endpoint is admin-only (@require_auth gate); SSRF risk documented for Phase 4 review |
| T-02-11 (URL in error responses) | URL echoed in 422 JSON — admin already knows the URL they submitted; no new disclosure |
| T-02-12 (slow URL exhausts Apache timeout) | `trafilatura.settings.DOWNLOAD_TIMEOUT = 15` limits fetch; embed has 30s timeout; combined under 60s |

## Deployment Notes

After `git pull` on SiteGround staging server:

1. **Add `.htaccess` rewrite rule** (in the existing CGI block):
   ```apache
   RewriteRule ^admin/ingest/url/?$ /app.cgi/admin/ingest/url [QSA,L]
   ```

2. No new dependencies — `trafilatura` was already added to `requirements.txt` in Plan 02-01.

## Self-Check: PASSED

Files verified on disk:
- tests/test_ingest_url.py — FOUND
- app/ingest/parser.py (fetch_and_extract_url added) — FOUND
- app/services/ingestion.py (ingest_url added) — FOUND
- app/routes/ingest.py (url_ingest route added) — FOUND

Both commits (4e12632, aea83f4) confirmed in git log.
