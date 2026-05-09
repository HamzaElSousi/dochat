# Phase 3: Query Pipeline & RAG Logic - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 6 new/modified files
**Analogs found:** 5 / 6 (1 file has no direct analog — scripts/archive_sessions.py)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/routes/chat.py` | route/controller | request-response | `app/routes/ingest.py` | role-match (no auth, different shape) |
| `app/services/query.py` | service | request-response + CRUD | `app/services/ingestion.py` | role-match (same transaction pattern) |
| `app/ingest/embedder.py` | utility | transform | `app/ingest/embedder.py` (self) | exact (add thin wrapper) |
| `app/db.py` | config/model | CRUD | `app/db.py` (self) | exact (add table init + helpers) |
| `scripts/archive_sessions.py` | utility/cron | batch + CRUD | none | no analog |
| `app/__init__.py` | config | — | `app/__init__.py` (self) | exact (add one import + register_blueprint) |

---

## Pattern Assignments

### `app/routes/chat.py` (route, request-response)

**Analog:** `app/routes/ingest.py`

**Imports pattern** (`app/routes/ingest.py` lines 1–7):
```python
import os
from flask import Blueprint, request, jsonify, current_app
# NOTE: no require_auth import — /chat is public (D-04)
from ..services.query import handle_chat   # replaces ingest_file/ingest_url
```

**Blueprint declaration pattern** (`app/routes/ingest.py` line 8):
```python
chat_bp = Blueprint('chat', __name__)
```

**CORS pattern** (new, no analog — implement from D-08):
```python
# CORS: read ALLOWED_ORIGINS env var (comma-separated) at request time.
# Only inject Access-Control-Allow-Origin when the request Origin header
# matches a listed domain. Add to both OPTIONS preflight and POST response.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get('ALLOWED_ORIGINS', '').split(',') if o.strip()]

def _cors_headers(origin: str) -> dict:
    if origin in ALLOWED_ORIGINS:
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    return {}
```

**Route handler pattern** (`app/routes/ingest.py` lines 68–91 — url_ingest is closest shape):
```python
@chat_bp.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    origin = request.headers.get('Origin', '')
    cors = _cors_headers(origin)

    # Preflight
    if request.method == 'OPTIONS':
        return ('', 204, cors)

    conn = current_app.config.get('DB_CONN')

    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        resp = jsonify({"error": "Missing required field: 'message'"})
        resp.headers.update(cors)
        return resp, 400

    session_id = data.get('session_id') or None  # None triggers new session creation

    try:
        result = handle_chat(conn, message, session_id)
        resp = jsonify(result)
        resp.headers.update(cors)
        return resp, 200
    except Exception:
        # Never expose stack traces to the client
        resp = jsonify({"error": "Internal server error"})
        resp.headers.update(cors)
        return resp, 500
```

**Error handling pattern** (`app/routes/ingest.py` lines 57–65):
```python
    try:
        result = handle_chat(conn, message, session_id)
        resp = jsonify(result)
        resp.headers.update(cors)
        return resp, 200
    except Exception:
        # Never expose stack traces to the client (T-02-06 convention)
        resp = jsonify({"error": "Internal server error"})
        resp.headers.update(cors)
        return resp, 500
```

---

### `app/services/query.py` (service, request-response + CRUD)

**Analog:** `app/services/ingestion.py`

**Imports pattern** (`app/services/ingestion.py` lines 1–12):
```python
import os
import uuid
import struct
import sqlite3
from datetime import datetime, timezone

from app.ingest.embedder import embed_query   # new thin wrapper (see embedder section)
from app.services.ingestion import serialize_f32  # reuse existing packer
```

**`serialize_f32` reuse** (`app/services/ingestion.py` lines 14–16):
```python
# Do NOT redefine — import directly from app.services.ingestion:
from app.services.ingestion import serialize_f32
```

**Transaction pattern — manual BEGIN/COMMIT/ROLLBACK** (`app/services/ingestion.py` lines 101–108 and 169–176):
```python
# Guard against leftover implicit transaction (CR-04 pattern — copy verbatim)
if conn.in_transaction:
    conn.execute("ROLLBACK")
conn.execute("BEGIN")

try:
    # ... DML statements ...
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```

**Config/env access pattern** (`app/services/ingestion.py` — os.environ.get):
```python
# All config from env vars — never hardcode (established project rule)
SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.35'))
FALLBACK_MESSAGE     = os.environ.get('FALLBACK_MESSAGE', "I don't have information on that yet. Feel free to ask something else.")
PRIMARY_MODEL        = 'google/gemma-3-27b-it:free'
FALLBACK_MODEL       = 'qwen/qwen3-next-80b-a3b-instruct:free'
LLM_TIMEOUT          = 30   # seconds (D-13)
TOP_K                = 4    # QUERY-01
MAX_HISTORY_TURNS    = 10   # QUERY-04
```

**LLM call pattern** (new, follows embedder.py `requests.post` shape at lines 29–41):
```python
import requests

