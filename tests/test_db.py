import os
import sqlite3


def test_db_init_sets_config_keys(app):
    """init_db() must set DB_CONN, SQLITE_VEC_MODE, DB_PATH on app.config — covers INFRA-02."""
    assert 'DB_CONN' in app.config
    assert 'SQLITE_VEC_MODE' in app.config
    assert 'DB_PATH' in app.config


def test_db_wal_mode(app):
    """PRAGMA journal_mode must return 'wal' — covers INFRA-02."""
    conn = app.config['DB_CONN']
    row = conn.execute("PRAGMA journal_mode;").fetchone()
    assert row[0] == 'wal', f"Expected 'wal', got '{row[0]}'"


def test_db_busy_timeout(app):
    """PRAGMA busy_timeout must be 10000 ms — covers INFRA-02 hard rule."""
    conn = app.config['DB_CONN']
    row = conn.execute("PRAGMA busy_timeout;").fetchone()
    assert row[0] == 10000, f"Expected 10000, got {row[0]}"


def test_sqlite_vec_mode_valid(app):
    """SQLITE_VEC_MODE must be 'native' or 'python-fallback' — covers INFRA-02."""
    mode = app.config['SQLITE_VEC_MODE']
    assert mode in ('native', 'python-fallback'), f"Unexpected mode: {mode!r}"


def test_storage_path_not_under_public_html(app):
    """STORAGE_PATH must not contain 'public_html' — covers INFRA-03."""
    storage = app.config['STORAGE_PATH']
    assert 'public_html' not in storage, f"STORAGE_PATH must not be under public_html: {storage}"


def test_storage_path_is_absolute(app):
    """STORAGE_PATH must be an absolute path (no literal ~ tilde) — covers INFRA-03, Pitfall 6."""
    storage = app.config['STORAGE_PATH']
    assert os.path.isabs(storage), f"STORAGE_PATH must be absolute, got: {storage}"
    assert not storage.startswith('~'), "STORAGE_PATH must not start with ~ (use expanduser)"


def test_storage_dir_created(app):
    """Storage directory must exist after app startup — covers INFRA-03."""
    storage = app.config['STORAGE_PATH']
    assert os.path.isdir(storage), f"Storage directory not created: {storage}"


def test_vec_round_trip(app):
    """If mode=native, vec0 table creation + insert + retrieval must succeed — covers INFRA-02."""
    mode = app.config['SQLITE_VEC_MODE']
    conn = app.config['DB_CONN']

    if mode != 'native':
        import pytest
        pytest.skip("sqlite-vec native extension not available on this machine — fallback mode active")

    import sqlite_vec
    import struct

    # Serialize a float32 vector as bytes — sqlite-vec requires binary format
    vector = [0.1, 0.2, 0.3, 0.4]
    vec_bytes = struct.pack('4f', *vector)

    # Create a test vec0 table, insert a vector, retrieve it
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _test_vec USING vec0(embedding FLOAT[4])")
    conn.execute("INSERT INTO _test_vec(embedding) VALUES (?)", (vec_bytes,))
    row = conn.execute("SELECT rowid FROM _test_vec LIMIT 1").fetchone()
    assert row is not None, "vec0 insert + retrieval failed"
    # Cleanup
    conn.execute("DROP TABLE IF EXISTS _test_vec")
