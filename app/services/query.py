import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import requests

from app.ingest.embedder import embed_query
from app.services.ingestion import serialize_f32

# ── Module-level constants (read from env on first import) ──────────────────
SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.35'))
FALLBACK_MESSAGE = os.environ.get(
    'FALLBACK_MESSAGE',
    "I don't have information on that yet. Feel free to ask something else."
)
ASSISTANT_NAME = os.environ.get('ASSISTANT_NAME', 'DocChat Assistant')
ASSISTANT_PERSONA = os.environ.get('ASSISTANT_PERSONA', 'a helpful AI assistant')
PRIMARY_MODEL = 'google/gemma-3-27b-it:free'
FALLBACK_MODEL = 'qwen/qwen3-next-80b-a3b-instruct:free'
LLM_TIMEOUT = 30          # seconds per model attempt (D-13)
TOP_K = 4                 # top chunks to retrieve (QUERY-01)
MAX_HISTORY_TURNS = 10    # turns = user+assistant pairs; cap = 20 messages (QUERY-04)


# ── LLM helpers ─────────────────────────────────────────────────────────────

def _call_llm(messages: list[dict], model: str) -> str:
    """POST to OpenRouter chat completions. Raises requests.HTTPError or Timeout on failure."""
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    response = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={'model': model, 'messages': messages},
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    try:
        content = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        # OpenRouter returns 200 with no choices on content-filter refusals / overload
        raise requests.RequestException(f"Malformed LLM response: {data!r}")
    if content is None:
        raise requests.RequestException("LLM returned null content")
    return content


def _call_llm_with_retry(messages: list[dict]) -> str | None:
    """Try PRIMARY_MODEL; on 429/timeout/error retry with FALLBACK_MODEL.
    Returns None if both fail (caller uses FALLBACK_MESSAGE, D-14).
    """
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            return _call_llm(messages, model)
        except (requests.exceptions.Timeout, requests.HTTPError, requests.RequestException):
            continue
    return None


# ── Session helpers ──────────────────────────────────────────────────────────

