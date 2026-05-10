---
phase: 06-lead-capture
plan: "02"
subsystem: backend-routes
tags: [flask, sqlite, cors, smtp, lead-capture, settings, phase-6]
dependency_graph:
  requires:
    - 06-01-SUMMARY.md (phone column in leads, settings table, send_lead_notification)
  provides:
    - app/routes/admin.py:admin_settings (GET /dochat/admin/settings, @require_auth)
    - app/routes/admin_api.py:admin_settings_save (POST /dochat/admin/settings, @require_auth)
    - app/routes/admin_api.py:public_leads (POST /dochat/api/leads, public, CORS)
    - app/routes/admin_api.py:public_settings (GET /dochat/api/settings, public, CORS)
  affects:
    - Widget JS (reads /dochat/api/settings on init, POSTs /dochat/api/leads on form submit)
    - Admin UI (Settings tab now backed by live route)
tech_stack:
  added:
    - uuid (stdlib — lead ID generation)
    - datetime.timezone (stdlib — UTC timestamp)
  patterns:
    - CORS allowlist via _cors_headers_leads() matching chat.py pattern
    - Manual BEGIN/COMMIT/ROLLBACK for all writes (no context manager)
    - Non-fatal email call: send_lead_notification() called after DB commit; failure logged, 200 still returned
    - Input length bounds on all lead fields (T-06-07 mitigation)
key_files:
  modified:
    - app/routes/admin.py
    - app/routes/admin_api.py
decisions:
  - "Input length bounds applied on all public_leads() fields (name<=200, email<=254, phone<=30, question<=2000) per T-06-07 threat model mitigation — auto-added via Rule 2"
  - "_cors_headers_leads() defined locally in admin_api.py rather than importing from chat.py — avoids cross-blueprint import coupling; same pattern, different function name"
  - "ALLOWED_ORIGINS read at module load in admin_api.py (same as chat.py) — CGI-safe because fresh process per request re-imports the module"
metrics:
  duration: "12 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
requirements:
  - LEADS-01
  - LEADS-03
  - LEADS-04
---

# Phase 6 Plan 02: Backend Routes for Lead Capture and Settings Summary

**One-liner:** Four Flask routes wiring the lead capture and settings subsystem — protected admin settings GET/POST and public widget-facing leads POST + settings GET, with CORS, input bounds, and non-fatal SMTP integration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Admin settings routes — GET + POST /dochat/admin/settings | a500f55 | app/routes/admin.py, app/routes/admin_api.py |
| 2 | Public API routes — POST /dochat/api/leads + GET /dochat/api/settings | 98bd7d0 | app/routes/admin_api.py |

## What Was Built

### Task 1 — Admin Settings Routes

**app/routes/admin.py — `admin_settings()`**
- GET `/dochat/admin/settings` — reads `book_call_url` from settings table (empty string if unset), renders `admin/settings.html` with `active_page='settings'`
- Protected by `@require_auth`

**app/routes/admin_api.py — `admin_settings_save()`**
- POST `/dochat/admin/settings` — accepts JSON or form body, upserts `book_call_url` into settings table via `INSERT OR REPLACE`
- Manual `BEGIN/COMMIT/ROLLBACK` pattern; returns `{"saved": true, "book_call_url": "..."}`
- Protected by `@require_auth`

### Task 2 — Public API Routes

**app/routes/admin_api.py — `public_leads()`**
- POST `/dochat/api/leads` — accepts `{name, email, phone, question}` JSON
- Enforces input length bounds: name<=200, email<=254, phone<=30, question<=2000 (T-06-07)
- Returns 400 if name or email is missing/empty
- Inserts lead into `leads` table with UUID id and UTC timestamp
- Calls `send_lead_notification()` after successful DB commit — failure is non-fatal, returns 200 regardless
- CORS headers applied via `_cors_headers_leads()` for ALLOWED_ORIGINS
- OPTIONS preflight returns 204

**app/routes/admin_api.py — `public_settings()`**
- GET `/dochat/api/settings` — returns `{"book_call_url": "..."}` from settings table
- No auth required (intentionally public — widget reads it on init)
- CORS headers applied via `_cors_headers_leads()`
- OPTIONS preflight returns 204

**Module-level additions in admin_api.py:**
- `import uuid`, `from datetime import datetime, timezone`
- `from ..services.email import send_lead_notification`
- `_ALLOWED_ORIGINS` list from `ALLOWED_ORIGINS` env var
- `_cors_headers_leads()` helper function

## Verification Results

- Task 1 automated verify: PASSED (401 without auth, 200 with auth, settings save round-trip)
- Task 2 automated verify: PASSED (settings round-trip, lead save with mock SMTP, 400 on missing name)
- `python3 -m pytest tests/test_admin.py tests/test_db.py -x -q`: 22/22 passed

## Deviations from Plan

### Auto-added (Rule 2 — Missing Critical Functionality)

**[Rule 2 - Security] Input length bounds on public_leads() fields**
- **Found during:** Task 2 implementation — threat model T-06-07 dispositioned as `mitigate`
- **Issue:** Plan action block did not include the length-bound slicing in the code snippet, but the success criteria and threat model both require it
- **Fix:** Added `[:200]`, `[:254]`, `[:30]`, `[:2000]` slices on name, email, phone, question respectively, with validation check preserved on the unsliced values
- **Files modified:** app/routes/admin_api.py
- **Commit:** 98bd7d0

## Known Stubs

None — all routes are fully wired to the database. No hardcoded empty values flow to widget or admin UI. The `book_call_url` defaults to empty string when not configured (intentional per D-10 — no pre-seeded rows).

## Threat Flags

None — all new endpoints are within the threat model scope defined in the plan. No new network surface beyond what was planned.

| Threat | Mitigation Applied |
|--------|--------------------|
| T-06-04 (SQL injection) | Parameterized queries with ? placeholders throughout |
| T-06-05 (CORS spoofing) | _cors_headers_leads() checks against ALLOWED_ORIGINS allowlist |
| T-06-07 (DoS via long fields) | Input sliced to name<=200, email<=254, phone<=30, question<=2000 |
| T-06-09 (unauthenticated admin settings) | @require_auth on POST /dochat/admin/settings |

## Self-Check: PASSED

- app/routes/admin.py modified: EXISTS
- app/routes/admin_api.py modified: EXISTS
- Commit a500f55 (Task 1): FOUND
- Commit 98bd7d0 (Task 2): FOUND
- 22 admin + db tests passing: CONFIRMED
- `def admin_settings` in admin.py: 1 (confirmed)
- `def admin_settings_save` in admin_api.py: 1 (confirmed)
- `def public_leads` in admin_api.py: 1 (confirmed)
- `def public_settings` in admin_api.py: 1 (confirmed)
- `send_lead_notification` in admin_api.py: 2 (import + call, confirmed)
