import os
import sqlite3
import flask


def _open_db(db_path: str) -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and 10s busy timeout.
    WAL is persistent (file-level). busy_timeout is per-connection — set on EVERY open.
    """
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

    app.config['DB_CONN'] = conn
    app.config['SQLITE_VEC_MODE'] = mode
    app.config['DB_PATH'] = db_path
