import os
import sqlite3
import flask


def _open_db(db_path: str) -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and 10s busy timeout.
    WAL is persistent (file-level). busy_timeout is per-connection — set on EVERY open.
    """
    # check_same_thread=False: this deployment uses CGI via Passenger, where each
    # HTTP request spawns a fresh OS process. There is never more than one thread
    # sharing this connection, so the sqlite3 thread-safety check is intentionally
    # disabled. If the deployment model ever changes to a multi-threaded server
    # (e.g. Gunicorn with threads), this must be replaced with per-request
    # connections (Flask g) or a threading.Lock-protected pool.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  # 10 000 ms = 10 seconds
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _load_sqlite_vec(conn: sqlite3.Connection) -> str:
    """Load sqlite-vec native extension with graceful fallback.

    Two separate except clauses are intentional:
    - AttributeError: enable_load_extension not compiled into this Python's sqlite3
    - Exception: .so found but failed to load (SQLite version mismatch, platform issue)

    Returns 'native' or 'python-fallback'.
    """
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return "native"
    except AttributeError:
        # sqlite3 compiled without SQLITE_ENABLE_LOAD_EXTENSION
        return "python-fallback"
    except Exception:
        # .so found but failed to load
        return "python-fallback"


def init_document_tables(conn: sqlite3.Connection) -> None:
    """Create document, chunk, and vector tables if they do not exist.

    vec_items MUST use distance_metric=cosine — Phase 3 similarity threshold
    (~0.35) is calibrated for cosine distance. Omitting this defaults to L2,
    which breaks Phase 3 silently.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'indexing',
            chunk_count INTEGER DEFAULT 0,
            filepath TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(id),
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_items
        USING vec0(embedding float[1536] distance_metric=cosine)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id TEXT NOT NULL,
            vec_rowid INTEGER NOT NULL
        )
    """)
    conn.commit()


def init_session_tables(conn: sqlite3.Connection) -> None:
    """Create sessions table if it does not exist.

    session_id: UUID string (server-generated, D-02)
    messages:   JSON array of {"role": "user"|"assistant", "content": "..."} (D-01)
    last_active: ISO-8601 UTC — cron script uses this for 24-hour TTL expiry (D-03)
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


def init_leads_table(conn: sqlite3.Connection) -> None:
    """Create leads table if it does not exist.

    Phase 4 creates the schema so the leads view works (empty table — no error).
    Phase 6 adds the capture route that populates this table.

    id:         UUID string (primary key)
    name:       lead's name (from Phase 6 capture form)
    email:      lead's email address
    question:   the visitor question that triggered the lead capture
    created_at: ISO-8601 UTC timestamp
    phone:      lead's phone number (Phase 6 — optional, may be NULL)
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            question   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # Phase 6: add phone column if not present (idempotent)
    existing = [row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()]
    if 'phone' not in existing:
        conn.execute("ALTER TABLE leads ADD COLUMN phone TEXT")
    conn.commit()


def init_settings_table(conn: sqlite3.Connection) -> None:
    """Create settings table if it does not exist.

    key:   arbitrary setting name (e.g. 'book_call_url')
    value: setting value as text

    No pre-seeded rows — defaults to empty string when key absent.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def init_db(app: flask.Flask) -> None:
    """Initialize sqlite-vec DB. Called once from create_app().

    Sets on app.config:
      DB_CONN       — sqlite3.Connection (reused across requests)
      SQLITE_VEC_MODE — 'native' or 'python-fallback'
      DB_PATH       — absolute path to dochat.db
    """
    storage_path = app.config['STORAGE_PATH']
    os.makedirs(storage_path, exist_ok=True)

    db_path = os.path.join(storage_path, 'dochat.db')
    conn = _open_db(db_path)
    mode = _load_sqlite_vec(conn)
    init_document_tables(conn)
    init_session_tables(conn)   # new — D-01
    init_leads_table(conn)      # Phase 4 — leads schema (populated in Phase 6)
    init_settings_table(conn)   # Phase 6 — book-call URL and other settings

    app.config['DB_CONN'] = conn
    app.config['SQLITE_VEC_MODE'] = mode
    app.config['DB_PATH'] = db_path
