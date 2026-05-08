---
phase: 01-infrastructure-deployment-validation
plan: "01"
subsystem: infrastructure
tags: [flask, sqlite-vec, passenger-wsgi, pytest, scaffold]

dependency_graph:
  requires: []
  provides:
    - passenger_wsgi_entry_point
    - flask_application_factory
    - sqlite_vec_db_init
    - health_endpoint
    - pytest_suite
  affects: []

tech_stack:
  added:
    - flask==3.1.3
    - sqlite-vec==0.1.9
    - python-dotenv==1.2.2
    - pytest==8.3.5
  patterns:
    - Flask application factory (create_app)
    - Passenger WSGI entry point with load_dotenv-first ordering
    - sqlite-vec WAL+busy_timeout initialization with AttributeError/Exception dual-except fallback
    - Storage path resolution via os.path.expanduser (no literal tilde)
    - /health endpoint returning 5-key JSON with degraded/503 on storage failure

key_files:
  created:
    - passenger_wsgi.py
    - app/__init__.py
    - app/db.py
    - app/routes/__init__.py
    - app/routes/health.py
    - requirements.txt
    - .env.example
    - .gitignore
    - tmp/.gitkeep
    - pytest.ini
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_health.py
    - tests/test_db.py
    - tests/test_config.py
  modified: []

decisions:
  - "sqlite-vec native extension loaded via enable_load_extension; fallback to python-fallback mode on AttributeError or Exception — both return gracefully"
  - "load_dotenv called before Flask app import in passenger_wsgi.py — prevents SECRET_KEY KeyError on Passenger startup"
  - "STORAGE_PATH resolved via os.path.expanduser to avoid literal tilde directory creation bug"
  - "conftest.py patches app_module.os.path.expanduser directly (not via dotted string) due to Python monkeypatch limitation with __init__ module names"
  - "vec0 insert uses struct.pack serialized float32 bytes — sqlite-vec 0.1.9 requires binary format, not Python list"

metrics:
  duration: "~25 minutes"
  completed: "2026-05-08"
  tasks_completed: 2
  tests_written: 17
  tests_passing: 17
  files_created: 15
---

# Phase 1 Plan 01: Flask Scaffold and pytest Suite Summary

Flask scaffold with Passenger WSGI entry point, sqlite-vec WAL initialization with dual-except fallback, /health endpoint, and full 17-test pytest suite — all passing green locally.

## What Was Built

### Task 1: Project Scaffold

All scaffold files created exactly per plan specifications:

- **passenger_wsgi.py** — Passenger WSGI entry point. `load_dotenv()` is called before `from app import create_app` (line 10 vs line 12). No `app.run()` call. Sets `sys.path` from `os.path.abspath(__file__)`.

- **app/__init__.py** — Flask application factory. `create_app()` reads `SECRET_KEY` from `os.environ` (raises `KeyError` if missing). `STORAGE_PATH` resolved via `os.path.expanduser('~/dochat/storage')`.

- **app/db.py** — sqlite-vec initialization. `_open_db()` sets `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=10000`, `PRAGMA synchronous=NORMAL` on every connection. `_load_sqlite_vec()` uses two separate `except` clauses: `AttributeError` (extension loading not compiled in) and `Exception` (load failure) — both return `'python-fallback'`. Returns `'native'` on success.

- **app/routes/health.py** — GET /health blueprint. Returns 5-key JSON: `status`, `sqlite_vec_version`, `sqlite_vec_mode`, `storage_path`, `storage_writable`. Returns 503 when storage not writable. Never exposes stack traces.

- **requirements.txt** — Pinned: `flask==3.1.3`, `sqlite-vec==0.1.9`, `python-dotenv==1.2.2`, `pytest==8.3.5`.

- **.env.example** — Committed placeholder with `OPENROUTER_API_KEY`, `ADMIN_PASSWORD`, `SECRET_KEY`.

- **.gitignore** — `.env` on exact line; `__pycache__/`, `venv/`, `*.db-shm`, `*.db-wal`, `storage/`.

- **tmp/.gitkeep** — Creates `tmp/` directory for `touch tmp/restart.txt` Passenger restart signal.

### Task 2: pytest Test Suite

17 tests across 3 modules, all passing:

