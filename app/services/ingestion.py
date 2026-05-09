import os
import uuid
import struct
import sqlite3
from datetime import datetime, timezone

from app.ingest.parser import detect_file_type, parse_file
from app.ingest.chunker import chunk_text
from app.ingest.embedder import embed_chunks


def serialize_f32(vector: list[float]) -> bytes:
    """Pack float list into binary format required by sqlite-vec vec0 tables."""
    return struct.pack(f"{len(vector)}f", *vector)


def _delete_document(conn: sqlite3.Connection, doc_id: str) -> None:
    """Delete all rows associated with doc_id from vec_items, chunk_embeddings, chunks, documents.

    vec0 virtual tables can only be deleted by rowid — the chunk_embeddings mapping
    table is required to find vec_rowid for each chunk (RESEARCH.md Pitfall 7).
    All operations run within the caller's active transaction.
    """
    # Step 1: Look up vec rowids for this document's chunks via the mapping table
    vec_rows = conn.execute(
        "SELECT ce.vec_rowid FROM chunk_embeddings ce "
        "JOIN chunks c ON c.id = ce.chunk_id "
        "WHERE c.doc_id = ?",
        [doc_id]
    ).fetchall()

    # Step 2: Delete from vec_items by rowid (vec0 only supports rowid-based delete)
    for (vec_rowid,) in vec_rows:
        conn.execute("DELETE FROM vec_items WHERE rowid = ?", [vec_rowid])

    # Step 3: Delete mapping, chunks, document metadata in dependency order
    conn.execute(
        "DELETE FROM chunk_embeddings WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)", [doc_id]
    )
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", [doc_id])
    conn.execute("DELETE FROM documents WHERE id = ?", [doc_id])


def ingest_file(
    conn: sqlite3.Connection,
    storage_path: str,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """Parse, chunk, embed, and store a document atomically.

    Rollback strategy (RESEARCH.md Pattern 1):
      1. Parse + chunk + embed (raises ValueError on failure — no DB/disk state yet)
      2. Write file bytes to tmp path (storage_path/tmp/<doc_id>.<ext>)
      3. BEGIN transaction
      4. DELETE existing doc if same filename (duplicate replace — Pitfall 7)
      5. INSERT documents (status='indexing'), chunks, vec_items, chunk_embeddings
      6. UPDATE documents.status='ready', chunk_count=N
      7. COMMIT
      8. os.rename(tmp_path, final_path)  <- atomic within same filesystem

    On ANY exception: ROLLBACK + delete tmp_path.
    Never use 'with conn:' context manager — use only manual BEGIN/COMMIT/ROLLBACK
    to avoid sqlite3.OperationalError on nested transactions (RESEARCH.md Pitfall 6).

    Returns: {"doc_id": str, "filename": str, "chunk_count": int, "status": "ready"}
    Raises: ValueError with human-readable message on parse/chunk/embed failure.
    """
    # Detect file type (raises ValueError for unsupported extensions)
    filetype = detect_file_type(filename)

    doc_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1].lower()

    # Set up paths — all derived from storage_path parameter (never os.path.expanduser here)
    tmp_dir = os.path.join(storage_path, 'tmp')
    final_dir = os.path.join(storage_path, 'uploads', doc_id)
    tmp_path = os.path.join(tmp_dir, f"{doc_id}{ext}")
    final_path = os.path.join(final_dir, f"original{ext}")

    os.makedirs(tmp_dir, exist_ok=True)

    # Parse text (raises ValueError on corrupt/empty/unsupported content)
    text = parse_file(file_bytes, filetype)

    # Chunk text (raises ValueError if no chunks produced)
    chunks = chunk_text(text)

    # Embed all chunks — may raise requests.HTTPError or ValueError
    embeddings = embed_chunks(chunks)

    # Write file to temp location BEFORE transaction (so we can clean up on failure)
    with open(tmp_path, 'wb') as f:
        f.write(file_bytes)

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute("BEGIN")

        # Fetch existing doc's filepath BEFORE deleting (vec0 delete needs rowid from mapping)
        existing_row = conn.execute(
            "SELECT id, filepath FROM documents WHERE filename = ?", [filename]
        ).fetchone()
        if existing_row:
            existing_id, existing_filepath = existing_row
            _delete_document(conn, existing_id)
            if existing_filepath and os.path.exists(existing_filepath):
                try:
                    os.remove(existing_filepath)
                except OSError:
                    pass  # Non-fatal — orphaned file is acceptable (T-02-09)

        conn.execute(
            "INSERT INTO documents (id, filename, filetype, uploaded_at, status, chunk_count, filepath) "
            "VALUES (?, ?, ?, ?, 'indexing', 0, ?)",
            [doc_id, filename, filetype, now_iso, final_path]
        )

        for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO chunks (id, doc_id, content, chunk_index) VALUES (?, ?, ?, ?)",
                [chunk_id, doc_id, chunk_content, idx]
            )
            result = conn.execute(
                "INSERT INTO vec_items(embedding) VALUES (?)",
                [serialize_f32(embedding)]
            )
            vec_rowid = result.lastrowid
            conn.execute(
                "INSERT INTO chunk_embeddings (chunk_id, vec_rowid) VALUES (?, ?)",
                [chunk_id, vec_rowid]
            )

        conn.execute(
            "UPDATE documents SET status = 'ready', chunk_count = ? WHERE id = ?",
            [len(chunks), doc_id]
        )
        conn.execute("COMMIT")

        os.makedirs(final_dir, exist_ok=True)
        os.rename(tmp_path, final_path)

    except Exception:
        conn.execute("ROLLBACK")
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise

    return {
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "status": "ready",
    }
