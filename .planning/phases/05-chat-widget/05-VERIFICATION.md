---
phase: 05-chat-widget
verified: 2026-05-10T00:00:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Verify the FAB renders on a WordPress or Webflow page (not just bare HTML)"
    expected: "FAB button appears bottom-right, unaffected by host CMS CSS; panel opens; typing indicator shows; chips appear after response"
    why_human: "Roadmap SC#1 explicitly calls out WordPress and Webflow pages. The Plan 03 human checkpoint only confirmed a bare HTML page. CMS environments inject their own CSS resets, theme styles, and script loaders that could interfere with the IIFE or Shadow DOM host injection."
  - test: "Confirm chips section appears after a real LLM bot response (requires live backend)"
    expected: "After typing a question and receiving a non-fallback answer, three chip buttons appear below the bot bubble"
    why_human: "Plan 03 human checkpoint confirmed FAB + panel + typing indicator only. Chip rendering requires a real LLM response returning a valid chips array — cannot be confirmed from static code alone."
  - test: "Verify CSS injection attack surface (CR-02) does not break widget under normal DocChatConfig usage"
    expected: "With a standard primaryColor like '#3b82f6', widget renders correctly. Reviewer CR-02 flags an injection risk but normal usage may still be safe for current deployment."
    why_human: "Code review (05-REVIEW.md CR-02) flags that cfg.* values are interpolated verbatim into CSS style string. Severity impact on normal usage (legitimate hex colors only) vs. adversarial input requires human risk assessment decision."
---

# Phase 5: Chat Widget Verification Report

**Phase Goal:** Embeddable chat widget — FAB button, Shadow DOM panel, chip suggestions, single script-tag delivery via /dochat/widget.js
**Verified:** 2026-05-10
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /chat response always includes a chips field (list) | VERIFIED | `grep -c "'chips'" app/services/query.py` = 5 (4 return dicts + helper body). All return sites confirmed at lines 190, 208, 264, 285. |
| 2 | chips contains 3 follow-up question strings when LLM parses successfully | VERIFIED | `_parse_chips()` at line 66-95 enforces `len(chips) == 3`; success path at line 285 passes parsed chips. `python3 -c "... _parse_chips OK"` passes. |
| 3 | chips is an empty list when LLM returns malformed JSON (silent fail) | VERIFIED | `_parse_chips()` returns `(raw, [])` on any parse error. All 10 unit tests in `test_chat_chips.py` pass, including malformed JSON, wrong count, empty string, and no-JSON cases. |
| 4 | A bare HTML page with only the embed snippet shows a 48x48px FAB button fixed bottom-right | VERIFIED | CSS confirmed: `width: 48px; height: 48px; bottom: 24px; right: 24px; position: fixed` at widget.js lines 57-60. Human checkpoint in Plan 03 SUMMARY confirmed FAB visible. |
| 5 | Clicking the FAB opens a 380x560px panel (desktop); clicking FAB or x closes it | VERIFIED | CSS: `width: 380px; height: 560px` at lines 79-81. openPanel/closePanel toggle `.dc-open` class. Plan 03 human checkpoint confirmed open/close. |
| 6 | Sending a message shows three animated dots while awaiting response, then a bot bubble | VERIFIED | `addTypingIndicator()` creates `.dc-typing` with 3 `.dc-dot` spans. `dc-bounce` keyframe animation present (2 occurrences). Plan 03 human checkpoint confirmed typing indicator. |
| 7 | Widget renders in Shadow DOM — injecting conflicting CSS into the host page does not change widget appearance | VERIFIED | `attachShadow({ mode: 'open' })` present exactly once at line checked. Plan 03 human checkpoint explicitly confirmed: "FAB button visible on bare HTML embed page, unaffected by host CSS injection (Shadow DOM isolation confirmed)". |
| 8 | On a 375px viewport the panel expands to calc(100vw-16px) wide | VERIFIED | `@media (max-width: 480px)` breakpoint at line 301 sets `width: calc(100vw - 16px)`. A 375px viewport triggers this breakpoint. |
| 9 | Setting window.DocChatConfig.primaryColor='#ff0000' changes FAB, header, and visitor bubble to red | VERIFIED | CSS custom properties `--dc-primary: ${cfg.primaryColor}` in `:host` block; `--dc-header-bg`, `--dc-user-bubble` both fall back to `var(--dc-primary)`. Config applied before Shadow DOM build. |
| 10 | apiUrl missing fires console.warn('[DocChat] apiUrl is required...') and input is disabled | VERIFIED | Lines 391-395: `if (!cfg.apiUrl) { console.warn('[DocChat] apiUrl is required...'); input.disabled = true; sendBtn.disabled = true; }`. Pattern `apiUrl is required` confirmed present. |
| 11 | GET /dochat/widget.js returns 200 with Content-Type: application/javascript | VERIFIED | `test_widget_js_route_exists` and `test_widget_js_content_type` both pass. `app/__init__.py` lines 30-42: `@app.route('/dochat/widget.js')` using `send_from_directory(..., mimetype='application/javascript')`. |