| Test | Coverage | Result |
|------|----------|--------|
| test_secret_key_from_env | INFRA-04: SECRET_KEY from env | PASSED |
| test_missing_secret_key_raises | INFRA-04: KeyError when missing | PASSED |
| test_env_file_not_committed | INFRA-04: .env in .gitignore | PASSED |
| test_no_hardcoded_secrets_in_source | INFRA-04: no literal secrets in .py files | PASSED |
| test_db_init_sets_config_keys | INFRA-02: DB_CONN, SQLITE_VEC_MODE, DB_PATH set | PASSED |
| test_db_wal_mode | INFRA-02: PRAGMA journal_mode = wal | PASSED |
| test_db_busy_timeout | INFRA-02: PRAGMA busy_timeout = 10000 | PASSED |
| test_sqlite_vec_mode_valid | INFRA-02: mode is native or python-fallback | PASSED |
| test_storage_path_not_under_public_html | INFRA-03: no public_html in path | PASSED |
| test_storage_path_is_absolute | INFRA-03: absolute path, no tilde | PASSED |
| test_storage_dir_created | INFRA-03: directory exists after startup | PASSED |
| test_vec_round_trip | INFRA-02: vec0 insert + retrieval (skipped if fallback) | PASSED (native) |
| test_health_returns_json | INFRA-01: Content-Type application/json | PASSED |
| test_health_keys | INFRA-01: all 5 keys present | PASSED |
| test_health_ok_when_storage_writable | INFRA-01: storage_writable=True | PASSED |
| test_health_status_code | INFRA-01: 200 or 503 | PASSED |
| test_health_no_stack_trace | V7 error handling: no Traceback in response | PASSED |

**Local sqlite-vec mode: native** (Python 3.10 on WSL2 has `enable_load_extension` compiled in)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed monkeypatch target for os.path.expanduser in conftest**
- **Found during:** Task 2 — first pytest run
- **Issue:** Plan specified `monkeypatch.setattr('app.__init__.os.path.expanduser', ...)` but pytest's `monkeypatch.setattr` cannot resolve `app.__init__.os` as a dotted module name — `'app.__init__'` is not treated as a subpackage.
- **Fix:** Changed to `monkeypatch.setattr(app_module.os.path, 'expanduser', ...)` — patches the `os.path` object that was imported into the `app` module directly, which is the correct approach for patching already-imported references.
- **Files modified:** `tests/conftest.py`

**2. [Rule 1 - Bug] Fixed vec0 INSERT syntax and binary serialization**
- **Found during:** Task 2 — `test_vec_round_trip`
- **Issue 1:** `INSERT INTO _test_vec VALUES (?)` failed with "table has 2 columns but 1 values" — vec0 has an implicit rowid column; must use explicit column name.
- **Issue 2:** Passing a Python list `[0.1, 0.2, 0.3, 0.4]` failed with `InterfaceError: Error binding parameter 0` — sqlite-vec 0.1.9 requires float32 vectors as raw binary bytes, not Python lists.
- **Fix:** Changed to `INSERT INTO _test_vec(embedding) VALUES (?)` with `struct.pack('4f', *vector)` to produce the required binary format.
- **Files modified:** `tests/test_db.py`

## Known Stubs

None — all implemented functionality is fully wired. The /health endpoint returns real data from the DB connection and storage check. No placeholder values flow to any output.

## Threat Flags

No new threat surface beyond what the plan's threat model documents. All T-01-01 through T-01-05 mitigations are implemented:
- `.env` excluded from git (T-01-01)
- `/health` catches all exceptions and returns generic strings (T-01-02)
- STORAGE_PATH resolved via expanduser outside public_html (T-01-03)
- load_dotenv before app import (T-01-05)

## Self-Check

Files exist:
- passenger_wsgi.py: FOUND
- app/__init__.py: FOUND
- app/db.py: FOUND
- app/routes/__init__.py: FOUND
- app/routes/health.py: FOUND
- requirements.txt: FOUND
- .env.example: FOUND
- .gitignore: FOUND
- tmp/.gitkeep: FOUND
- pytest.ini: FOUND
- tests/__init__.py: FOUND
- tests/conftest.py: FOUND
- tests/test_health.py: FOUND
- tests/test_db.py: FOUND
- tests/test_config.py: FOUND

pytest result: 17 passed in 1.46s (exit code 0)

## Self-Check: PASSED
