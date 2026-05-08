# Phase 1: Infrastructure & Deployment Validation - Research

**Researched:** 2026-05-08
**Domain:** SiteGround shared hosting / Phusion Passenger / Flask WSGI / sqlite-vec
**Confidence:** MEDIUM (core patterns verified; SiteGround-specific behaviours partially assumed due to no SSH access during research)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 1 produces the real project scaffold that Phases 2–6 build on — not a throwaway probe.
- **D-02:** Scaffold structure: `passenger_wsgi.py`, `app/__init__.py`, `app/db.py`, `requirements.txt`, `.env.example`, `storage/` reference.
- **D-03:** Public `GET /health` endpoint returning `{ "status", "sqlite_vec_version", "sqlite_vec_mode", "storage_path", "storage_writable" }`. No auth.
- **D-04:** Deploy via SSH + `git pull` from GitHub.
- **D-05:** App restart signal is `touch passenger_wsgi.py` (standard Passenger restart — also `touch tmp/restart.txt` is valid; see Pitfalls).
- **D-06:** sqlite-vec native preferred, auto-fall back to pure-Python mode if native `.so` fails.
- **D-07:** `/health` reports `"sqlite_vec_mode": "python-fallback"` and a warning if degraded.
- **D-08:** Phase complete when `https://staging.social-automate.com/health` returns passing JSON.
- **D-09:** App is root of `staging.social-automate.com` — no sub-path.
- **D-10:** Phase 1 stays on staging; prod promotion deferred.

### Claude's Discretion
- sqlite-vec WAL pragma / busy_timeout sequence — follow CLAUDE.md hard rules exactly.
- Python version via cPanel Python Selector — 3.11+ preferred.
- `.env.example` keys: at minimum `OPENROUTER_API_KEY`, `ADMIN_PASSWORD`, `SECRET_KEY`.

### Deferred Ideas (OUT OF SCOPE)
- Widget embedding on all staging pages + standalone `/dochat/` page — Phase 5.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Flask app runs on SiteGround via Passenger WSGI (`passenger_wsgi.py`, single-worker) | passenger_wsgi.py pattern, cPanel Python Selector setup, virtualenv activation |
| INFRA-02 | sqlite-vec initializes with WAL mode and 10s busy timeout at startup | WAL + busy_timeout pragma sequence; sqlite-vec load mechanism; fallback handling |
| INFRA-03 | All data files outside `public_html/` at `~/dochat/storage/` | Storage path pattern; os.path resolution from app code; permissions check |
| INFRA-04 | All secrets loaded from `.env`, never hardcoded | python-dotenv `load_dotenv()` placement in `passenger_wsgi.py`; `.env.example` keys |
</phase_requirements>

---

## Summary

Phase 1 establishes the deployment foundation on SiteGround shared hosting. The key challenge is the Passenger WSGI environment: unlike a VPS, shared hosting manages Python apps through cPanel's Python Selector, which creates a virtualenv at `~/virtualenv/<appname>/<version>/`, sets the application root to a folder under `$HOME`, and writes a `.htaccess` with `PassengerAppRoot` and `PassengerBaseURI` directives to wire the subdomain to the app. The `passenger_wsgi.py` file at the application root is the single entry point Passenger invokes — it must import the Flask app object as `application` and must call `load_dotenv()` before importing the app.

sqlite-vec is a compiled C extension loaded via `sqlite3.enable_load_extension()`. On SiteGround, extension loading availability is **unverified** and must be tested via SSH at execution time. The sqlite-vec PyPI package (v0.1.9) ships manylinux wheels so `pip install` in the cPanel virtualenv should succeed; however, whether the SQLite bundled in SiteGround's Python has extension loading compiled in is unknown. The fallback strategy (catch `AttributeError` / `OperationalError` on `enable_load_extension`) must be coded defensively and reported in `/health`.

WAL mode and busy_timeout are set via PRAGMA statements immediately after every connection is opened. WAL mode is persistent (stored in the DB file); busy_timeout is per-connection. The hard rule is 10 000 ms (10s).

