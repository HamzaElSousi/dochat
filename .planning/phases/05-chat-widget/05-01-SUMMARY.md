---
phase: 05-chat-widget
plan: "01"
subsystem: api
tags: [flask, sqlite, openrouter, llm, rag, chips, pytest]

# Dependency graph
requires:
  - phase: 03-query-pipeline-rag-logic
    provides: handle_chat() RAG pipeline, POST /chat endpoint, _call_llm_with_retry()

provides:
  - _parse_chips() helper in app/services/query.py — extracts chips JSON from raw LLM output
  - Chip prompt injection in system_prompt — LLM asked to output follow-up chips JSON after answer
  - chips field in all 4 return sites of handle_chat() (3 fallback paths + success path)
  - Updated POST /chat response schema documented in chat.py docstring
  - tests/test_chat_chips.py with 10 chip tests (4 integration + 6 unit)

affects:
  - 05-02-widget-js (widget JS must read chips field from /chat response)
  - 05-03-delivery (no change — chips already in response schema)

# Tech tracking
tech-stack:
  added:
    - re (Python stdlib regex module — added import for chip JSON extraction)
  patterns:
    - LLM structured output via prompt injection: chip JSON block appended after answer text
    - Silent parse failure: _parse_chips() returns (raw, []) on any error — never raises
    - Chip-stripped answer stored in session history (not raw_answer with JSON block)

key-files:
  created:
    - tests/test_parse_chips_red.py (TDD RED commit — 4 failing tests before implementation)
    - tests/test_chat_chips.py (10 chip tests: 4 integration via mock + 6 _parse_chips unit tests)
  modified:
    - app/services/query.py (import re, _parse_chips(), system_prompt update, all return sites)
    - app/routes/chat.py (docstring updated to declare chips in response contract)

key-decisions:
  - "chips=[] on all fallback paths — no LLM call was made so no chips can be generated"
  - "_parse_chips() enforces exactly 3 chips — not 2 or 4; rejects empty strings after strip"
  - "Chip JSON block stripped from answer_text before storing in session history (D-06)"
  - "TDD RED commit made before implementation to satisfy tdd=true task requirement"

patterns-established:
  - "LLM chip extraction: regex finds last {chips:[...]} block; json.loads in try/except; length==3 check"
  - "All handle_chat() return dicts include 'chips' key — never absent from response schema"

requirements-completed:
  - WIDGET-03

# Metrics
duration: 4min
completed: 2026-05-10
---

# Phase 5 Plan 01: Backend Chat Chips Summary

**LLM follow-up chip generation added to POST /chat: _parse_chips() extracts 3 questions from structured JSON appended to LLM answer, chips=[] on any parse failure or fallback path**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-10T03:40:19Z
- **Completed:** 2026-05-10T03:44:12Z
- **Tasks:** 2 (+ 1 TDD RED commit)
- **Files modified:** 4

## Accomplishments

- Added `_parse_chips()` to `app/services/query.py` — extracts `{"chips": [...]}` JSON block from raw LLM output, validates exactly 3 non-empty strings, returns chip-stripped answer text
- Updated system_prompt to instruct LLM to append chips JSON after every answer
- All 4 return sites in `handle_chat()` now include `'chips'` key (3 fallback paths return `[]`, success path returns parsed chips)
- Session history stores chip-stripped answer text, not raw LLM output
- Created `tests/test_chat_chips.py` with 10 tests covering all chip code paths; 90/90 total tests pass

## Task Commits

Each task was committed atomically:

1. **TDD RED: test_parse_chips_red.py** - `a3149f4` (test)
2. **Task 1: _parse_chips() + handle_chat() updates** - `1b8f213` (feat)
3. **Task 2: chat.py docstring + test_chat_chips.py** - `8d5d4f6` (feat)

_Note: Task 1 used TDD — RED commit (a3149f4) before implementation commit (1b8f213)_

## Files Created/Modified

- `app/services/query.py` — Added `import re`, `_parse_chips()` function, chip prompt in system_prompt, `chips` field in all 4 return dicts, `raw_answer`/`answer`/`chips` variable split at Step 7
- `app/routes/chat.py` — Docstring updated: `chips: ["Q1", "Q2", "Q3"]` in Response contract; no logic changes needed (handle_chat result passes through jsonify automatically)
- `tests/test_chat_chips.py` — 10 tests: 4 integration (via `patch('app.routes.chat.handle_chat')`), 6 unit tests for `_parse_chips()` directly
- `tests/test_parse_chips_red.py` — TDD RED file: 4 failing tests created before implementation

## Decisions Made

- `_parse_chips()` enforces exactly 3 chips (not 2, not 4) — the plan's `<behavior>` spec is strict; partial lists are rejected silently
- Chip JSON stripped from `answer_text` before saving to session history — prevents chip JSON from leaking into next-turn LLM context window
- TDD RED file (`test_parse_chips_red.py`) kept in the test suite since all RED tests now pass green — they duplicate `test_chat_chips.py` coverage; this is harmless and maintains the audit trail

## Deviations from Plan

None - plan executed exactly as written.

The acceptance criteria `grep -c "^import re"` outputs 2 (not 1) because `^import re` also matches `import requests` — this is a quirk in the grep pattern. `import re` is present at line 3 of `query.py`; the requirement is satisfied.

## Issues Encountered

- The plan's acceptance criteria states `grep -c "def test_" tests/test_chat_chips.py` outputs `9`, but the plan body lists 10 test functions (including `test_parse_chips_empty_string_item`). All 10 functions from the plan body were implemented. The discrepancy is in the plan spec itself.

## Known Stubs

None.

## Threat Flags

No new security surface introduced. `_parse_chips()` treats LLM output as untrusted text: all parsing via `json.loads()` in `try/except`, no `eval()` or `exec()`, chip content is user-facing strings only (T-05-01 mitigated as planned).

## Self-Check

Files exist:
- `app/services/query.py` — FOUND
- `app/routes/chat.py` — FOUND
- `tests/test_chat_chips.py` — FOUND

Commits exist:
- `a3149f4` (RED test) — FOUND
- `1b8f213` (feat query.py) — FOUND
- `8d5d4f6` (feat chat.py + test_chat_chips.py) — FOUND

## Self-Check: PASSED

## Next Phase Readiness

- `POST /chat` response now includes `chips: ["Q1", "Q2", "Q3"]` on success or `chips: []` on failure
- Widget JS (Plan 02) can read `chips` from response and render chip buttons
- No blockers

---
*Phase: 05-chat-widget*
*Completed: 2026-05-10*
