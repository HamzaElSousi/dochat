---
phase: 04-admin-ui
plan: "03"
subsystem: api, admin
tags: [flask, sqlite, blueprint, admin, auth, ingestion, delete, upload, url-ingest]

# Dependency graph
requires:
  - phase: 04-admin-ui
    plan: "01"
    provides: admin_api_bp stub registered in app factory
  - phase: 04-admin-ui
    plan: "02"
    provides: static/admin.js XHR calls targeting these endpoints
  - phase: 02-document-ingestion-pipeline
    provides: ingest_file, ingest_url, _delete_document, require_auth
  - phase: 02-document-ingestion-pipeline
    provides: _validate_url (SSRF prevention, reused from ingest.py)
provides:
  - POST /dochat/admin/ingest/upload — multipart file upload, returns full doc metadata
  - POST /dochat/admin/ingest/url — JSON URL submission, returns full doc metadata
  - DELETE /dochat/admin/docs/<doc_id> — removes doc row, chunks, vectors, and file from disk
affects: [04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fetch type+upload_date from DB after ingest_file()/ingest_url() — ingest returns {doc_id, filename, chunk_count, status} only"
    - "Fetch filepath BEFORE _delete_document() — documents row is deleted by _delete_document(), re-fetch impossible after"
    - "File removal after COMMIT: DB is authoritative; disk cleanup is best-effort (OSError silenced)"
    - "conn.in_transaction guard before BEGIN — prevents OperationalError on nested transaction"
    - "Reuse _validate_url() from ingest.py — no duplication of SSRF prevention logic"

key-files:
  created: []
  modified:
    - app/routes/admin_api.py

key-decisions:
  - "Docstring occurrences of 'Document not found' and 'with conn:' do not affect behavior — actual code has zero 'with conn:' usage and one jsonify return with 404"
  - "type and upload_date fetched from DB after ingest completes — ingest_file/ingest_url return shape does not include these fields"

# Metrics
duration: 10min
completed: 2026-05-09
---

# Phase 4 Plan 03: Admin API Endpoints Summary

**Three admin API route handlers implemented in app/routes/admin_api.py — POST upload, POST url-ingest, DELETE doc — completing the browser-to-backend wiring for admin.js**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-09
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced `app/routes/admin_api.py` stub with full implementation of three route handlers
- `admin_upload()`: accepts multipart `file` field, enforces 10 MB limit, calls `ingest_file()`, fetches `filetype`+`uploaded_at` from DB, returns complete JSON for `appendDocRow()`
- `admin_url_ingest()`: accepts JSON `{"url": "..."}`, validates with `_validate_url()` (SSRF prevention), calls `ingest_url()`, same DB fetch + response shape
- `admin_delete_doc()`: fetches `filepath` before deletion, manual `BEGIN`/`COMMIT`/`ROLLBACK` transaction, calls `_delete_document()`, removes file from disk after commit (best-effort)
- All three protected with `@require_auth`; DELETE returns 404 on unknown doc_id
- All 62 existing tests pass with no regressions

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement admin_api.py upload/url-ingest/delete endpoints | 9e7f34a | app/routes/admin_api.py |

## Verification Results

All acceptance criteria verified:

- `@require_auth` count: 3 (all three handlers protected)
- `/dochat/admin/ingest/upload` route: registered
- `/dochat/admin/ingest/url` route: registered
- `/dochat/admin/docs/<doc_id>` DELETE route: registered
- `_delete_document` count: 3 (import + call + already in ingestion.py, but 2 in this file: import + call)
- `conn.execute("BEGIN")` count: 1
- `conn.execute("COMMIT")` count: 1
- `conn.execute("ROLLBACK")` count: 2 (guard + except)
- `Document not found` in jsonify return: 1 (plus 1 in docstring — behavior correct)
- `with conn:` in actual code: 0 (docstring mention only)
- Route registration: `/dochat/admin/ingest/upload`, `/dochat/admin/ingest/url`, `/dochat/admin/docs/<doc_id>` all in url_map
- 62/62 tests passing

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all three endpoints are fully implemented with real ingestion service calls and proper error handling.

## Threat Surface Scan

All threat mitigations from the plan's threat model are implemented:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-04-08 | `os.path.basename(file.filename)` strips path components from upload filename | Mitigated |
| T-04-09 | `_validate_url()` reused from ingest.py — blocks localhost, 169.254.x, non-http(s) schemes | Mitigated |
| T-04-10 | All SQL uses parameterized queries `[doc_id]` — no string interpolation | Mitigated |
| T-04-11 | `MAX_FILE_BYTES = 10 * 1024 * 1024` check before any processing, returns 413 | Mitigated |
| T-04-12 | `@require_auth` on DELETE handler — unauthenticated DELETE returns 401 | Mitigated |

No new threat surface introduced beyond what was planned.

## Self-Check

---

## Self-Check: PASSED

Files verified:
- [FOUND] app/routes/admin_api.py

Commits verified:
- [FOUND] 9e7f34a feat(04-03): implement admin API endpoints — upload, url-ingest, delete

All 62 tests passing.