def _call_llm(messages: list[dict], model: str) -> str:
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

**Primary-then-fallback retry pattern** (D-13 and D-14):
```python
def _call_llm_with_retry(messages: list[dict]) -> str | None:
    """Try primary model; on 429/timeout retry with fallback. Return None if both fail."""
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            return _call_llm(messages, model)
        except (requests.exceptions.Timeout, requests.HTTPError):
            continue
    return None   # both failed — caller uses fallback message (D-14)
```

**Session CRUD pattern** (new — wraps `_open_db()` / sessions table added to db.py):
```python
def _load_session(conn: sqlite3.Connection, session_id: str) -> list[dict] | None:
    row = conn.execute(
        "SELECT messages FROM sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    if not row:
        return None
    import json
    return json.loads(row[0])

def _save_session(conn: sqlite3.Connection, session_id: str, messages: list[dict]) -> None:
    import json
    now_iso = datetime.now(timezone.utc).isoformat()
    if conn.in_transaction:
        conn.execute("ROLLBACK")
    conn.execute("BEGIN")
    try:
        conn.execute(
            """INSERT INTO sessions (session_id, messages, created_at, last_active)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE
               SET messages = excluded.messages,
                   last_active = excluded.last_active""",
            [session_id, json.dumps(messages), now_iso, now_iso]
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```

**Top-level `handle_chat` shape** (mirrors `ingest_file`/`ingest_url` single-function service API):
```python
def handle_chat(conn: sqlite3.Connection, message: str, session_id: str | None) -> dict:
    """Embed query → vector search → threshold gate → LLM → session save → return dict.

    Returns:
      {"answer": str, "session_id": str, "fallback": bool, "sources": list[dict]}
    Never raises to caller — all LLM/embed failures degrade to fallback message (D-14).
    """
```

---

### `app/ingest/embedder.py` — add `embed_query()` wrapper (modify existing)

**Analog:** `app/ingest/embedder.py` itself (lines 11–53)