**Primary recommendation:** Build the scaffold locally first; push to GitHub; SSH into SiteGround; activate the virtualenv and pip install; test `/health` over HTTPS. The single highest-risk unknown is whether `enable_load_extension` is available — the fallback path must work before the native path can be depended on.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP request handling | Passenger (app server) | Flask (WSGI app) | Passenger receives from nginx/Apache, forwards to WSGI callable |
| App bootstrap / secrets loading | passenger_wsgi.py | Flask factory | Dotenv must load before any Flask config reads env vars |
| Vector DB init (WAL + busy_timeout) | Flask app startup (db.py) | — | Called once at factory time; per-connection pragmas on all subsequent gets |
| File storage isolation | OS filesystem (~/dochat/storage/) | Flask config | Path resolved at startup; never web-accessible |
| Health reporting | Flask route (/health) | — | Aggregates state from db.py and storage checks |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | WSGI web framework | Locked decision — Passenger is WSGI; FastAPI disqualified |
| sqlite-vec | 0.1.9 | Vector search extension for SQLite | Locked decision — low RAM, no ChromaDB |
| python-dotenv | 1.2.2 | Load `.env` secrets into `os.environ` | Standard secret-loading for WSGI; dotenv files not auto-loaded by Passenger |

[VERIFIED: npm/PyPI registry — Flask 3.1.3, sqlite-vec 0.1.9, python-dotenv 1.2.2 confirmed current as of 2026-05-08]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Werkzeug | (Flask dep) | WSGI utilities, routing internals | Auto-installed with Flask |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite-vec 0.1.9 | pysqlite3-binary | Use pysqlite3-binary only if system SQLite < 3.41 AND extension loading blocked; adds complexity |
| python-dotenv | os.environ set in .htaccess | .htaccess SetEnv is less portable; dotenv is the standard pattern |

**Installation (inside cPanel virtualenv, after activation):**
```bash
pip install flask==3.1.3 sqlite-vec==0.1.9 python-dotenv==1.2.2
```

**Version verification:** Confirmed against PyPI registry on 2026-05-08.
[VERIFIED: npm/PyPI registry]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser/curl
    |
    | HTTPS
    v
SiteGround nginx/Apache
    |
    | (PassengerAppRoot / PassengerBaseURI in .htaccess)
    v
Phusion Passenger (mod_passenger)
    |
    | WSGI callable: application
    v
passenger_wsgi.py
    ├── load_dotenv("/home/<user>/dochat/.env")
    ├── sys.path.insert(0, os.path.dirname(__file__))
    └── from app import create_app; application = create_app()
                |
                v
        app/__init__.py  (Flask factory)
            ├── app = Flask(__name__)
            ├── app.config from os.environ
            ├── init_db(app)           <-- app/db.py
            └── register blueprint: health_bp
                    |
                    v
            GET /health
                ├── check sqlite_vec load (native vs fallback)
                ├── check storage_path exists + writable
                └── return JSON

        app/db.py  (called at factory time)
            ├── sqlite3.connect(STORAGE_PATH/dochat.db)
            ├── PRAGMA journal_mode=WAL
            ├── PRAGMA busy_timeout=10000
            └── sqlite_vec.load(conn)  [with fallback]

~/dochat/storage/          (outside public_html)
    ├── dochat.db
    └── uploads/           (Phase 2+)
```

### Recommended Project Structure

```
dochat/                         # Application root (cPanel Application root)
├── passenger_wsgi.py           # Passenger entry point — ONLY file in root
├── app/
│   ├── __init__.py             # Flask application factory (create_app)
│   ├── db.py                   # sqlite-vec init, WAL mode, busy_timeout
│   └── routes/
│       └── health.py           # GET /health blueprint
├── requirements.txt
├── .env.example                # Committed; no real secrets
├── .env                        # NOT committed; real secrets
└── tmp/                        # For Passenger restart.txt (optional)
    └── .gitkeep
```

Storage directory (outside web root, created at first boot or by setup task):
```
~/dochat/storage/
├── dochat.db
└── uploads/   (Phase 2)
```

### Pattern 1: passenger_wsgi.py — Flask Factory with dotenv

**What:** Entry point Passenger invokes. Must load secrets before importing Flask app.
**When to use:** Every cPanel/Passenger Flask deployment.

```python
# passenger_wsgi.py
import sys
import os

# Ensure the app directory is on the path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# Load .env BEFORE importing the Flask app so config reads env vars correctly
from dotenv import load_dotenv
load_dotenv(os.path.join(APP_DIR, '.env'))