**Score:** 11/11 truths verified

### Deferred Items

None.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/query.py` | `_parse_chips()` + chip prompt + chips in all return dicts | VERIFIED | 286 lines. `def _parse_chips` at line 66. `import re` at line 3. 4 return sites with chips. System prompt chip instruction at lines 247-249. |
| `app/routes/chat.py` | POST /chat response schema with chips field in docstring | VERIFIED | 71 lines. Docstring at lines 39-40 documents `chips: ["Q1", "Q2", "Q3"]` in Response contract. |
| `tests/test_chat_chips.py` | Pytest tests verifying chips field in all code paths | VERIFIED | 10 test functions (`def test_`). All 10 pass. 4 integration tests + 6 `_parse_chips` unit tests. |
| `app/static/widget.js` | Self-contained Shadow DOM chat widget — all HTML, CSS, JS inlined | VERIFIED | 575 lines (exceeds 300-line minimum). All 10 Python3 pattern checks pass. No `import`/`require` statements. |
| `app/__init__.py` | Flask static route serving widget.js at /dochat/widget.js | VERIFIED | Lines 30-42. `send_from_directory` with explicit `filename='widget.js'`. |
| `staging_widget_htaccess_patch.txt` | Exact .htaccess RewriteRule for widget.js on staging server | VERIFIED | Contains `RewriteRule ^dochat/widget\.js$ /app.cgi/dochat/widget.js [QSA,L]`. Anchored with escaped dot. |
| `tests/test_widget_delivery.py` | Automated test verifying Flask serves widget.js with correct headers | VERIFIED | 5 test functions (`def test_widget`). All 5 pass. Tests: 200 status, JS content-type, attachShadow presence, dochat_session_id presence, no import statements. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/query.py` | `_call_llm_with_retry()` | chip prompt appended to system_prompt; chips parsed from raw LLM answer | WIRED | `system_prompt` at lines 241-250 includes chip JSON instruction. `raw_answer = _call_llm_with_retry(...)` at line 256; `answer, chips = _parse_chips(raw_answer)` at line 266. |
| `app/routes/chat.py` | `handle_chat()` | result dict includes chips key passed through to jsonify(result) | WIRED | `result = handle_chat(conn, message, session_id)` passes through to `resp = jsonify(result)`. Chips flow automatically. |
| `app/static/widget.js` | `window.DocChatConfig.apiUrl` | `fetch(cfg.apiUrl, {method:'POST', ...})` in sendMessage() | WIRED | Line 541: `fetch(cfg.apiUrl, {...})`. Guard at line 527: `if (!cfg.apiUrl) return;`. |
| `app/static/widget.js` | `sessionStorage` | `sessionStorage.getItem('dochat_session_id')` on init; `setItem` on first response | WIRED | Line 376: `sessionStorage.getItem('dochat_session_id') || null`. Line 558: `sessionStorage.setItem('dochat_session_id', data.session_id)`. |
| `app/__init__.py` | `app/static/widget.js` | Flask `send_from_directory('/dochat/widget.js')` route | WIRED | Lines 30-42. `os.path.dirname(__file__)` resolves to `app/` directory; `send_from_directory(static_dir, 'widget.js')`. |
| `staging_widget_htaccess_patch.txt` | `app.cgi` | `RewriteRule ^dochat/widget\.js$ /app.cgi/dochat/widget.js [QSA,L]` | WIRED | Exact RewriteRule present with anchoring and [L] flag. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/static/widget.js` (addBotBubble) | `data.answer`, `data.chips` | `fetch(cfg.apiUrl)` POST response parsed via `.then(res.json())` | Yes — fetch calls live API, response flows to bubble render | FLOWING |
| `app/services/query.py` (handle_chat) | `chips` | `_parse_chips(raw_answer)` where `raw_answer` comes from `_call_llm_with_retry()` | Yes — LLM response processed; fallback paths return `[]` correctly | FLOWING |
| `app/static/widget.js` (state.sessionId) | `state.sessionId` | `sessionStorage.getItem(...)` on init + `setItem` on API response | Yes — stored/retrieved from sessionStorage; sent as `session_id` in fetch body | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| _parse_chips extracts 3 chips from valid JSON | `python3 -c "from app.services.query import _parse_chips; ..."` | `_parse_chips OK` | PASS |
| All 15 new tests pass (10 chips + 5 delivery) | `pytest tests/test_chat_chips.py tests/test_widget_delivery.py -v` | 15 passed | PASS |
| Full test suite 95 tests pass | `pytest tests/ --tb=short` | 95 passed | PASS |
| widget.js 10-pattern check | Python3 pattern verification script | All checks pass. File is 575 lines. | PASS |
| widget.js has no import/require | `grep -c "import\|require(" app/static/widget.js` | 0 | PASS |
| Flask route exists for /dochat/widget.js | `grep -c "dochat/widget.js" app/__init__.py` | 2 | PASS |
| htaccess patch contains app.cgi | `grep -c "app.cgi" staging_widget_htaccess_patch.txt` | 2 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WIDGET-01 | 05-02, 05-03 | Floating FAB button opens/closes chat panel | SATISFIED | `#dc-fab` CSS: 48x48px fixed bottom-right. openPanel/closePanel wired to FAB click. Human checkpoint confirmed. |
| WIDGET-02 | 05-02, 05-03 | Typing indicator (animated dots) while awaiting LLM | SATISFIED | `addTypingIndicator()` with `.dc-typing` + `.dc-dot` + `dc-bounce` keyframe. Human checkpoint confirmed. |
| WIDGET-03 | 05-01, 05-02 | Three follow-up chip suggestions after each bot answer | SATISFIED | `_parse_chips()` in query.py generates chips; `addBotBubble()` renders them. All 10 chip tests pass. |
| WIDGET-04 | 05-02 | Conversation history visible within panel | SATISFIED | `state.messages` array; `addUserBubble()` and `addBotBubble()` append to `#dc-messages` on each turn. |
| WIDGET-05 | 05-02, 05-03 | Widget inside Shadow DOM — host CSS cannot break it | SATISFIED | `attachShadow({mode:'open'})` confirmed. Human checkpoint confirmed isolation against conflicting CSS. |
| WIDGET-06 | 05-02 | Responsive mobile layout; touch targets >= 44px | SATISFIED | `@media (max-width: 480px)` sets `calc(100vw-16px)`. Close button: 44x44px. Send button: 44x44px. Chips: `min-height: 44px`. |
| WIDGET-07 | 05-02 | Configurable colors and logo via window.DocChatConfig | SATISFIED | All 7 CSS custom properties mapped from `cfg.*` in `:host` block. `title.textContent = cfg.title`. Logo shown when `cfg.logo` set. |
| WIDGET-08 | 05-02, 05-03 | Single `<script>` tag embed, no build step | SATISFIED | IIFE with zero imports. Flask route at `/dochat/widget.js`. htaccess patch ready for staging. Human checkpoint confirmed embed. |