**Wrapper to append at end of file** (Claude's Discretion — thin one-liner wrapper):
```python
def embed_query(text: str) -> list[float]:
    """Embed a single visitor query string. Thin wrapper around embed_chunks().

    Returns a 1536-dim float vector.
    Raises ValueError on empty input; raises requests.HTTPError on API failure.
    """
    return embed_chunks([text])[0]
```

This is the only change to this file. No other lines are modified.

---

### `app/db.py` — add `sessions` table init + session CRUD helpers (modify existing)

**Analog:** `app/db.py` itself (lines 46–82 — `init_document_tables`)

**New table init function to add after `init_document_tables`** (follows exact same DDL style):
```python
def init_session_tables(conn: sqlite3.Connection) -> None:
    """Create sessions table if it does not exist.

    session_id: UUID string (server-generated, D-02)
    messages:   JSON array of {"role": "user"|"assistant", "content": "..."} (D-01)
    last_active: ISO-8601 UTC — cron script uses this for 24h TTL expiry (D-03)
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            messages   TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_active TEXT NOT NULL
        )
    """)
    conn.commit()
```

**Call site in `init_db()`** (`app/db.py` lines 85–103 — add one line after `init_document_tables`):
```python
    init_document_tables(conn)
    init_session_tables(conn)   # <-- add this line
```

No other changes to `init_db()`.

---

### `scripts/archive_sessions.py` (standalone cron script, no analog)

**No direct analog exists.** This is the first standalone (non-Flask) script in the project. Use the following patterns drawn from existing project conventions:

**Env var access** — same as `app/ingest/embedder.py` lines 23:
```python
import os
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')  # illustrates pattern
MYSQL_URL          = os.environ.get('MYSQL_URL', '')
```

**SQLite open** — call `_open_db()` from `app/db.py` (lines 6–20). Script must resolve db_path the same way `init_db()` does:
```python
import sys, os
# Resolve project root so app package is importable from cron context
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.db import _open_db

STORAGE_PATH = os.path.expanduser('~/dochat/storage')
db_path      = os.path.join(STORAGE_PATH, 'dochat.db')
conn         = _open_db(db_path)
```

**Manual transaction** — same BEGIN/COMMIT/ROLLBACK as `app/services/ingestion.py` lines 101–176:
```python
if conn.in_transaction:
    conn.execute("ROLLBACK")
conn.execute("BEGIN")
try:
    # ... DELETE from sessions ...
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```

**MySQL archival pattern** (D-17 to D-20, new — use PyMySQL or mysql-connector):
```python
import json, pymysql   # or: import mysql.connector

def _archive_to_mysql(sessions: list[tuple]) -> None:
    """Write expired sessions to dochat_conversations. Leave in SQLite on failure (D-20)."""
    conn_my = pymysql.connect(
        host=..., user=..., password=..., database=...,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    # Parse MYSQL_URL for credentials — never hardcode
    ...
    with conn_my.cursor() as cur:
        for session_id, messages_json, created_at, last_active in sessions:
            messages = json.loads(messages_json)
            cur.execute(
                """INSERT IGNORE INTO dochat_conversations
                   (session_id, messages, started_at, ended_at, turn_count)
                   VALUES (%s, %s, %s, %s, %s)""",
                (session_id, messages_json, created_at, last_active, len(messages) // 2)
            )
    conn_my.commit()
    conn_my.close()
```

**Logging pattern** (no existing logger — use stdlib `logging`):
```python
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# On MySQL failure: log + skip delete (D-20), never silently drop session
try:
    _archive_to_mysql(expired_rows)
    # Delete from SQLite only after successful MySQL write
    ...
except Exception as exc:
    logger.error("MySQL archival failed, sessions retained for next run: %s", exc)
```

**Script entry point pattern**:
```python
if __name__ == '__main__':
    main()
```

---

### `app/__init__.py` — register `chat_bp` (modify existing)

**Analog:** `app/__init__.py` itself (lines 1–20)

**Import line to add** (line 5 — after `from .routes.ingest import ingest_bp`):
```python
from .routes.chat import chat_bp
```

**Register line to add** (after `app.register_blueprint(ingest_bp)`):
```python
    app.register_blueprint(chat_bp)
```

No other changes. Final `create_app()` body:
```python
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')
    init_db(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(chat_bp)   # <-- new
    return app
```

---

## Shared Patterns

### Manual Transaction (BEGIN/COMMIT/ROLLBACK)
**Source:** `app/services/ingestion.py` lines 101–108, 169–176
**Apply to:** `app/services/query.py` (all session writes), `scripts/archive_sessions.py` (SQLite deletes)
```python
if conn.in_transaction:
    conn.execute("ROLLBACK")
conn.execute("BEGIN")
try:
    # ... DML ...
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```
Rule: NEVER use `with conn:` context manager. NEVER nest transactions.

### Env Var Access
**Source:** `app/ingest/embedder.py` line 23; `app/auth.py` line 17
**Apply to:** `app/routes/chat.py` (ALLOWED_ORIGINS), `app/services/query.py` (SIMILARITY_THRESHOLD, FALLBACK_MESSAGE, OPENROUTER_API_KEY, ASSISTANT_NAME, ASSISTANT_PERSONA), `scripts/archive_sessions.py` (MYSQL_URL)
```python
VALUE = os.environ.get('ENV_KEY', 'default_value')
```

### OpenRouter HTTP Call
**Source:** `app/ingest/embedder.py` lines 29–41
**Apply to:** `app/services/query.py` (`_call_llm`)
```python
response = requests.post(
    "https://openrouter.ai/api/v1/...",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={...},
    timeout=30,
)
response.raise_for_status()
```

### Config Access in Routes
**Source:** `app/routes/ingest.py` lines 40–41
**Apply to:** `app/routes/chat.py`
```python
conn = current_app.config.get('DB_CONN')
storage_path = current_app.config.get('STORAGE_PATH')
```

### Error Handling — Never Expose Tracebacks
**Source:** `app/routes/ingest.py` lines 63–65
**Apply to:** `app/routes/chat.py`
```python
    except Exception:
        # Never expose stack traces to the client (T-02-06)
        return jsonify({"error": "Internal server error ..."}), 500
```

### DDL Convention
**Source:** `app/db.py` lines 53–81
**Apply to:** `app/db.py` — new `init_session_tables()` function
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS table_name (
        col TYPE CONSTRAINT,
        ...
    )
""")
conn.commit()
```
Always use `CREATE TABLE IF NOT EXISTS`. Always call `conn.commit()` at the end of the init function.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `scripts/archive_sessions.py` | utility/cron | batch + CRUD | No standalone (non-Flask) scripts exist in the project yet. Pattern drawn from conventions in app/ source files. |

---

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/ingest/`, `app/db.py`, `app/__init__.py`, `app/auth.py`
**Files scanned:** 7
**Pattern extraction date:** 2026-05-09