from app import create_app
application = create_app()
```

[CITED: https://prettyprinted.com/tutorials/automatically_load_environment_variables_in_flask/ — load_dotenv must be called manually in WSGI context; Flask's built-in dotenv support only runs under `flask run`]
[ASSUMED: `os.path.abspath(__file__)` resolves correctly in Passenger environment — most cPanel deployments confirm this pattern]

### Pattern 2: Flask Application Factory (app/__init__.py)

**What:** Standard Flask factory. Creates app object, loads config, registers blueprints, inits DB.
**When to use:** Always — enables testability and clean separation.

```python
# app/__init__.py
import os
from flask import Flask
from .db import init_db
from .routes.health import health_bp

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')

    init_db(app)

    app.register_blueprint(health_bp)

    return app
```

[CITED: https://flask.palletsprojects.com/en/stable/patterns/appfactories/ — official Flask factory pattern]

### Pattern 3: sqlite-vec Initialization with WAL + Fallback (app/db.py)

**What:** Opens the DB, sets WAL mode + 10s busy_timeout, loads sqlite-vec (native then fallback).
**When to use:** Called once from create_app(); connection stored on app object for reuse.

```python
# app/db.py
import os
import sqlite3
import flask

def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")   # 10 seconds
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _load_sqlite_vec(conn: sqlite3.Connection) -> str:
    """
    Attempt to load the native sqlite-vec extension.
    Falls back to pure-Python mode if extension loading is unavailable.
    Returns 'native' or 'python-fallback'.
    """
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return "native"
    except (AttributeError, Exception):
        # AttributeError: enable_load_extension not available (SQLite compiled without it)
        # OperationalError: .so won't load on this platform
        # Fall through to pure-Python mode — sqlite_vec still usable without native ext
        # Note: pure-Python mode may be slower; flag in /health
        return "python-fallback"

def init_db(app: flask.Flask) -> None:
    storage_path = app.config['STORAGE_PATH']
    os.makedirs(storage_path, exist_ok=True)

    db_path = os.path.join(storage_path, 'dochat.db')
    conn = _open_db(db_path)
    mode = _load_sqlite_vec(conn)

    app.config['DB_CONN'] = conn
    app.config['SQLITE_VEC_MODE'] = mode
    app.config['DB_PATH'] = db_path
