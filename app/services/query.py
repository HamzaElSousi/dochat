import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone

import requests

from app.ingest.embedder import embed_query
from app.llm_config import (
    fallback_model,
    llm_api_key,
    llm_base_url,
    primary_model,
    requires_api_key,
)
from app.services.ingestion import serialize_f32

# ── Module-level constants (read from env on first import) ──────────────────
SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.35'))
FALLBACK_MESSAGE = os.environ.get(
    'FALLBACK_MESSAGE',
    "I don't have information on that yet. Feel free to ask something else."
)
ASSISTANT_NAME = os.environ.get('ASSISTANT_NAME', 'DocChat Assistant')
ASSISTANT_PERSONA = os.environ.get('ASSISTANT_PERSONA', 'a helpful AI assistant')
LLM_TIMEOUT = 60          # seconds per model attempt (local models can be slower than hosted)
TOP_K = 4                 # top chunks to retrieve (QUERY-01)
MAX_HISTORY_TURNS = 10    # turns = user+assistant pairs; cap = 20 messages (QUERY-04)

# Warn at module load if a hosted key is needed but absent — prevents silent 401
# fallbacks (WR-01). With LLM_PROVIDER=ollama no key is required, so stay quiet.
if requires_api_key() and not os.environ.get('OPENROUTER_API_KEY'):
    import warnings
    warnings.warn(
        "OPENROUTER_API_KEY is not set — hosted LLM/embedding calls will fail and "
        "return the fallback message. Set LLM_PROVIDER=ollama to run fully local.",
        RuntimeWarning,
        stacklevel=2,
    )


# ── LLM helpers ─────────────────────────────────────────────────────────────

def _call_llm(messages: list[dict], model: str) -> str:
    """POST to the configured chat-completions endpoint (OpenRouter or Ollama).

    Raises requests.HTTPError or Timeout on failure.
    """
    api_key = llm_api_key()
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    response = requests.post(
        f'{llm_base_url()}/chat/completions',
        headers=headers,
        json={'model': model, 'messages': messages, 'stream': False},
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    try:
        content = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        # Providers return 200 with no choices on content-filter refusals / overload
        raise requests.RequestException(f"Malformed LLM response: {data!r}")
    if content is None:
        raise requests.RequestException("LLM returned null content")
    return content


def _call_llm_with_retry(messages: list[dict]) -> str | None:
    """Try the primary model; on 429/timeout/error retry with the fallback model.
    Returns None if both fail (caller uses FALLBACK_MESSAGE, D-14).
    """
    for model in (primary_model(), fallback_model()):
        try:
            return _call_llm(messages, model)
        except (requests.exceptions.Timeout, requests.HTTPError, requests.RequestException):
            continue
    return None


def _parse_chips(raw: str) -> tuple[str, list[str]]:
    """Extract chips JSON from raw LLM output. Returns (answer_text, chips).

    Expects LLM to append a JSON block after its answer:
      {"chips": ["Q1", "Q2", "Q3"]}

    Rules:
    - The JSON block must be the last {...} in the response.
    - chips must be a list of exactly 3 non-empty strings.
    - On any parse failure: return (raw, []) — silent fail per D-07.
    - The chip JSON block is stripped from the returned answer_text.
    """
    # Find last JSON object containing "chips" — re.findall returns all matches;
    # take the last one so a chips-like example earlier in the text is ignored (WR-03)
    matches = list(re.finditer(r'\{[^{}]*"chips"\s*:\s*\[[^\]]*\][^{}]*\}', raw, re.DOTALL))
    if not matches:
        return raw, []
    match = matches[-1]
    json_str = match.group(0)
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return raw, []
    chips = data.get('chips')
    if not isinstance(chips, list) or len(chips) != 3:
        return raw, []
    chips = [str(c).strip() for c in chips]
    if not all(chips):   # reject if any chip is empty string after strip
        return raw, []
    # Strip the chip JSON block from the answer text
    answer_text = raw[:match.start()].rstrip()
    return answer_text, chips


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
        import logging
        logging.getLogger(__name__).warning(
            "_save_session: rolling back leaked transaction before BEGIN"
        )
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
      {"answer": str, "session_id": str, "fallback": bool, "sources": list[dict],
       "chips": list[str]}

    chips is a list of up to 3 follow-up question strings. Empty list on fallback or
    when chip parsing fails (silent fail per D-07).

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
            'chips': [],
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
            'chips': [],
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
        "say you don't know. Do not use any outside knowledge. "
        "When mentioning any URL or link, always write the full address including https:// "
        "(e.g. https://social-automate.com/book, never just social-automate.com/book).\n\n"
        f"Context:\n{context_text}\n\n"
        "After your answer, on a new line, output EXACTLY this JSON and nothing else after it:\n"
        '{"chips": ["<question 1>", "<question 2>", "<question 3>"]}\n'
        "The three chips are short questions (under 12 words each) written from the VISITOR'S perspective — "
        "things the visitor might want to ask YOU next based on your answer. "
        "Do NOT write questions you would ask the visitor."
    )
    llm_messages = [{'role': 'system', 'content': system_prompt}]
    llm_messages.extend(history)
    llm_messages.append({'role': 'user', 'content': message})

    # ── Step 7: Call LLM with retry (QUERY-05) ────────────────────────────────
    raw_answer = _call_llm_with_retry(llm_messages)
    if raw_answer is None:
        # Both models failed — graceful degradation (D-14)
        return {
            'answer': FALLBACK_MESSAGE,
            'session_id': session_id,
            'fallback': True,
            'sources': sources,
            'chips': [],
        }
    answer, chips = _parse_chips(raw_answer)

    # ── Step 8: Persist updated session ──────────────────────────────────────
    # Store chip-stripped answer (not raw_answer) in session history
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
        'chips': chips,
    }
