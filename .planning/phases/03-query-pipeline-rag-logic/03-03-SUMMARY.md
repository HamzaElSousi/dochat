---
phase: 03-query-pipeline-rag-logic
plan: 03
subsystem: chat-route
tags: [flask, cors, blueprint, chat-endpoint, env-config, htaccess]
dependency_graph:
  requires: [03-02]
  provides: [POST /chat, CORS, chat-route]
  affects: [03-04, 03-05]
tech_stack:
  added: []
  patterns: [exact-string CORS allowlist, OPTIONS preflight, defensive 500 guard, module-level env-var config]
key_files:
  created: []
  modified:
    - app/routes/chat.py
    - .env.example
decisions:
  - "_ALLOWED_ORIGINS list computed at module import time — in CGI mode (fresh process per request) this re-reads env vars every request, which is correct"
  - "session_id = data.get('session_id') or None converts empty string to None, signaling new session to handle_chat()"
  - "CORS headers applied to all response paths (400, 500, 200) so browser can read error details from cross-origin widget"
  - "OPTIONS preflight returns 204 with CORS headers per D-08; no body needed"
  - "Route only handles POST and OPTIONS — Flask returns 405 automatically for GET and other methods"
metrics:
  duration_minutes: 6
  completed_date: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 3 Plan 03: Chat Route Summary

**One-liner:** Full POST /chat endpoint replacing Plan 01 stub — CORS allowlist via ALLOWED_ORIGINS, OPTIONS preflight, validation, handle_chat() delegation, and Phase 3 env var documentation in .env.example.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write full app/routes/chat.py (replaces Plan 01 stub) | d3d80da | app/routes/chat.py |
| 2 | Update .env.example with Phase 3 env vars and .htaccess note | 8a6769f | .env.example |

## What Was Built

**Task 1 — Full chat route (app/routes/chat.py):**

- **`_ALLOWED_ORIGINS`** — module-level list parsed from `ALLOWED_ORIGINS` env var at import time. Empty or missing var means no origins are allowed, which means no CORS headers are added (no wildcard fallback).
- **`_cors_headers(origin)`** — returns a dict of three CORS headers if origin is in the allowlist; empty dict otherwise. Uses exact string comparison — no wildcard, no prefix match (T-03-03-01).
- **`chat()` route** — handles both `POST` and `OPTIONS` on `/chat`:
  - OPTIONS preflight: returns `('', 204, cors)` immediately.
  - POST: validates `message` field (400 if missing/empty), extracts optional `session_id`, calls `handle_chat()`, returns D-06 JSON shape with CORS headers.
  - Defensive `except Exception` around `handle_chat()` returns `{"error": "Internal server error"}` 500 — no stack trace exposure (T-03-03-02).
- **No `@require_auth`** — public endpoint per D-04.
- CORS headers are applied to all response paths (400, 500, 200) so cross-origin widgets can read error details.

**Task 2 — .env.example Phase 3 block:**

New section appended after existing Phase 1/2 vars:
- `ALLOWED_ORIGINS=` — with example comment showing comma-separated format
- `FALLBACK_MESSAGE=` — with full default text
- `SIMILARITY_THRESHOLD=0.35` — with tuning guidance (D-11)
- `ASSISTANT_NAME=DocChat Assistant` — branding (D-15)
- `ASSISTANT_PERSONA=a helpful AI assistant` — branding (D-15)
- `.htaccess deployment note` — `RewriteRule ^chat/?$ /app.cgi/chat [QSA,L]` as a comment, documenting the manual server-side step required before the endpoint is reachable via the CGI handler (D-04)

## Verification Results

- `python3 -c "from app.routes.chat import chat_bp, chat, _cors_headers; print('OK')"` — OK
- `grep -c "require_auth" app/routes/chat.py` — 0 (public endpoint confirmed)
- `grep -c "ALLOWED_ORIGINS" .env.example` — 1
- `grep -c "SIMILARITY_THRESHOLD" .env.example` — 1
- `pytest tests/ -x -q` — 50 passed, 0 failed (no regressions)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The chat_bp stub from Plan 01 has been fully replaced. All QUERY requirements are now wired end-to-end: embed (Plan 01) → handle_chat (Plan 02) → HTTP route (this plan).

## Threat Surface Scan

New public inbound endpoint `POST /chat` introduced. This is the primary surface documented in the plan's threat model:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: public-endpoint | app/routes/chat.py | POST /chat is unauthenticated — any client can call it |

Mitigations already applied per threat model:
- **T-03-03-01** (Origin spoofing): exact string match in `_cors_headers()` — no wildcard, forge-able by non-browser clients but irrelevant for browser same-origin policy
- **T-03-03-02** (Stack trace disclosure): `except Exception` returns only `{"error": "Internal server error"}` — no traceback
- **T-03-03-03** (DoS via oversized body): accepted risk — Flask 16MB default limit applies; add explicit guard post-MVP if abuse observed
- **T-03-03-04** (session_id tampering): handled at service layer (parameterized query, unknown UUID creates new session harmlessly)

## Self-Check: PASSED

- app/routes/chat.py — `def chat():` present: FOUND
- app/routes/chat.py — `from ..services.query import handle_chat` present: FOUND
- app/routes/chat.py — `def _cors_headers(origin: str) -> dict:` present: FOUND
- app/routes/chat.py — `@chat_bp.route('/chat', methods=['POST', 'OPTIONS'])` present: FOUND
- app/routes/chat.py — `if request.method == 'OPTIONS':` present: FOUND
- app/routes/chat.py — no `@require_auth`: CONFIRMED (count=0)
- .env.example — `ALLOWED_ORIGINS=` present: FOUND
- .env.example — `FALLBACK_MESSAGE=` present: FOUND
- .env.example — `SIMILARITY_THRESHOLD=0.35` present: FOUND
- .env.example — `ASSISTANT_NAME=DocChat Assistant` present: FOUND
- .env.example — `ASSISTANT_PERSONA=a helpful AI assistant` present: FOUND
- .env.example — `RewriteRule ^chat` in comment: FOUND
- .env.example — `SECRET_KEY` still present: FOUND (original vars preserved)
- Commit d3d80da in git log: FOUND
- Commit 8a6769f in git log: FOUND
- `pytest tests/ -x -q` — 50 passed: CONFIRMED
