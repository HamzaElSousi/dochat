---
phase: 05-chat-widget
plan: "03"
subsystem: delivery
tags: [flask, static-file, htaccess, pytest, widget, cgi]

# Dependency graph
requires:
  - phase: 05-chat-widget-plan-02
    provides: app/static/widget.js — self-contained Shadow DOM chat widget

provides:
  - GET /dochat/widget.js Flask route in create_app() via send_from_directory
  - staging_widget_htaccess_patch.txt with anchored RewriteRule for CGI routing
  - tests/test_widget_delivery.py — 5 automated delivery tests

affects:
  - phase-06-lead-capture (widget embed URL is now resolvable at /dochat/widget.js)

# Tech tracking
tech-stack:
  added:
    - flask.send_from_directory (already in Flask — explicit import added to app/__init__.py)
  patterns:
    - Static file serving via custom route (not Flask default /static/) — required to serve at /dochat/widget.js
    - send_from_directory with explicit filename to prevent path traversal (T-05-11)
    - Anchored RewriteRule ^dochat/widget\.js$ with escaped dot for exact URL match

key-files:
  created:
    - staging_widget_htaccess_patch.txt
    - tests/test_widget_delivery.py
  modified:
    - app/__init__.py

key-decisions:
  - "Route added directly in create_app() (not a new Blueprint) — simplest integration, no extra file"
  - "send_from_directory uses os.path.dirname(__file__) to resolve app/static/ — not the root static/ folder that Flask's static_folder points to"
  - ".htaccess rule uses escaped dot (widget\\.js) and anchoring (^...$) matching Phase 4 pattern"

patterns-established:
  - "Widget delivery via Flask custom route at /dochat/* prefix (consistent with all other DocChat routes)"

requirements-completed:
  - WIDGET-01
  - WIDGET-02
  - WIDGET-03
  - WIDGET-04
  - WIDGET-05
  - WIDGET-06
  - WIDGET-07
  - WIDGET-08

# Metrics
duration: 5min
completed: 2026-05-10
---

# Phase 5 Plan 03: Widget Delivery & Integration Summary

**Flask route at /dochat/widget.js serving app/static/widget.js, .htaccess CGI RewriteRule, and 5 automated delivery tests — all 95 tests pass; human visual verification checkpoint pending**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-10
- **Tasks:** 1 of 1 automated (+ 1 human checkpoint pending)
- **Files modified:** 3

## Accomplishments

- Added `widget_js()` route in `create_app()` — serves `app/static/widget.js` at `/dochat/widget.js` using `send_from_directory` with explicit `mimetype='application/javascript'`
- Created `staging_widget_htaccess_patch.txt` with anchored `RewriteRule ^dochat/widget\.js$ /app.cgi/dochat/widget.js [QSA,L]` matching the Phase 4 .htaccess format
- Created `tests/test_widget_delivery.py` with 5 tests: 200 status, JavaScript content-type, `attachShadow` presence, `dochat_session_id` presence, and no ES module import statements
- All 95 tests pass (90 prior + 5 new delivery tests)

## Task Commits

1. **Task 1: Flask route + .htaccess patch + delivery tests** — `62e9a78` (feat)

## Files Created/Modified

- `app/__init__.py` — Added `from flask import send_from_directory` to import line; added `widget_js()` route inside `create_app()` after blueprint registration
- `staging_widget_htaccess_patch.txt` — New file: Phase 5 .htaccess RewriteRule for staging server widget.js URL routing
- `tests/test_widget_delivery.py` — New file: 5 delivery tests verifying GET /dochat/widget.js returns 200, correct content-type, Shadow DOM code, session key, and no module imports

## Decisions Made

- Route added directly in `create_app()` (not a new Blueprint) — no extra file needed for a single static-file route
- `send_from_directory` resolves `app/static/` via `os.path.dirname(__file__)` — `app/__init__.py`'s `static_folder` points to root-level `static/` (different directory), so an explicit path is required

## Deviations from Plan

None — plan executed exactly as written.

## Human Checkpoint Status

**PENDING** — Task 2 is `type="checkpoint:human-verify"`. The automated gate (Task 1) is complete. Awaiting human verification:
- FAB button visible on bare HTML embed page, unaffected by host CSS injection
- Panel opens/closes correctly, typing indicator appears
- Mobile layout at ≤480px works

## Known Stubs

None.

## Threat Flags

No new threat surface introduced beyond the plan's `<threat_model>`:
- T-05-10 (.htaccess RewriteRule): Anchored rule `^dochat/widget\.js$` with escaped dot — exact match only, no wildcard traversal, [L] flag stops further processing — mitigated as planned
- T-05-11 (send_from_directory): Explicit `filename='widget.js'` prevents path traversal — mitigated as planned
- T-05-09 (public file): widget.js intentionally public, contains no secrets — accepted as planned

## Self-Check

Files exist:
- `app/__init__.py` — FOUND
- `staging_widget_htaccess_patch.txt` — FOUND
- `tests/test_widget_delivery.py` — FOUND

Commits exist:
- `62e9a78` — FOUND

## Self-Check: PASSED

---
*Phase: 05-chat-widget*
*Completed: 2026-05-10*
