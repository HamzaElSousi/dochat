# Phase 4: Admin UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 4-Admin UI
**Areas discussed:** Auth UX, Page layout, CSS approach, Upload feedback

---

## Route Prefix (pre-discussion blocker)

| Option | Description | Selected |
|--------|-------------|----------|
| `/admin` | Default from roadmap | |
| `/dochat/admin` | Namespaced to avoid conflict with existing PHP site | ✓ |

**User's choice:** `/dochat/admin`
**Notes:** User noted the site already has an existing PHP-based admin backend at `/admin` (manages leads, contracts, site settings). Using `/admin` for DocChat would conflict. `/dochat/admin` was chosen as the clearest namespace.

---

## Auth UX

| Option | Description | Selected |
|--------|-------------|----------|
| Browser Basic Auth dialog | Keep `@require_auth` stub as-is; browser shows native username/password popup | ✓ |
| Custom HTML login form | Build `/dochat/admin/login` with HTML form + Flask session cookie | |

**User's choice:** Browser Basic Auth dialog
**Notes:** HTTP Basic Auth via browser dialog is sufficient. `@require_auth` in `app/auth.py` already handles this — no new login template or session management needed.

---

## Page layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single page, tabbed | One `/dochat/admin` URL with JS tabs for Docs / Leads | |
| Multi-route navigation | Separate `/dochat/admin/docs` and `/dochat/admin/leads` with nav bar | ✓ |

**User's choice:** Multi-route navigation
**Notes:** Two distinct routes with a shared nav bar. Full page transitions between sections are acceptable for an admin-only tool.

Sub-question — docs page layout:

| Option | Description | Selected |
|--------|-------------|----------|
| Upload form above, list below | Single vertical layout on `/dochat/admin/docs` | ✓ |
| Side-by-side columns | Form left, list right | |

**User's choice:** Upload form above, list below

---

## CSS approach

| Option | Description | Selected |
|--------|-------------|----------|
| Pico.css CDN | Classless, ~10KB, one `<link>` tag | ✓ |
| Bootstrap 5 CDN | Full-featured, ~40KB CSS + ~16KB JS | |
| Raw custom CSS | Hand-rolled ~200 lines, no CDN | |

**User's choice:** Pico.css CDN
**Notes:** No npm on SiteGround — CDN-only. Pico.css classless approach means semantic HTML looks styled without adding class names to every element.

---

## Upload feedback

| Option | Description | Selected |
|--------|-------------|----------|
| XHR fetch + spinner | JS posts to JSON API, shows spinner, updates list in-place | ✓ |
| Form submit + page reload | Standard HTML form POST, server redirect + flash message | |

**User's choice:** XHR fetch + spinner

Sub-question — doc list update on success:

| Option | Description | Selected |
|--------|-------------|----------|
| Append new row immediately | JS appends row using JSON response data | ✓ |
| Reload full doc list via fetch | GET new JSON list endpoint, re-render table | |

Sub-question — document deletion:

| Option | Description | Selected |
|--------|-------------|----------|
| Delete button + confirm dialog | `confirm()` before DELETE request; row removed in-place | ✓ |
| Delete button, no confirm | Single click deletes immediately | |

---

## Claude's Discretion

- Jinja2 template structure (base template with block inheritance)
- `.htaccess` rewrite rules for all `/dochat/admin/*` routes
- `DELETE /dochat/admin/docs/<doc_id>` service implementation (file removal + sqlite-vec cleanup)
- `leads` DB table schema (created in Phase 4 for empty view; Phase 6 populates it)
- HTML5 native drag-and-drop events (no library)

## Deferred Ideas

- Custom HTML login form with Flask session cookie — deferred (HTTP Basic sufficient for solo admin)
- Document re-indexing UI — v2 backlog
- Document preview (show indexed chunks) — v2 backlog
- SSE streaming upload progress — deferred (CGI SSE untested on SiteGround)
