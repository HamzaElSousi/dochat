---
phase: 06-lead-capture
plan: "03"
subsystem: admin-ui-and-widget
tags: [admin-settings, widget, lead-capture, shadow-dom, vanilla-js, phase-6]
dependency_graph:
  requires:
    - 06-01-PLAN.md (settings table in DB, phone column in leads)
    - 06-02-PLAN.md (POST /dochat/admin/settings, GET /dochat/api/settings, POST /dochat/api/leads routes)
  provides:
    - templates/admin/settings.html (Settings admin page)
    - templates/admin/base.html: Settings nav tab
    - static/admin.js: saveSettings() function
    - app/static/widget.js: addLeadForm(), fetchSettings(), _leadSubmitted flag, dc-lead-form CSS
  affects:
    - Admin nav bar (Settings tab added)
    - Widget fallback response handling (lead form instead of fallback bubble)
tech_stack:
  added: []
  patterns:
    - Shadow DOM element creation (textContent-only, no innerHTML) for XSS safety
    - URL derivation from apiUrl via regex replace (/chat -> /api/settings, /api/leads)
    - In-memory _leadSubmitted boolean to prevent re-showing form (D-02)
    - Non-blocking fetchSettings() on widget init (silent failure, non-critical)
key_files:
  modified:
    - templates/admin/base.html
    - static/admin.js
    - app/static/widget.js
  created:
    - templates/admin/settings.html
decisions:
  - "addLeadForm() uses textContent (not innerHTML) for all dynamic content — satisfies T-06-10"
  - "CTA button href set as anchor .href property (not innerHTML); rel=noopener noreferrer added — satisfies T-06-11"
  - "settings.html uses Jinja2 {{ book_call_url | e }} for HTML-escaped input value — satisfies T-06-12"
  - "fetchSettings() is silent-fail: catch block swallowed — non-critical for widget operation"
  - "node --check confirms no syntax errors; window ReferenceError in Node is expected browser-only runtime behavior"
metrics:
  duration: "12 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
requirements:
  - LEADS-01
  - LEADS-02
---

# Phase 6 Plan 03: Admin Settings UI and Widget Lead Capture Summary

**One-liner:** Settings nav tab + settings.html template + saveSettings() handler in admin, plus widget _leadSubmitted flag, fetchSettings() on init, addLeadForm() with name/email/phone fields, thank-you message, and Book a Call CTA button.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Admin Settings UI — base.html nav tab + settings.html + admin.js handler | 9a5d390 | templates/admin/base.html, templates/admin/settings.html, static/admin.js |
| 2 | Widget lead capture form — _leadSubmitted flag, settings fetch, form render, CTA | c530404 | app/static/widget.js |

## What Was Built

### Task 1 — Admin Settings UI

- `templates/admin/base.html`: Added Settings nav tab after Leads link with `aria-current="page"` wiring for `active_page == 'settings'`.
- `templates/admin/settings.html`: New template extending `admin/base.html`. Contains a labeled URL input for `book_call_url`, a hint text, an inline feedback div (`role="alert" aria-live="polite"`), and a Save Settings button. Jinja2 `{{ book_call_url | e }}` escapes the value (T-06-12).
- `static/admin.js`: Added `saveSettings(url)` function that POSTs JSON `{book_call_url}` to `/dochat/admin/settings`, shows inline feedback ("Settings saved." in green or error in red), and handles network failures gracefully. DOMContentLoaded handler wires settings form submit to `saveSettings()`.

### Task 2 — Widget Lead Capture Form

- **State additions**: `_leadSubmitted: false` (D-02 flag) and `_settingsUrl: ''` (D-12 storage) added to the state object.
- **CSS**: Added `dc-lead-form`, `dc-lead-submit`, `dc-cta-btn`, and `dc-thankyou` CSS class definitions inside the Shadow DOM style array before the `@media (prefers-reduced-motion)` block.
- **fetchSettings()**: Derives settings URL from `cfg.apiUrl` by replacing trailing `/chat` with `/api/settings` (or uses `cfg.settingsUrl` directly). Fetches on init when `cfg.apiUrl` is set. Stores `book_call_url` in `state._settingsUrl`. Silent failure — non-critical.
- **addLeadForm(question)**: Renders a div.dc-lead-form inside the chat message list with heading, Name/Email/Phone inputs (maxLength constraints), and Send button. On submit: validates name + email (red border highlight on blank), POSTs to `/api/leads`, sets `_leadSubmitted = true`, replaces form with dc-thankyou div + optional Book a Call `<a>` CTA button (only if `state._settingsUrl` is set). Error: re-enables button, appends `.dc-lead-err` paragraph.
- **sendMessage() fallback branch**: Replaced unconditional `addBotBubble()` with conditional: `if (data.fallback && !state._leadSubmitted) addLeadForm(text); else addBotBubble(...)`. Implements D-01 (trigger on any fallback), D-02 (once-per-session form), D-03 (form replaces bubble).

## Verification Results

- `python3 -m pytest tests/test_widget_delivery.py -x -q`: 5/5 passed
- `python3 -m pytest tests/test_admin.py -x -q`: 14/14 passed
- `node --check app/static/widget.js`: SYNTAX OK
- Task 1 Flask: GET /dochat/admin/settings returns 200 with book_call_url input and Settings nav link
- All grep acceptance criteria: passed (counts confirmed)

## Deviations from Plan

None — plan executed exactly as written. All five sections of widget.js modifications applied in order without restructuring the IIFE.

## Known Stubs

None — all wiring is complete end-to-end. `state._settingsUrl` defaults to empty string (no CTA button rendered when settings fetch hasn't returned a URL or returned empty). This is intentional graceful degradation (not a stub — the button is genuinely omitted when no URL is configured).

## Threat Flags

None beyond what the plan's threat model already covered. All three mitigations from the threat register were applied:
- T-06-10: textContent used throughout addLeadForm() — no innerHTML for dynamic content
- T-06-11: CTA href set as `.href` property; `rel="noopener noreferrer"` applied
- T-06-12: `{{ book_call_url | e }}` in settings.html Jinja2 template

## Self-Check: PASSED

- templates/admin/base.html modified: EXISTS
- templates/admin/settings.html created: EXISTS
- static/admin.js modified: EXISTS
- app/static/widget.js modified: EXISTS
- Commit 9a5d390 (Task 1): FOUND
- Commit c530404 (Task 2): FOUND
- 5 widget delivery tests passing: CONFIRMED
- 14 admin tests passing: CONFIRMED
