---
phase: 05-chat-widget
plan: "02"
subsystem: ui
tags: [vanilla-js, shadow-dom, widget, chat, css-custom-properties, sessionStorage]

# Dependency graph
requires:
  - phase: 03-query-pipeline-rag-logic
    provides: POST /chat endpoint returning {answer, session_id, fallback, sources}
  - phase: 05-chat-widget-plan-01
    provides: chips field added to POST /chat response schema
provides:
  - app/static/widget.js — self-contained Shadow DOM chat widget, single <script> tag embeddable
  - Full theming via window.DocChatConfig → CSS custom properties
  - sessionStorage session persistence across same-tab navigation
affects: [05-chat-widget-plan-03, phase-06-lead-capture]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shadow DOM isolation: attachShadow({mode:'open'}) on host div injected into document.body"
    - "CSS custom properties injected via :host{} block in shadow root style element"
    - "IIFE pattern for zero-global-pollution widget packaging"
    - "Array.prototype.join() for multi-line CSS string construction without template literals"

key-files:
  created:
    - app/static/widget.js
  modified: []

key-decisions:
  - "Used Array.join() for CSS string instead of template literals — avoids potential escaping issues in IIFE context"
  - "Comment in file header avoids the word 'import' to keep grep-c import acceptance check clean"
  - "addTypingIndicator uses setAttribute for role/aria-label (not inline HTML) — consistent with dynamic DOM pattern in the file"

patterns-established:
  - "Widget IIFE pattern: (function(){'use strict'; cfg → shadow → style → HTML → state → events → API})();"
  - "All message text set via element.textContent not innerHTML — prevents XSS from LLM/user input (T-05-04 mitigated)"
  - "chips.slice(0,3) cap — even if backend sends >3 chips, only 3 rendered (T-05-08 mitigated)"

requirements-completed: [WIDGET-01, WIDGET-02, WIDGET-04, WIDGET-05, WIDGET-06, WIDGET-07, WIDGET-08]

# Metrics
duration: 25min
completed: 2026-05-09
---

# Phase 5 Plan 02: Chat Widget Summary

**Single-file 575-line vanilla JS Shadow DOM chat widget with full DocChatConfig theming, typing indicator, chip auto-send, and sessionStorage session persistence**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-09T00:00:00Z
- **Completed:** 2026-05-09T00:25:00Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- Created `app/static/widget.js` (575 lines) — self-contained IIFE, zero dependencies, no ES module imports
- Shadow DOM isolation via `attachShadow({mode:'open'})` — host-page CSS cannot affect widget appearance
- Full 7-property CSS custom property theming system mapped from `window.DocChatConfig` (`--dc-primary`, `--dc-header-bg`, `--dc-bot-bubble`, `--dc-user-bubble`, `--dc-text`, `--dc-radius`, `--dc-font-family`)
- FAB 48x48px fixed bottom-right (24px from edges), panel 380x560px desktop, mobile breakpoint at 480px with `calc(100vw-16px)` width
- Typing indicator with `dc-bounce` CSS keyframe animation (3 staggered dots, 1.2s each)
- Follow-up chip rendering: max 3 chips, click populates input AND submits (auto-send), chips removed from DOM on click
- `sessionStorage` key `dochat_session_id` for session persistence across same-tab navigation
- `@media (prefers-reduced-motion: reduce)` disables panel transition and dot animation
- `apiUrl` guard: `console.warn('[DocChat] apiUrl is required...')` + input disabled when absent
- All ARIA attributes: `role="log"`, `aria-live="polite"` on message area; `role="status"`, `aria-label="DocChat is typing"` on typing indicator

## Task Commits

1. **Task 1: Create app/static/widget.js — full Shadow DOM chat widget** - `ecec964` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `app/static/widget.js` — Self-contained IIFE chat widget: Shadow DOM setup, CSS custom properties, FAB/panel HTML, state management, open/close toggle, textarea auto-resize, Enter-key submit, typing indicator, chip rendering with auto-send, API fetch with session persistence, error bubble

## Decisions Made

- Used `Array.join('\n')` to build the CSS string instead of a template literal — avoids potential IIFE/escaping complexity
- Comment header says "No external modules" (not "No import/require") to keep the `grep -c "import"` acceptance check at 0
- Typing indicator ARIA attributes set via `setAttribute` for consistency with the dynamic DOM pattern used throughout the file

## Deviations from Plan

None — plan executed exactly as written. All 17 checklist items in the plan verified. Python verify script exits 0. All acceptance criteria pass.

## Issues Encountered

Minor: The comment block in the file header originally contained the word "import" (as in "No import/require"), which caused `grep -c "import\|require("` to return 1 instead of 0. Fixed by rephrasing the comment to "No external modules" — a one-line change, not a functional issue.

## Threat Surface Scan

No new threat surface introduced beyond what the plan's `<threat_model>` already covers:
- T-05-04 (XSS): All message text uses `element.textContent` — mitigated as planned
- T-05-07 (Shadow DOM): `attachShadow({mode:'open'})` — mitigated as planned
- T-05-08 (chip DoS): `chips.slice(0,3)` cap — mitigated as planned

No unplanned network endpoints, auth paths, file access patterns, or schema changes.

## User Setup Required

None — `widget.js` is a static file. No external service configuration required. The embedding site must set `window.DocChatConfig.apiUrl` before loading the script.

## Next Phase Readiness

- `app/static/widget.js` is complete and ready for Plan 03 (delivery and integration)
- Plan 03 will serve `widget.js` at `/dochat/widget.js` via Flask static route and add the `.htaccess` RewriteRule for the script URL
- No blockers

---
*Phase: 05-chat-widget*
*Completed: 2026-05-09*