```

[CITED: https://alexgarcia.xyz/sqlite-vec/python.html — enable_load_extension + sqlite_vec.load() pattern]
[CITED: https://til.simonwillison.net/sqlite/enabling-wal-mode — WAL mode is persistent (file-level), busy_timeout is per-connection]
[ASSUMED: pure-Python fallback is available within sqlite-vec 0.1.9's Python package when native load fails — the CONTEXT.md references it as a known mode, but sqlite-vec docs do not explicitly describe a separate "pure Python" code path. The fallback described in D-06/D-07 may mean "sqlite_vec still importable but not loaded as an extension"; verify at execution time]

### Pattern 4: GET /health Endpoint

```python
# app/routes/health.py
import os
from flask import Blueprint, jsonify, current_app
import sqlite_vec

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health():
    app = current_app
    mode = app.config.get('SQLITE_VEC_MODE', 'unknown')
    storage_path = app.config.get('STORAGE_PATH', '')

    # Verify storage is writable
    storage_ok = False
    try:
        test_file = os.path.join(storage_path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        storage_ok = True
    except OSError:
        storage_ok = False

    # Get sqlite_vec version
    vec_version = 'unknown'
    try:
        conn = app.config.get('DB_CONN')
        if conn:
            row = conn.execute("SELECT vec_version()").fetchone()
            vec_version = row[0] if row else 'unavailable'
    except Exception:
        vec_version = 'unavailable'

    response = {
        "status": "ok" if (storage_ok and mode == "native") else "degraded",
        "sqlite_vec_version": vec_version,
        "sqlite_vec_mode": mode,
        "storage_path": storage_path,
        "storage_writable": storage_ok,
    }

    if mode == "python-fallback":
        response["warning"] = "native extension unavailable — investigate SQLite version"

    status_code = 200 if storage_ok else 503
    return jsonify(response), status_code
```

[ASSUMED: `vec_version()` SQL function is available in sqlite-vec 0.1.9 — this is a standard function in the extension, but not explicitly verified against this version]

### Anti-Patterns to Avoid

- **Calling `app.run()` in passenger_wsgi.py**: Passenger does not use the Flask dev server; `app.run()` at module level will break the process.
- **Importing Flask app before load_dotenv()**: Config will read `None` from `os.environ` and silently use fallback defaults. Always `load_dotenv()` first in `passenger_wsgi.py`.
- **Storing DB files under public_html/**: Files there are web-accessible. All data goes to `~/dochat/storage/`.
- **Opening a new sqlite3.connect() per request without busy_timeout**: Each connection needs the PRAGMA on open; WAL is persistent but busy_timeout is per-connection.
- **Hardcoding `~/dochat/storage`** as a literal tilde string: Use `os.path.expanduser('~/dochat/storage')` — tilde is not expanded automatically by Python.
- **Assuming `touch passenger_wsgi.py` is the only restart method**: Both `touch passenger_wsgi.py` and `touch tmp/restart.txt` signal Passenger to restart; the former is simpler (no tmp/ directory needed) [ASSUMED: SiteGround honours timestamp change on passenger_wsgi.py itself as the restart signal — some Passenger versions require tmp/restart.txt instead; verify at execution time].

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secret loading | Custom env parser | `python-dotenv` `load_dotenv()` | Handles quoting, comments, multi-line; widely tested |
| Extension load error handling | Silent catch-all | Explicit `AttributeError` + `Exception` separate catches | `AttributeError` = extension loading API not compiled in (different fix than `OperationalError` = .so not found) |
| Storage path resolution | Hardcoded absolute path | `os.path.expanduser('~/dochat/storage')` | Works regardless of username/UID on SiteGround |
| WSGI entry point | Custom dispatch logic | Flask app object as `application` directly | Flask's `Flask` instance IS a valid WSGI callable |

**Key insight:** The shared hosting environment is fragile — rely on the simplest, most standard patterns so that Passenger has nothing unexpected to choke on.

---

## Common Pitfalls

### Pitfall 1: SQLite extension loading disabled at compile time
**What goes wrong:** `conn.enable_load_extension(True)` raises `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'` — the Python sqlite3 module was compiled without `SQLITE_ENABLE_LOAD_EXTENSION`.
**Why it happens:** CPython distributions on CloudLinux/shared hosting sometimes build sqlite3 without extension loading for security hardening. SiteGround's status is unverified.
**How to avoid:** Always wrap `enable_load_extension` in a try/except and fall back to sqlite-vec's pure-Python mode (D-06 / D-07 locked decision). Log the mode in `/health`.
**Warning signs:** `AttributeError` in app logs on first startup; `/health` returns `"sqlite_vec_mode": "python-fallback"`.

### Pitfall 2: Environment variables not available at Flask config time
**What goes wrong:** `os.environ['SECRET_KEY']` raises `KeyError` because `load_dotenv()` was called after `from app import create_app`.
**Why it happens:** Passenger imports modules top-to-bottom; if Flask's `create_app()` runs before `load_dotenv()`, the env is empty.
**How to avoid:** Call `load_dotenv(os.path.join(APP_DIR, '.env'))` as the FIRST substantive statement in `passenger_wsgi.py`, before any app imports.
**Warning signs:** HTTP 500 on all requests with `KeyError` in error log.

### Pitfall 3: Incorrect Application Root in cPanel Python Selector
**What goes wrong:** cPanel creates the virtualenv but Passenger cannot find `passenger_wsgi.py`, returning a 500 with "No such file".
**Why it happens:** The "Application root" field in Python Selector is relative to `$HOME`. If you enter `dochat` but the files are at `~/dochat/` — this should match, but a mismatch causes the 500.
**How to avoid:** After creating the app in cPanel, SSH in and verify the directory structure matches what cPanel created. The virtualenv lives at `~/virtualenv/dochat/<version>/`.
**Warning signs:** HTTP 500 immediately on first request; Passenger error log mentions missing `passenger_wsgi.py`.

### Pitfall 4: WAL mode .shm/.wal files appearing in wrong location
**What goes wrong:** sqlite-vec writes `.db-shm` and `.db-wal` companion files next to the `.db` file. If the DB is in `public_html/`, these files are web-accessible.
**Why it happens:** WAL mode always creates these two companion files in the same directory as the database.
**How to avoid:** Confirmed by hard rule — DB lives at `~/dochat/storage/dochat.db`, never under `public_html/`.
**Warning signs:** Seeing `.db-shm` and `.db-wal` requests in the web server access log.

### Pitfall 5: Passenger restart not taking effect
**What goes wrong:** Code change deployed via `git pull` but old code still runs.
**Why it happens:** Passenger caches the process; it only restarts when it detects a change in the restart signal file.
**How to avoid:** After every `git pull`, run `touch passenger_wsgi.py` (or `touch tmp/restart.txt`). Both update a file timestamp that Passenger monitors.
**Warning signs:** `git pull` succeeds but `/health` still returns old version info.

### Pitfall 6: Tilde not expanded in storage path
**What goes wrong:** `~/dochat/storage` passed as a string literal to `os.makedirs()` creates a literal directory named `~` in the current working directory.
**Why it happens:** Python does not expand `~` unless you call `os.path.expanduser()`.
**How to avoid:** Always use `os.path.expanduser('~/dochat/storage')` or build the path from `os.environ['HOME']`.
**Warning signs:** Directory `~/dochat/storage` doesn't exist but a literal `~` directory appears in the project root.

### Pitfall 7: SQLite version < 3.41 on SiteGround
**What goes wrong:** sqlite-vec documentation states full feature support requires SQLite >= 3.41. Older versions may have degraded behaviour (certain queries return wrong results silently).
**Why it happens:** SiteGround's system SQLite may be behind the Python virtualenv's bundled version.
**How to avoid:** At execution time, SSH in and run: `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"`. If < 3.41, consider adding `pysqlite3-binary` to requirements.txt as a drop-in replacement.
**Warning signs:** Vector similarity queries returning unexpected results; `/health` reports `sqlite_vec_mode: native` but queries behave oddly.

---

## Code Examples

### WAL + busy_timeout pragma sequence (verified pattern)
```python
# Source: https://til.simonwillison.net/sqlite/enabling-wal-mode
# Source: SQLite PRAGMA docs https://www.sqlite.org/pragma.html
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")       # persistent — only needed on DB creation
conn.execute("PRAGMA busy_timeout=10000;")     # 10 000 ms = 10 s, per-connection
conn.execute("PRAGMA synchronous=NORMAL;")     # safe + faster under WAL
```

### sqlite-vec load with graceful fallback
```python
# Source: https://alexgarcia.xyz/sqlite-vec/python.html
import sqlite_vec

def load_vec(conn):
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return "native"
    except AttributeError:
        # sqlite3 compiled without extension loading support
        return "python-fallback"
    except Exception:
        # .so found but failed to load (SQLite version mismatch, etc.)
        return "python-fallback"
```

### load_dotenv in passenger_wsgi.py (verified placement)
```python
# Source: https://prettyprinted.com/tutorials/automatically_load_environment_variables_in_flask/
import sys, os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(APP_DIR, '.env'))   # explicit path = no working-dir surprises

from app import create_app
application = create_app()
```

### Storage path expansion
```python
# Python built-in — os.path.expanduser handles ~ portably
storage = os.path.expanduser('~/dochat/storage')
os.makedirs(storage, exist_ok=True)   # idempotent; safe to call at every startup
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ChromaDB for vector search on shared hosting | sqlite-vec (single SQLite file, ~0 RAM overhead) | 2024 | No memory spike; fits shared hosting |
| `sentence-transformers` local embedding | OpenRouter API embedding | — | No PyTorch dependency; no OOM risk |
| Flask 2.x `@app.route` on module-level `app` | Flask 3.x application factory `create_app()` | Flask 2.0+ | Testability; Passenger compatibility |
| `touch tmp/restart.txt` (classic Passenger) | Both `touch passenger_wsgi.py` AND `touch tmp/restart.txt` work | Passenger 5+ | Either method valid; `touch passenger_wsgi.py` simpler |

**Deprecated/outdated:**
- `imp.load_source()` in passenger_wsgi.py: `imp` module is deprecated since Python 3.4; use direct import instead.
- `sys.executable` switching / `os.execl` to activate virtualenv: Modern cPanel Python Selector handles virtualenv activation automatically; manual `os.execl` trick is no longer needed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SiteGround's cPanel Python Selector virtualenv activates automatically (no manual `os.execl` / sys.path virtualenv tricks needed) | passenger_wsgi.py Pattern | passenger_wsgi.py will fail to find Flask; fix = add explicit site-packages path |
| A2 | `touch passenger_wsgi.py` triggers Passenger restart on SiteGround (timestamp change detected) | Pitfall 5 / Deploy | Old code runs after deploy; fix = always also `touch tmp/restart.txt` |
| A3 | sqlite-vec 0.1.9 has a usable "python-fallback" mode when extension loading is unavailable (D-06 / D-07) | db.py Pattern | `/health` reports fallback but vector ops may fail silently; need to verify actual fallback behaviour |
| A4 | SiteGround's Python 3.11/3.12/3.13 has `enable_load_extension` compiled in | Pitfall 1 | sqlite-vec runs in fallback only; acceptable per D-06 but important to detect |
| A5 | `vec_version()` SQL function is available in sqlite-vec 0.1.9 | /health endpoint pattern | `/health` reports 'unavailable' for version; non-blocking |
| A6 | SiteGround SSH port is 18765 | Deploy Workflow section | SSH connect fails; fix = check SiteGround dashboard for SSH credentials |

---

## Open Questions

1. **Does SiteGround's Python have `enable_load_extension` available?**
   - What we know: CloudLinux/shared hosts sometimes disable it at compile time for security
   - What's unclear: SiteGround's specific Python build configuration
   - Recommendation: First task after SSH access — `python3 -c "import sqlite3; c=sqlite3.connect(':memory:'); print(hasattr(c,'enable_load_extension'))"`

2. **What Python versions does SiteGround offer in cPanel Python Selector?**
   - What we know: SiteGround KB references Python 3.13.2; 3.11 and 3.12 likely available given standard CloudLinux selector
   - What's unclear: Exact list; whether 3.11 is selectable
   - Recommendation: Check cPanel Python Selector dropdown during setup; 3.11 preferred (stable LTS)

3. **Is sqlite-vec's "python-fallback" a meaningful fallback or a silent no-op?**
   - What we know: D-06/D-07 specify this mode; sqlite-vec GitHub shows no explicit pure-Python fallback in docs
   - What's unclear: Whether the Python package includes a fallback implementation or whether "fallback" means "the import works but vec0 virtual tables don't"
   - Recommendation: Test this locally first — try `import sqlite_vec` without calling `enable_load_extension`; see if `vec0` table creation succeeds

4. **Exact restart mechanism on SiteGround's Passenger**
   - What we know: Standard Passenger supports both `tmp/restart.txt` and file timestamp changes; cPanel docs mention `restart.txt`
   - What's unclear: Whether SiteGround's specific Passenger config monitors `passenger_wsgi.py` timestamp or only `tmp/restart.txt`
   - Recommendation: Use `touch tmp/restart.txt` as the primary restart method (create `tmp/` directory in scaffold); `touch passenger_wsgi.py` as secondary

---

## Environment Availability

> Phase requires SSH access to SiteGround and the ability to run Python in a virtualenv.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SiteGround SSH access | All deploy tasks | [ASSUMED] ✓ | Port 18765 | — |
| cPanel Python Selector | INFRA-01 | [ASSUMED] ✓ | Supported on all SiteGround shared plans | — |
| Python 3.11+ | INFRA-01 | [ASSUMED] ✓ | 3.13.2 confirmed; 3.11 likely available | Use 3.13 if 3.11 unavailable |
| Passenger WSGI | INFRA-01 | [ASSUMED] ✓ | Bundled with cPanel CloudLinux | — |
| SQLite with extension loading | INFRA-02 | [UNKNOWN] ✗/✓ | Unknown on SiteGround | Fall back to python-fallback mode (D-06) |
| GitHub SSH key on SiteGround | INFRA-01 deploy | Not yet configured | — | HTTPS git clone (no SSH key needed) |

**Missing dependencies with no fallback:**
- None that block Phase 1. The sqlite extension loading uncertainty has a coded fallback (D-06).

**Missing dependencies with fallback:**
- SQLite extension loading: fallback to sqlite-vec python mode (D-06/D-07).
- GitHub SSH key: use HTTPS clone instead.

[ASSUMED: all SiteGround availability items — must be verified during execution via SSH]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (standard Python testing) |
| Config file | None yet — Wave 0 creates `pytest.ini` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Flask app responds to GET /health | smoke (local) | `pytest tests/test_health.py -x` | ❌ Wave 0 |
| INFRA-02 | sqlite-vec loads; WAL + busy_timeout set | unit | `pytest tests/test_db.py::test_db_init -x` | ❌ Wave 0 |
| INFRA-02 | Test vector insert and retrieval succeeds | unit | `pytest tests/test_db.py::test_vec_round_trip -x` | ❌ Wave 0 |
| INFRA-03 | Storage path is outside public_html; writable | unit | `pytest tests/test_db.py::test_storage_path -x` | ❌ Wave 0 |
| INFRA-04 | Secrets loaded from .env; absent from source | unit | `pytest tests/test_config.py::test_secrets_from_env -x` | ❌ Wave 0 |

**Live validation (not automated):**
- INFRA-01 live: `curl https://staging.social-automate.com/health` returns 200 JSON (D-08)

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green + live `/health` endpoint returning passing JSON

### Wave 0 Gaps
- [ ] `tests/__init__.py`
- [ ] `tests/test_health.py` — covers INFRA-01
- [ ] `tests/test_db.py` — covers INFRA-02, INFRA-03
- [ ] `tests/test_config.py` — covers INFRA-04
- [ ] `pytest.ini` — configure testpaths, markers
- [ ] Framework install: `pip install pytest` in local venv

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not in Phase 1 (auth is Phase 4) |
| V3 Session Management | No | Not in Phase 1 |
| V4 Access Control | No | /health is intentionally public (D-03) |
| V5 Input Validation | No | No user input in Phase 1 |
| V6 Cryptography | Partial | SECRET_KEY from .env — never hardcoded (INFRA-04) |
| V7 Error Handling | Yes | Do not expose stack traces in /health JSON |
| V14 Configuration | Yes | Secrets in .env only; .env never committed; .env.example committed |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret in source code / git | Information Disclosure | .gitignore `.env`; committed `.env.example` only |
| DB file web-accessible | Information Disclosure | Store at `~/dochat/storage/`, never `public_html/` |
| Stack trace in /health response | Information Disclosure | Catch all exceptions in /health; return generic error message |
| .db-shm/.db-wal under public_html | Information Disclosure | Covered by storage path rule above |

---

## Sources

### Primary (HIGH confidence)
- [flask.palletsprojects.com/en/stable/patterns/appfactories/](https://flask.palletsprojects.com/en/stable/patterns/appfactories/) — Flask factory pattern
- [alexgarcia.xyz/sqlite-vec/python.html](https://alexgarcia.xyz/sqlite-vec/python.html) — sqlite-vec Python load mechanism
- [til.simonwillison.net/sqlite/enabling-wal-mode](https://til.simonwillison.net/sqlite/enabling-wal-mode) — WAL mode enabling, persistence
- PyPI registry (verified 2026-05-08) — Flask 3.1.3, sqlite-vec 0.1.9, python-dotenv 1.2.2

### Secondary (MEDIUM confidence)
- [prettyprinted.com/tutorials/automatically_load_environment_variables_in_flask/](https://prettyprinted.com/tutorials/automatically_load_environment_variables_in_flask/) — load_dotenv must be called manually in WSGI context
- [sushilparajuli.com/installing-a-python-app-on-shared-hosting-with-cpanel/](https://sushilparajuli.com/installing-a-python-app-on-shared-hosting-with-cpanel/) — cPanel passenger_wsgi.py structure
- [zaiste.net/posts/python-apps-phussion-passenger-flask/](https://zaiste.net/posts/python-apps-phussion-passenger-flask/) — Passenger Flask virtualenv pattern
- [jvmhost.com/articles/passenger-python-django-cpanel/](https://www.jvmhost.com/articles/passenger-python-django-cpanel/) — Passenger WSGI directory layout

### Tertiary (LOW confidence — verify at execution time)
- [siteground.com/kb/see-available-python-modules/](https://www.siteground.com/kb/see-available-python-modules/) — SiteGround Python 3.13.2 mentioned; other versions unconfirmed
- CloudLinux forum — selectorctl restart command; `touch passenger_wsgi.py` restart behaviour unconfirmed on SiteGround specifically

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via PyPI registry
- Architecture / passenger_wsgi.py pattern: MEDIUM — cross-verified across multiple cPanel hosts; SiteGround-specific behaviour partially assumed
- sqlite-vec WAL setup: HIGH — official docs + Simon Willison's verified TIL
- sqlite-vec fallback mode: LOW — referenced in CONTEXT.md decisions but not documented in sqlite-vec official docs; must verify at execution
- Pitfalls: MEDIUM — sourced from multiple hosting guides + sqlite.org documentation

**Research date:** 2026-05-08
**Valid until:** 2026-06-07 (sqlite-vec is pre-v1 and releases frequently; re-verify version before install)
