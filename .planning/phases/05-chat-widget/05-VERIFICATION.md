---
phase: 05-chat-widget
verified: 2026-05-10T18:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 11/11
  gaps_closed:
    - "WordPress/Webflow page embed — human approved on staging"
    - "Live chip rendering end-to-end — human approved on staging"
    - "CR-02 CSS injection risk — sanitizeCssValue() guard applied in f967ec4"
  gaps_remaining: []
  regressions: []
---

# Phase 5: Chat Widget Verification Report

**Phase Goal:** Embeddable chat widget — FAB button, Shadow DOM panel, chip suggestions, single script-tag delivery via /dochat/widget.js
**Verified:** 2026-05-10 (re-verification after code review fixes)
**Status:** passed
**Re-verification:** Yes — human checkpoints approved on staging; code review fixes applied in f967ec4

---

## Re-Verification Summary

Previous status was `human_needed` with three open items. All three are now closed:

| Item | Resolution |
|------|-----------|
| WordPress/Webflow page embed (SC#1) | Human approved on staging — FAB renders, panel opens, chips display, error handling works |
| Live chip rendering end-to-end | Human approved on staging — chips appear after real LLM response |
| CR-02 CSS injection risk | Fixed: `sanitizeCssValue()` added in f967ec4; all 7 `cfg.*` CSS interpolations now guarded |

Code review fixes applied in commit f967ec4 (all 91 tests pass):

| Fix ID | Description | File |
|--------|-------------|------|
| CR-01 | `addErrorBubble()` SVG built via `createElementNS` — no innerHTML | `app/static/widget.js` |
| CR-02 | `sanitizeCssValue()` guards all 7 DocChatConfig CSS interpolations | `app/static/widget.js` |
| CR-03 | UUID v4 regex validates client-supplied `session_id` before use | `app/routes/chat.py` |
| WR-01 | Warn at module load when `OPENROUTER_API_KEY` is missing | `app/services/query.py` |
| WR-02 | Log warning before defensive ROLLBACK in `_save_session` | `app/services/query.py` |
| WR-03 | `_parse_chips` uses `re.finditer` + takes last match (fixes first-match bug) | `app/services/query.py` |
| WR-04 | `MAX_MESSAGE_LEN` cap (2000 chars) with 400 response | `app/routes/chat.py` |
| WR-05 | `max_age=300` added to `send_from_directory` for widget.js | `app/__init__.py` |
| WR-06 | `state.loading` guard on chip click handler (double-click race fix) | `app/static/widget.js` |
| IN-01 | Deleted duplicate `tests/test_parse_chips_red.py` | (deleted) |

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /chat response always includes a chips field (list) | VERIFIED | 4 return sites + success path in `query.py`. All carry `'chips':` key. |
| 2 | chips contains 3 follow-up question strings when LLM parses successfully | VERIFIED | `_parse_chips()` enforces `len(chips) == 3`. WR-03 fix: now takes last JSON match via `re.finditer`. |
| 3 | chips is an empty list when LLM returns malformed JSON (silent fail) | VERIFIED | All error paths in `_parse_chips()` return `(raw, [])`. 10 unit tests pass. |
| 4 | A bare HTML page with only the embed snippet shows a 48x48px FAB button fixed bottom-right | VERIFIED | CSS confirmed in widget.js. Human approved on staging. |
| 5 | Clicking the FAB opens a 380x560px panel (desktop); clicking FAB or x closes it | VERIFIED | CSS: `width: 380px; height: 560px`. Human approved on staging. |
| 6 | Sending a message shows three animated dots while awaiting response, then a bot bubble | VERIFIED | `addTypingIndicator()` with `dc-bounce` keyframe. Human approved on staging. |
| 7 | Widget renders in Shadow DOM — injecting conflicting CSS into the host page does not change widget appearance | VERIFIED | `attachShadow({mode:'open'})` confirmed. Human approved isolation on staging. |
| 8 | On a 375px viewport the panel expands to calc(100vw-16px) wide | VERIFIED | `@media (max-width: 480px)` breakpoint in widget.js CSS block. |
| 9 | Setting window.DocChatConfig.primaryColor='#ff0000' changes FAB, header, and visitor bubble to red | VERIFIED | All 7 CSS custom properties now routed through `sanitizeCssValue()` before interpolation (CR-02 fix). |
| 10 | apiUrl missing fires console.warn('[DocChat] apiUrl is required...') and input is disabled | VERIFIED | Lines 398-402 in widget.js (post-fix). Pattern confirmed present. |
| 11 | GET /dochat/widget.js returns 200 with Content-Type: application/javascript | VERIFIED | Flask route in `app/__init__.py` with `max_age=300` (WR-05 fix). `test_widget_delivery.py` 5 tests pass. |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/query.py` | `_parse_chips()` + chip prompt + chips in all return dicts | VERIFIED | WR-03 fix: `re.finditer` + last match. WR-01/WR-02 warnings added. |
| `app/routes/chat.py` | POST /chat response schema with chips field; UUID validation | VERIFIED | CR-03: `_UUID_RE` validates session_id. WR-04: `MAX_MESSAGE_LEN` cap. Docstring updated. |
| `tests/test_chat_chips.py` | Pytest tests verifying chips field in all code paths | VERIFIED | 10 test functions. All pass. Duplicate `test_parse_chips_red.py` deleted (IN-01). |
| `app/static/widget.js` | Self-contained Shadow DOM chat widget — all HTML, CSS, JS inlined | VERIFIED | CR-01: `createElementNS` for error SVG. CR-02: `sanitizeCssValue()` guards 7 CSS interpolations. WR-06: loading guard on chip click. |
| `app/__init__.py` | Flask static route serving widget.js at /dochat/widget.js with cache headers | VERIFIED | WR-05: `max_age=300` added to `send_from_directory`. |
| `staging_widget_htaccess_patch.txt` | Exact .htaccess RewriteRule for widget.js on staging server | VERIFIED | `RewriteRule ^dochat/widget\.js$ /app.cgi/dochat/widget.js [QSA,L]` confirmed present. |
| `tests/test_widget_delivery.py` | Automated test verifying Flask serves widget.js with correct headers | VERIFIED | 5 test functions. All pass. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/query.py` | `_call_llm_with_retry()` | chip prompt in system_prompt; `_parse_chips(raw_answer)` extracts chips (last-match fix WR-03) | WIRED | Unchanged and verified. |
| `app/routes/chat.py` | `handle_chat()` | result dict chips key flows through jsonify(result); UUID guard before call (CR-03) | WIRED | UUID validation at line 73 before `handle_chat()` call. |
| `app/static/widget.js` | `window.DocChatConfig.apiUrl` | `fetch(cfg.apiUrl, {method:'POST',...})` in sendMessage() | WIRED | Unchanged and verified. |
| `app/static/widget.js` | `sessionStorage` | `getItem('dochat_session_id')` on init; `setItem` on first response | WIRED | Unchanged and verified. |
| `app/__init__.py` | `app/static/widget.js` | `send_from_directory` + `max_age=300` (WR-05) | WIRED | Cache header now applied. |
| `staging_widget_htaccess_patch.txt` | `app.cgi` | `RewriteRule ^dochat/widget\.js$ /app.cgi/dochat/widget.js [QSA,L]` | WIRED | Confirmed present. |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_parse_chips` extracts 3 chips from valid JSON | `python3 -c "from app.services.query import _parse_chips; ..."` | `_parse_chips OK` | PASS |
| Full test suite — 91 tests | `pytest tests/ --tb=short -q` | 91 passed in 5.32s | PASS |
| `sanitizeCssValue` guard present on all 7 CSS interpolations | `grep -c "sanitizeCssValue" app/static/widget.js` | 7 | PASS |
| `addErrorBubble` uses `createElementNS` not innerHTML | grep check | `createElementNS` present; no innerHTML in that function | PASS |
| UUID regex validates session_id in chat.py | grep check | `_UUID_RE.match(session_id_raw)` at line 73 | PASS |
| `max_age=300` in widget.js Flask route | grep check | `max_age=300` in `app/__init__.py` send_from_directory call | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WIDGET-01 | 05-02, 05-03 | Floating FAB button opens/closes chat panel | SATISFIED | Human approved on staging. Code unchanged by fixes. |
| WIDGET-02 | 05-02, 05-03 | Typing indicator (animated dots) while awaiting LLM | SATISFIED | Human approved on staging. Code unchanged by fixes. |
| WIDGET-03 | 05-01, 05-02 | Three follow-up chip suggestions after each bot answer | SATISFIED | Human approved live chip rendering on staging. WR-03 last-match fix improves reliability. |
| WIDGET-04 | 05-02 | Conversation history visible within panel | SATISFIED | Unchanged. `state.messages` array with addUserBubble/addBotBubble verified. |
| WIDGET-05 | 05-02, 05-03 | Widget inside Shadow DOM — host CSS cannot break it | SATISFIED | Human approved isolation on staging. |
| WIDGET-06 | 05-02 | Responsive mobile layout; touch targets >= 44px | SATISFIED | Unchanged. `@media (max-width: 480px)` and 44px touch targets verified. |
| WIDGET-07 | 05-02 | Configurable colors and logo via window.DocChatConfig | SATISFIED | CR-02 fix adds `sanitizeCssValue()` to all 7 config interpolations — improves security without breaking functionality. |
| WIDGET-08 | 05-02, 05-03 | Single `<script>` tag embed, no build step | SATISFIED | Human approved embed on staging. Zero imports confirmed. |

All 8 WIDGET requirements are SATISFIED.

---

## Anti-Patterns — Post-Fix Status

All critical items from the code review are resolved:

| Fix ID | Previous Finding | Resolution |
|--------|-----------------|-----------|
| CR-01 | `addErrorBubble()` innerHTML XSS surface | FIXED — `createElementNS` DOM construction |
| CR-02 | `cfg.*` values interpolated verbatim into CSS | FIXED — `sanitizeCssValue()` guards all 7 interpolations |
| CR-03 | No UUID validation on client-supplied session_id | FIXED — `_UUID_RE` regex validation in chat.py |
| WR-05 | Cache-Control missing from widget.js route | FIXED — `max_age=300` in `send_from_directory` |

No remaining blockers or warnings.

---

## Human Verification Required

None. All three human checkpoints from the initial verification have been satisfied:

1. WordPress/Webflow page embed — approved on staging.
2. Live chip rendering end-to-end — approved on staging.
3. CR-02 security risk acceptance — resolved by code fix (not acceptance); `sanitizeCssValue()` applied.

---

## Gaps Summary

No gaps. All 11 must-have truths verified. All 7 required artifacts exist, are substantive, wired, and data-flowing. All 8 WIDGET requirements satisfied. All code review findings resolved. 91 tests pass with no regressions.

---

_Verified: 2026-05-10 (re-verification)_
_Verifier: Claude (gsd-verifier)_
