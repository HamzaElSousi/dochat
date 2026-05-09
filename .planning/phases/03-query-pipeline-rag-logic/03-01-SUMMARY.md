---
phase: 03-query-pipeline-rag-logic
plan: 01
subsystem: query-foundation
tags: [db, embeddings, blueprint, sessions, sqlite, flask]
dependency_graph:
  requires: [02-02]
  provides: [sessions-table, embed_query, chat_bp-stub]
  affects: [03-02, 03-03]
tech_stack:
  added: []
  patterns: [CREATE TABLE IF NOT EXISTS idempotent DDL, embed_query thin wrapper, Blueprint stub]
key_files:
  created:
    - app/routes/chat.py
  modified:
    - app/db.py
    - app/ingest/embedder.py
    - app/__init__.py
decisions:
  - "sessions table uses manual conn.commit() (same idiom as init_document_tables — avoids sqlite3 context manager conflict)"
  - "chat_bp stub created now so Plan 01 tests can import app without error; Plan 03 replaces it with full implementation"
  - "embed_query() is a thin one-liner delegating to embed_chunks([text])[0] — zero new dependencies"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-09"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 4
---

# Phase 3 Plan 01: Query Pipeline Foundation Summary

**One-liner:** Sessions table DDL, embed_query single-query wrapper, and chat_bp Blueprint stub wired into Flask factory — zero new dependencies, all 50 tests passing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add init_session_tables() to app/db.py | 5890317 | app/db.py |
| 2 | Add embed_query() wrapper to app/ingest/embedder.py | 0732f02 | app/ingest/embedder.py |
| 3 | Wire chat_bp import into app/__init__.py | f698497 | app/__init__.py, app/routes/chat.py |

## What Was Built

**Task 1 — Sessions table:** `init_session_tables(conn)` creates a `sessions` table with 4 columns (session_id TEXT PRIMARY KEY, messages TEXT NOT NULL, created_at TEXT NOT NULL, last_active TEXT NOT NULL). It follows the identical DDL pattern as `init_document_tables()` — CREATE TABLE IF NOT EXISTS + manual conn.commit(). `init_db()` now calls it after document table init so the table exists on every app startup.

**Task 2 — embed_query wrapper:** A single-function addition to embedder.py that delegates to `embed_chunks([text])[0]`. Inherits ValueError on empty input and requests.HTTPError on API failure from embed_chunks(). No new imports, no new dependencies.

**Task 3 — chat_bp Blueprint stub:** `app/routes/chat.py` created as a minimal stub (Blueprint declaration only). `app/__init__.py` updated to import and register `chat_bp` following the exact same pattern as `ingest_bp`. Plan 03 will replace the stub with the full /api/chat endpoint implementation.

## Verification Results

- `pytest tests/ -x -q` — 50 passed, 0 failed (no regressions)
- `sessions` table confirmed in sqlite_master after `create_app()`
- `embed_query` importable and contains `embed_chunks([text])[0]`
- `chat_bp` imported and registered in Flask factory

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| chat_bp = Blueprint('chat', __name__) | app/routes/chat.py | 4 | Intentional Plan 01 stub; Plan 03 provides the full /api/chat implementation |

## Threat Surface Scan

No new network endpoints introduced in this plan. The sessions table DDL runs at startup with no user input — low risk. embed_query inherits the existing ValueError guard from embed_chunks().

## Self-Check: PASSED

- app/db.py — contains init_session_tables + call in init_db: FOUND
- app/ingest/embedder.py — contains embed_query: FOUND
- app/__init__.py — contains chat_bp import and register: FOUND
- app/routes/chat.py — stub created: FOUND
- Commits 5890317, 0732f02, f698497 — all present in git log
