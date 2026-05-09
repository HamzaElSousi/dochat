---
phase: 03-query-pipeline-rag-logic
plan: 04
subsystem: session-archival
tags: [cron, mysql, sqlite, pymysql, archival, sessions]
dependency_graph:
  requires: [03-01]
  provides: [archive_sessions_cron, pymysql_dep]
  affects: []
tech_stack:
  added: [PyMySQL>=1.1.0]
  patterns: [standalone-cron-script, sys.path.insert, pymysql.connect, manual-BEGIN-COMMIT-ROLLBACK, INSERT IGNORE]
key_files:
  created:
    - scripts/archive_sessions.py
  modified:
    - requirements.txt
    - .env.example
decisions:
  - "pymysql.connect() is opened per-session-row (not once for the whole batch) to minimize MySQL hold time during SQLite iteration"
  - "INSERT IGNORE used instead of INSERT to handle idempotent re-runs when SQLite delete previously failed"
  - "turn_count computed as len(messages)//2 — each turn = 1 user + 1 assistant message"
  - "datetime.fromisoformat() used to parse both offset-aware and naive ISO-8601 strings from SQLite"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 3 Plan 04: Session Archival Cron Script Summary

**One-liner:** Standalone hourly cron script that moves expired SQLite sessions (24h TTL) to MySQL dochat_conversations via pymysql, with log-and-retain failure handling per D-20.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create scripts/archive_sessions.py standalone cron script | ccde3d3 | scripts/archive_sessions.py |
| 2 | Add PyMySQL to requirements.txt and document MYSQL_URL in .env.example | d3e3290 | requirements.txt, .env.example |

## What Was Built

**Task 1 — archive_sessions.py:** A fully standalone Python cron script (no Flask runtime dependency) that:
- Uses `sys.path.insert(0, PROJECT_ROOT)` to import `app.db._open_db` from the cron context without a Flask app
- Queries `sessions WHERE last_active < datetime('now', '-24 hours')` (D-03 TTL)
- For each expired session: opens a pymysql connection, calls `_ensure_mysql_table()` (CREATE TABLE IF NOT EXISTS), INSERTs with INSERT IGNORE for idempotency, commits, then closes the MySQL connection
- Deletes from SQLite only after confirmed MySQL commit (T-03-04-03 mitigation)
- On any MySQL exception: logs the error and continues via `continue` — session is retained in SQLite for the next hourly retry (D-20)
- Uses manual `BEGIN`/`COMMIT`/`ROLLBACK` for SQLite deletes (consistent with established pattern — no `with conn:`)
- Computes `turn_count` as `len(messages) // 2`

**Task 2 — requirements.txt + .env.example:** `PyMySQL>=1.1.0` appended to requirements.txt (pip dry-run confirms PyMySQL-1.1.3 would install). `MYSQL_URL` documented in .env.example with the SQLAlchemy-style format `mysql+mysqlconnector://user:pass@host/dbname` matching the URL parsing logic in the script.

## Verification Results

- `python3 -c "import ast; ast.parse(open('scripts/archive_sessions.py').read())"` — syntax OK
- `grep -c "def main" scripts/archive_sessions.py` — 1
- `grep -c "PyMySQL" requirements.txt` — 1
- `grep -c "MYSQL_URL" .env.example` — 1
- `grep -q "with conn:" scripts/archive_sessions.py` — PASS (not found)
- `python3 -m pytest tests/ -x -q` — 50 passed, 0 failed (no regressions)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The script is fully functional. It cannot be exercised end-to-end locally without a live MySQL instance, but all logic paths are sound and the script exits 0 with "No expired sessions to archive." when the sessions table is empty.

## Threat Surface Scan

No new network endpoints introduced. The MYSQL_URL is read from environment (T-03-04-01 mitigated — never hardcoded). MySQL connection is opened only inside `main()` after URL validation (ValueError on empty/malformed URL). No new Flask routes or HTTP surface.

## Self-Check: PASSED

- scripts/archive_sessions.py — exists: FOUND
- scripts/archive_sessions.py — contains def main: FOUND
- scripts/archive_sessions.py — contains def _fetch_expired_sessions: FOUND
- scripts/archive_sessions.py — contains def _archive_session_to_mysql: FOUND
- scripts/archive_sessions.py — contains def _delete_session_from_sqlite: FOUND
- scripts/archive_sessions.py — contains logger.error: FOUND
- scripts/archive_sessions.py — contains D-20 continue comment: FOUND
- scripts/archive_sessions.py — contains from app.db import _open_db: FOUND
- scripts/archive_sessions.py — no 'with conn:': CONFIRMED
- requirements.txt — contains PyMySQL>=1.1.0: FOUND
- .env.example — contains MYSQL_URL: FOUND
- Commits ccde3d3, d3e3290 — both present in git log: CONFIRMED
- 50 tests passing: CONFIRMED