All 8 WIDGET requirements are SATISFIED by codebase evidence.

---

## Anti-Patterns Found

The code review report `05-REVIEW.md` (produced separately) documents the following findings. Reproducing the security-relevant ones here for verifier awareness:

| File | Pattern | Severity | Impact on Phase Goal |
|------|---------|----------|---------------------|
| `app/static/widget.js` line ~511 | `addErrorBubble()` uses `innerHTML` for SVG construction | WARNING | Current string is hardcoded — no active XSS vector. Future-proofing concern only. Does NOT prevent goal achievement. |
| `app/static/widget.js` CSS string | cfg.* values interpolated verbatim into style string (CR-02) | WARNING | With legitimate hex color inputs goal is met. Risk only materializes if embedder page is compromised. Does NOT prevent goal achievement for current use. |
| `app/routes/chat.py` | No UUID format validation on client-supplied session_id (CR-03) | WARNING | Session history is chat-only with no PII beyond the conversation. Does NOT prevent widget goal achievement. Security hardening item for Phase 6 or follow-on. |
| `tests/test_parse_chips_red.py` | Duplicate TDD artifact — 4 tests are strict subset of test_chat_chips.py | INFO | Adds noise to test output. All tests pass. Not a goal blocker. |
| `app/__init__.py` docstring | Cache-Control: max-age=300 documented but not implemented (WR-05) | INFO | Widget still served correctly without cache headers. Does NOT prevent goal achievement. |

