---
phase: 04-admin-ui
plan: "02"
subsystem: admin-ui, templates, static
tags: [flask, jinja2, pico-css, vanilla-js, admin, templates, drag-and-drop]

# Dependency graph
requires:
  - phase: 04-admin-ui
    plan: "01"
    provides: admin_bp stub, admin_api_bp stub, leads table DDL
  - phase: 02-document-ingestion-pipeline
    provides: require_auth decorator, documents table schema
  - phase: 03-query-pipeline-rag-logic
    provides: app factory pattern, blueprint registration idiom
provides:
  - Full admin route implementations with DB queries and template renders
  - templates/admin/base.html with Pico.css v2 CDN and custom CSS
  - templates/admin/docs.html with drop zone, URL form, error box, document table
  - templates/admin/leads.html with leads table and empty state
  - static/admin.js with all 8 required JS functions and XHR wiring
  - Flask template_folder/static_folder configured to project root
affects: [04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Flask template_folder=project_root/templates — needed when app is a package in a subdirectory"
    - "static_folder=project_root/static — same reason; Flask defaults to package directory"
    - "Jinja2 block inheritance: base.html with {% block content %}, child templates extend it"
    - "active_page variable: {% set active_page = 'docs' %} before extends to drive aria-current"
    - "escapeHtml() in admin.js — XSS prevention for all innerHTML insertions from API responses"
    - "Event delegation on #doc-table-body — handles both server-rendered and JS-appended delete buttons"

key-files:
  created:
    - templates/admin/base.html
    - templates/admin/docs.html
    - templates/admin/leads.html
    - static/admin.js
  modified:
    - app/routes/admin.py
    - app/__init__.py

key-decisions:
  - "template_folder and static_folder must be set to project root in Flask(__name__) when the factory is inside a package subdirectory — Flask defaults to resolving relative to the package directory (app/), not the project root"
  - "DOMContentLoaded comment block in admin.js causes grep -c to return 2 instead of 1 — actual addEventListener is present, behavior is correct"
  - "var used in DOMContentLoaded block per plan spec for browser compatibility; function declarations at module level use the 'use strict' pragma"

requirements-completed:
  - ADMIN-02
  - ADMIN-03
  - ADMIN-04
  - ADMIN-05

# Metrics
duration: 20min
completed: 2026-05-09
---

# Phase 4 Plan 02: Admin UI Pages Summary

**Full admin route implementations, three Jinja2 templates with Pico.css v2, and vanilla JS admin.js with drag-and-drop upload, XHR fetch, and delete confirmation wired to real DB queries**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-05-09
- **Tasks:** 3 + 1 auto-fix deviation
- **Files created/modified:** 6

## Accomplishments

- Replaced `app/routes/admin.py` stub with full implementations: `admin_docs()` queries `documents` table and renders `admin/docs.html`; `admin_leads()` queries `leads` table and renders `admin/leads.html`; `admin_root()` redirects to `admin_docs`; `_format_datetime()` helper for ISO-8601 display
- Created `templates/admin/base.html` with Pico.css v2 CDN, all custom CSS (drop zone, spinner, error box, status badges, delete button), nav bar with `aria-current="page"` driven by `active_page` variable
- Created `templates/admin/docs.html` with drop zone, URL submission form, inline error box, and document table server-rendered with Jinja2 loop
- Created `templates/admin/leads.html` with leads table server-rendered with Jinja2 loop and empty state message
- Created `static/admin.js` with all 8 required functions: `uploadFile`, `submitUrl`, `appendDocRow`, `showError`, `resetDropZone`, `resetUrlForm`, `deleteDoc`, and DOMContentLoaded event wiring
- Fixed Flask `__init__.py` to set `template_folder` and `static_folder` to project root (deviation Rule 1 auto-fix)
- All 62 existing tests pass with no regressions

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace admin route stubs | b308ef8 | app/routes/admin.py |
| 2 | Create admin templates | 3782613 | templates/admin/base.html, docs.html, leads.html |
| 3 | Create static/admin.js | 65cfdbc | static/admin.js |
| fix | Flask template_folder fix | bcb5261 | app/__init__.py |

## Verification Results

All success criteria verified:

- `GET /dochat/admin/docs` (Basic Auth) → 200 with drop zone and document table
- `GET /dochat/admin/leads` (Basic Auth) → 200 with leads table and empty state
- `GET /dochat/admin` (Basic Auth) → 302 redirect to `/dochat/admin/docs`
- `GET /dochat/admin/docs` (no auth) → 401
- Pico.css v2 CDN present in base.html
- static/admin.js has all 8 functions with correct XHR endpoints
- `python3 -m pytest tests/ -q` → 62/62 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Flask template_folder not pointing to project root**
- **Found during:** Task 2 end-to-end verification (template render test)
- **Issue:** `Flask(__name__)` resolves `template_folder` relative to the `app/` package directory (i.e., `app/templates/`). Templates were created at the project root `templates/admin/`. Jinja2 raised `TemplateNotFound: admin/docs.html`.
- **Fix:** Added `template_folder=os.path.join(project_root, 'templates')` and `static_folder=os.path.join(project_root, 'static')` to `Flask(__name__)` constructor in `app/__init__.py`.
- **Files modified:** `app/__init__.py`
- **Commit:** bcb5261

## Known Stubs

None — all routes render real templates with real DB queries. Documents and leads tables will be empty on a fresh install but the views handle empty state correctly with the `{% else %}` clause in Jinja2 for-loops.

Note: `static/admin.js` XHR endpoints target `/dochat/admin/ingest/upload`, `/dochat/admin/ingest/url`, and `DELETE /dochat/admin/docs/{docId}` — these are implemented in Plan 03. The JS is complete; the API endpoints are the stub.

## Threat Surface Scan

No new threat surface beyond what was planned.

| Mitigation | File | Status |
|------------|------|--------|
| T-04-04: XSS in appendDocRow | static/admin.js | Mitigated — escapeHtml() applied to all doc fields before innerHTML insertion |
| T-04-05: XSS in Jinja2 templates | templates/admin/*.html | Accepted — Jinja2 auto-escapes {{ }} expressions in HTML templates |
| T-04-06: Unauthenticated access | app/routes/admin.py | Mitigated — @require_auth on all three route functions, verified 401 returned |
| T-04-07: Information disclosure | app/routes/admin.py | Accepted — all list endpoints behind Basic Auth |

## Self-Check

Checking created files exist and commits are valid...

---

## Self-Check: PASSED

Files verified:
- [FOUND] app/routes/admin.py
- [FOUND] templates/admin/base.html
- [FOUND] templates/admin/docs.html
- [FOUND] templates/admin/leads.html
- [FOUND] static/admin.js
- [FOUND] app/__init__.py

Commits verified:
- [FOUND] b308ef8 feat(04-02): replace admin route stubs
- [FOUND] 3782613 feat(04-02): create admin HTML templates
- [FOUND] 65cfdbc feat(04-02): create static/admin.js
- [FOUND] bcb5261 fix(04-02): configure Flask template_folder and static_folder

All 62 tests passing.