def _load_session(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """Return stored messages list or [] if session not found."""
    row = conn.execute(
        'SELECT messages FROM sessions WHERE session_id = ?', [session_id]
    ).fetchone()
    if not row:
        return []
    return json.loads(row[0])


def _save_session(
    conn: sqlite3.Connection,
    session_id: str,
    messages: list[dict],
    created_at: str,
) -> None:
    """Upsert session row. Uses manual BEGIN/COMMIT/ROLLBACK — never 'with conn:'."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if conn.in_transaction:
        conn.execute('ROLLBACK')
    conn.execute('BEGIN')
    try:
        conn.execute(
            """INSERT INTO sessions (session_id, messages, created_at, last_active)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE
               SET messages = excluded.messages,
                   last_active = excluded.last_active""",
            [session_id, json.dumps(messages), created_at, now_iso],
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


# ── Vector search helper ─────────────────────────────────────────────────────

def _vector_search(conn: sqlite3.Connection, query_vec: list[float]) -> list[tuple]:
    """Return list of (chunk_id, distance) ordered by distance ASC, limit TOP_K.

    Uses sqlite-vec KNN syntax: WHERE embedding MATCH <blob> AND k = <int>.
    Distance is cosine distance (0.0=identical, 2.0=opposite).
    """
    blob = serialize_f32(query_vec)
    rows = conn.execute(
        """SELECT ce.chunk_id, vi.distance
           FROM vec_items vi
           JOIN chunk_embeddings ce ON ce.vec_rowid = vi.rowid
           WHERE vi.embedding MATCH ?
             AND vi.k = ?
           ORDER BY vi.distance ASC""",
        [blob, TOP_K],
    ).fetchall()
    return rows  # [(chunk_id, distance), ...]


# ── Public API ───────────────────────────────────────────────────────────────

def handle_chat(
    conn: sqlite3.Connection,
    message: str,
    session_id: str | None,
) -> dict:
    """Embed query → vector search → similarity gate → LLM → save session → return dict.

    Always returns:
      {"answer": str, "session_id": str, "fallback": bool, "sources": list[dict]}

    Never raises to caller — all LLM/embed failures degrade to fallback message (D-14).
    """
    is_new_session = session_id is None
    if is_new_session:
        session_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Embed the visitor query ──────────────────────────────────────
    try:
        query_vec = embed_query(message)
    except Exception:
        # Embedding failure → return fallback, no session saved
        return {
            'answer': FALLBACK_MESSAGE,
            'session_id': session_id,
            'fallback': True,
            'sources': [],
        }

    # ── Step 2: Vector search (top-k=4) ──────────────────────────────────────
    try:
        hits = _vector_search(conn, query_vec)
    except Exception:
        hits = []

    # ── Step 3: Similarity gate (QUERY-02) ───────────────────────────────────
    # cosine DISTANCE threshold: > (1.0 - SIMILARITY_THRESHOLD) means not similar enough
    distance_threshold = 1.0 - SIMILARITY_THRESHOLD   # default: 1.0 - 0.35 = 0.65
    if not hits or hits[0][1] > distance_threshold:
        return {
            'answer': FALLBACK_MESSAGE,
            'session_id': session_id,
            'fallback': True,
            'sources': [],
        }

    chunk_ids = [row[0] for row in hits]

    # ── Step 4: Retrieve chunk content + source metadata ─────────────────────
    placeholders = ','.join('?' for _ in chunk_ids)
    chunk_rows = conn.execute(
        f"""SELECT c.id, c.content, c.doc_id, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE c.id IN ({placeholders})""",
        chunk_ids,
    ).fetchall()

    # Preserve order from vector search
    chunk_map = {row[0]: row for row in chunk_rows}
    ordered_chunks = [chunk_map[cid] for cid in chunk_ids if cid in chunk_map]

    context_text = '\n\n'.join(row[1] for row in ordered_chunks)
    sources = [
        {'filename': row[3], 'doc_id': row[2]}
        for row in ordered_chunks
    ]

    # ── Step 5: Load session history (QUERY-04) ───────────────────────────────
    history = _load_session(conn, session_id)
    # Trim to last MAX_HISTORY_TURNS turns (1 turn = 2 messages: user + assistant)
    max_messages = MAX_HISTORY_TURNS * 2
    if len(history) > max_messages:
        history = history[-max_messages:]

    # ── Step 6: Build LLM message list (QUERY-03) ─────────────────────────────
    system_prompt = (
        f"You are {ASSISTANT_NAME}, {ASSISTANT_PERSONA}. "
        "Answer ONLY using the context provided below. "
        "If the context does not contain enough information to answer the question, "
        "say you don't know. Do not use any outside knowledge.\n\n"
        f"Context:\n{context_text}"
    )
    llm_messages = [{'role': 'system', 'content': system_prompt}]
    llm_messages.extend(history)
    llm_messages.append({'role': 'user', 'content': message})

    # ── Step 7: Call LLM with retry (QUERY-05) ────────────────────────────────
    answer = _call_llm_with_retry(llm_messages)
    if answer is None:
        # Both models failed — graceful degradation (D-14)
        return {
            'answer': FALLBACK_MESSAGE,
            'session_id': session_id,
            'fallback': True,
            'sources': sources,
        }

    # ── Step 8: Persist updated session ──────────────────────────────────────
    updated_history = history + [
        {'role': 'user', 'content': message},
        {'role': 'assistant', 'content': answer},
    ]
    try:
        _save_session(conn, session_id, updated_history, now_iso)
    except Exception:
        # Session save failure is non-fatal — answer was already computed
        pass

    return {
        'answer': answer,
        'session_id': session_id,
        'fallback': False,
        'sources': sources,
    }
