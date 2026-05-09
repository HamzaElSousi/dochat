#!/usr/bin/env python3
"""archive_sessions.py — Hourly cron: archive expired SQLite sessions to MySQL.

Queries sessions WHERE last_active < NOW() - 24 hours.
For each expired session:
  1. INSERT into MySQL dochat_conversations (CREATE TABLE IF NOT EXISTS).
  2. DELETE from SQLite sessions.

On MySQL failure: logs error, leaves session in SQLite for next hourly retry (D-20).
Sessions are NEVER silently dropped.

Cron command (SiteGround cPanel -> Cron Jobs):
  python3 /home/customer/dochat/scripts/archive_sessions.py >> /home/customer/dochat/logs/archive.log 2>&1

Required env vars:
  MYSQL_URL: mysql+mysqlconnector://user:pass@host/dbname
"""
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

# -- Resolve project root so 'app' package is importable from cron context ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.db import _open_db  # noqa: E402 -- must come after sys.path manipulation

# -- Logging setup -------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

# -- Constants -----------------------------------------------------------------
STORAGE_PATH = os.path.expanduser('~/dochat/storage')
DB_PATH = os.path.join(STORAGE_PATH, 'dochat.db')
MYSQL_URL = os.environ.get('MYSQL_URL', '')

SESSION_TTL_HOURS = 24   # sessions inactive longer than this are archived (D-03)


def _parse_mysql_url(url: str) -> dict:
    """Parse mysql+mysqlconnector://user:pass@host/db into pymysql.connect() kwargs.

    Raises ValueError if URL is empty or malformed.
    """
    if not url:
        raise ValueError("MYSQL_URL env var is not set")
    # Strip dialect prefix so urlparse handles it as a plain URL
    plain = url.replace('mysql+mysqlconnector://', 'mysql://', 1)
    parsed = urlparse(plain)
    if not parsed.hostname:
        raise ValueError(f"Could not parse host from MYSQL_URL: {url!r}")
    return {
        'host': parsed.hostname,
        'port': parsed.port or 3306,
        'user': parsed.username,
        'password': parsed.password or '',
        'database': (parsed.path or '/').lstrip('/'),
        'charset': 'utf8mb4',
        'autocommit': False,
    }


def _ensure_mysql_table(cursor) -> None:
    """Create dochat_conversations if it does not exist (D-18)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dochat_conversations (
            session_id VARCHAR(36) PRIMARY KEY,
            messages   JSON NOT NULL,
            started_at DATETIME NOT NULL,
            ended_at   DATETIME NOT NULL,
            turn_count INT NOT NULL
        )
    """)


def _fetch_expired_sessions(conn: sqlite3.Connection) -> list:
    """Return list of (session_id, messages, created_at, last_active) rows older than TTL."""
    rows = conn.execute(
        """SELECT session_id, messages, created_at, last_active
           FROM sessions
           WHERE last_active < datetime('now', ?)""",
        [f'-{SESSION_TTL_HOURS} hours'],
    ).fetchall()
    return rows


def _archive_session_to_mysql(cursor, session_id: str, messages_json: str,
                               created_at: str, last_active: str) -> None:
    """INSERT one session into dochat_conversations. Uses INSERT IGNORE to skip duplicates."""
    messages = json.loads(messages_json)
    turn_count = len(messages) // 2  # each turn = 1 user + 1 assistant message

    # Parse ISO-8601 UTC strings to MySQL DATETIME format (drop timezone suffix)
    def _to_mysql_dt(iso: str) -> str:
        # Accept "2026-05-09T12:00:00+00:00" or "2026-05-09T12:00:00.123456+00:00"
        dt = datetime.fromisoformat(iso)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        """INSERT IGNORE INTO dochat_conversations
           (session_id, messages, started_at, ended_at, turn_count)
           VALUES (%s, %s, %s, %s, %s)""",
        (session_id, messages_json, _to_mysql_dt(created_at),
         _to_mysql_dt(last_active), turn_count),
    )


def _delete_session_from_sqlite(conn: sqlite3.Connection, session_id: str) -> None:
    """Delete one session from SQLite using manual BEGIN/COMMIT/ROLLBACK."""
    if conn.in_transaction:
        conn.execute('ROLLBACK')
    conn.execute('BEGIN')
    try:
        conn.execute('DELETE FROM sessions WHERE session_id = ?', [session_id])
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def main() -> None:
    """Fetch expired sessions, archive to MySQL, delete from SQLite."""
    import pymysql

    # -- Open SQLite ----------------------------------------------------------
    conn = _open_db(DB_PATH)

    expired = _fetch_expired_sessions(conn)
    if not expired:
        logger.info("No expired sessions to archive.")
        conn.close()
        return

    logger.info("Found %d expired session(s) to archive.", len(expired))

    # -- Parse MySQL connection params ----------------------------------------
    try:
        mysql_kwargs = _parse_mysql_url(MYSQL_URL)
    except ValueError as exc:
        logger.error("Cannot connect to MySQL: %s", exc)
        conn.close()
        return

    # -- Archive each session -------------------------------------------------
    archived = 0
    skipped = 0
    for session_id, messages_json, created_at, last_active in expired:
        # Step 1: Write to MySQL (on failure: log + skip delete per D-20)
        try:
            conn_my = pymysql.connect(**mysql_kwargs)
            try:
                with conn_my.cursor() as cur:
                    _ensure_mysql_table(cur)
                    _archive_session_to_mysql(
                        cur, session_id, messages_json, created_at, last_active
                    )
                conn_my.commit()
            finally:
                conn_my.close()
        except Exception as exc:
            logger.error(
                "MySQL write failed for session %s -- retaining in SQLite for next run: %s",
                session_id, exc,
            )
            skipped += 1
            continue  # Do NOT delete from SQLite (D-20)

        # Step 2: Delete from SQLite only after confirmed MySQL write
        try:
            _delete_session_from_sqlite(conn, session_id)
            archived += 1
        except Exception as exc:
            logger.error(
                "SQLite delete failed for session %s -- session may be duplicated on next run: %s",
                session_id, exc,
            )
            skipped += 1

    conn.close()
    logger.info(
        "Archive complete: %d archived, %d skipped (retained for retry).",
        archived, skipped,
    )


if __name__ == '__main__':
    main()
