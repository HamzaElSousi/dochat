---
phase: 04-admin-ui
plan: "01"
subsystem: database, api
tags: [flask, sqlite, blueprint, leads, admin, auth]

# Dependency graph
requires:
  - phase: 03-query-pipeline-rag-logic
    provides: chat_bp pattern, app/__init__.py factory, app/db.py session tables pattern
  - phase: 02-document-ingestion-pipeline
    provides: require_auth decorator, _open_db() pattern
provides:
  - leads table DDL in app/db.py (CREATE TABLE IF NOT EXISTS leads)
  - admin_bp blueprint stub with /dochat/admin, /dochat/admin/docs, /dochat/admin/leads routes
  - admin_api_bp blueprint stub registered in app factory
  - All admin routes protected by @require_auth HTTP Basic Auth
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "init_leads_table(conn) pattern — add Phase N DDL after init_session_tables() in init_db()"
    - "Blueprint stub pattern — register early, implement routes in subsequent plan"

key-files:
  created:
    - app/routes/admin.py
    - app/routes/admin_api.py
  modified:
    - app/db.py
    - app/__init__.py

key-decisions:
  - "Route prefix /dochat/admin (not /admin) — avoids conflict with existing PHP backend at social-automate.com"
  - "admin_bp and admin_api_bp registered as stubs so Wave 1 unblocks all downstream plans simultaneously"
  - "leads table schema created in Phase 4 with all columns; Phase 6 will populate it via capture route"

patterns-established:
  - "Blueprint stub: create file with Blueprint() declaration + guarded routes, register in factory immediately"
  - "DDL ordering: append init_<table>_table(conn) calls in init_db() after existing schema calls"

requirements-completed:
  - ADMIN-01
  - ADMIN-06

# Metrics
duration: 15min
completed: 2026-05-09
---

# Phase 4 Plan 01: Admin UI Foundation Summary

**leads table DDL added to app/db.py and admin_bp/admin_api_bp blueprint stubs registered in Flask factory with @require_auth on all admin routes**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-09T (wave start)
- **Completed:** 2026-05-09
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `init_leads_table()` to `app/db.py` with correct 5-column schema (id, name, email, question, created_at) called from `init_db()`
- Created `app/routes/admin.py` with `admin_bp` Blueprint and three stub routes all protected by `@require_auth`
- Created `app/routes/admin_api.py` with `admin_api_bp` Blueprint stub
- Registered both blueprints in `create_app()` in `app/__init__.py`
- All 62 existing tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add leads table DDL to app/db.py** - `0e29a1a` (feat)
2. **Task 2: Create admin blueprint stubs + register in app factory** - `420471d` (feat)
3. **Task 3: Verify all existing tests still pass** - verification only, no commit needed

## Files Created/Modified

- `app/db.py` - Added `init_leads_table()` function and call in `init_db()`
- `app/__init__.py` - Added admin_bp and admin_api_bp imports and `register_blueprint()` calls
- `app/routes/admin.py` - New: admin_bp with /dochat/admin, /dochat/admin/docs, /dochat/admin/leads stubs
- `app/routes/admin_api.py` - New: admin_api_bp stub (routes implemented in Plan 03)

## Decisions Made

- Route prefix locked at `/dochat/admin` per D-01 (existing PHP backend at `/admin`)
- `admin_bp` registered as stub immediately so Plans 02-04 can work in parallel (Wave 1 purpose)
- `admin_api_bp` stub has no routes yet; Plan 03 will add POST/DELETE endpoints

## Deviations from Plan

None - plan executed exactly as written.

Note: The worktree was initially 44 commits behind master (worktree was spawned from Phase 1 commit). A fast-forward merge was performed before implementing tasks to bring the worktree to master state. This is not a deviation — it's a worktree setup correction.

## Issues Encountered

- Worktree was spawned from commit `bf98634` (Phase 1 deployment fix) rather than `master`. Used `git merge master --ff-only` to fast-forward before starting work. All master commits applied cleanly with no conflicts.

## Known Stubs

- `app/routes/admin.py` — `admin_docs()` and `admin_leads()` return `'Coming soon', 200`. These are intentional stubs; Plan 02 replaces the bodies with full Jinja2 template renders.
- `app/routes/admin_api.py` — No routes defined yet. Plan 03 implements POST /dochat/admin/ingest/upload, POST /dochat/admin/ingest/url, DELETE /dochat/admin/docs/<doc_id>.

These stubs are intentional Wave 1 scaffolding — downstream plans in this wave depend on the blueprints being importable and registered.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can now implement admin HTML templates (admin_docs, admin_leads route bodies)
- Plan 03 can now implement admin API routes in admin_api_bp
- Plan 04 can now add .htaccess rewrite rules and deploy
- The `leads` table schema exists and is queryable (empty until Phase 6)

---
*Phase: 04-admin-ui*
*Completed: 2026-05-09*