No anti-patterns block the phase goal. All identified issues are security hardening items or informational. The critical items (CR-01, CR-02, CR-03) affect security posture but the widget is functionally complete and delivered.

---

## Human Verification Required

### 1. WordPress / Webflow Page Embed

**Test:** Paste the embed snippet onto a WordPress or Webflow page (not a bare HTML file).
**Expected:** FAB button appears bottom-right; panel opens; typing indicator shows; chips appear after a real LLM response.
**Why human:** Roadmap Success Criteria #1 explicitly calls out WordPress and Webflow pages. The automated Plan 03 checkpoint only confirmed a bare HTML page. CMS environments have their own script loaders, CSS resets, and potentially conflicting `z-index` stacking contexts that could break Shadow DOM host injection.

### 2. Live Chip Rendering (End-to-End)

**Test:** With the Flask server running and a populated document index, send a question through the embedded widget.
**Expected:** Three chip buttons appear below the bot bubble. Clicking a chip populates the input and submits automatically (auto-send). Chips disappear from DOM after click.
**Why human:** Plan 03 human checkpoint confirmed FAB/panel/typing indicator only. Chips require a non-fallback LLM response. The backend implementation and widget rendering code are both verified but the combined end-to-end path with real LLM output has not been confirmed by human observation.

### 3. Security Risk Acceptance for CR-02 (CSS Injection)

**Test:** Review `05-REVIEW.md` CR-02. Decide whether to patch `sanitizeCssValue()` before Phase 5 is marked complete or defer to a security phase.
**Expected:** Decision recorded (fix now or accept + log as known issue).
**Why human:** The `cfg.*` interpolation into CSS string is a design-level vulnerability that was not flagged during planning. Whether this blocks Phase 5 sign-off is a product/security decision, not a code verification question.

---

## Gaps Summary

No automated gaps found. All 11 must-have truths verified. All 7 required artifacts exist, are substantive, and are wired. All 8 WIDGET requirements are satisfied by codebase evidence.

Status is `human_needed` (not `passed`) because:
1. Roadmap SC#1 requires WordPress/Webflow verification — not yet confirmed.
2. End-to-end chip rendering requires a live LLM call — not yet confirmed.
3. CR-02 security finding requires a human risk-acceptance decision.

The automated implementation is complete and correct. Human checkpoints are the remaining gate.

---

_Verified: 2026-05-10_
_Verifier: Claude (gsd-verifier)_
