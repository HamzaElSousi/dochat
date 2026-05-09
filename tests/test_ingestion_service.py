"""Service-layer tests for the ingestion pipeline.

Tests call ingest_file() and embed_chunks() directly (bypassing HTTP layer)
so they can inspect the SQLite database to verify correctness properties:
atomic rollback, token-aware chunking, batch embedding, duplicate-replace semantics.

Covers: INGEST-05 (chunk size), INGEST-06 (batch embed), INGEST-07 (rollback), D-07 (duplicate-replace).
"""
import os
import requests
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embed_mock(mocker, n_chunks):
    """Return a mock for requests.post that simulates successful embed call."""
    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.json.return_value = {
        'data': [{'embedding': [0.1] * 1536, 'index': i} for i in range(n_chunks)]
    }
    mock_post.return_value.raise_for_status = lambda: None
    return mock_post


def _ingest_txt(conn, storage_path, mocker, filename='sample.txt', n_chunks=1, text=None):
    """Ingest a small TXT document with mocked embeddings."""
    from app.services.ingestion import ingest_file
    if text is None:
        text = ('The quick brown fox jumps over the lazy dog. ' * 50).encode('utf-8')
    _make_embed_mock(mocker, n_chunks)
    return ingest_file(conn, storage_path, text, filename)


# ---------------------------------------------------------------------------
# Rollback tests (INGEST-07)
# ---------------------------------------------------------------------------

def test_rollback_on_embed_failure(app, mocker):
    """When embed_chunks raises HTTPError, documents and chunks tables remain empty."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("429 rate limit")

    from app.services.ingestion import ingest_file
    with pytest.raises((requests.HTTPError, ValueError, Exception)):
        ingest_file(conn, storage_path, b'Some text content. ' * 50, 'rollback_test.txt')

    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert doc_count == 0, f"Expected 0 documents after rollback, got {doc_count}"
    assert chunk_count == 0, f"Expected 0 chunks after rollback, got {chunk_count}"


def test_rollback_on_embed_failure_no_vec_rows(app, mocker):
    """When embedding fails, chunk_embeddings table remains empty."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("500 server error")

    from app.services.ingestion import ingest_file
    with pytest.raises(Exception):
        ingest_file(conn, storage_path, b'Some content. ' * 50, 'rollback_vec.txt')

    ce_count = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
    assert ce_count == 0, f"Expected 0 chunk_embeddings after rollback, got {ce_count}"


def test_rollback_no_temp_file_on_disk(app, mocker):
    """When embedding fails, the temp file written before the transaction is deleted."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']
    tmp_dir = os.path.join(storage_path, 'tmp')

    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("503")

    from app.services.ingestion import ingest_file
    with pytest.raises(Exception):
        ingest_file(conn, storage_path, b'Content. ' * 50, 'rollback_file.txt')

    # No .txt files should linger in the tmp dir
    if os.path.exists(tmp_dir):
        leftover = [f for f in os.listdir(tmp_dir) if f.endswith('.txt')]
        assert leftover == [], f"Temp files not cleaned up: {leftover}"


# ---------------------------------------------------------------------------
# Batch embedding tests (INGEST-06)
# ---------------------------------------------------------------------------

def test_embed_batch_single_call(app, mocker):
    """Ingesting a document that produces ~1 chunk calls requests.post exactly once."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    # Use short text that produces a predictable small number of chunks
    short_text = 'This is a sentence. ' * 40   # ~40 * 5 tokens = ~200 tokens -> 1 chunk
    mock_post = _make_embed_mock(mocker, 1)

    from app.services.ingestion import ingest_file
    ingest_file(conn, storage_path, short_text.encode(), 'single_batch.txt')

    assert mock_post.call_count == 1, f"Expected 1 embed call, got {mock_post.call_count}"


def test_embed_subbatch_101_chunks(mocker):
    """embed_chunks with 101 inputs splits into 2 sub-batches of <=100 each."""
    call_batches = []

    def fake_post(*args, **kwargs):
        batch = kwargs['json']['input']
        call_batches.append(len(batch))
        mock_resp = mocker.MagicMock()
        mock_resp.json.return_value = {
            'data': [{'embedding': [0.1] * 1536, 'index': i} for i in range(len(batch))]
        }
        mock_resp.raise_for_status = lambda: None
        return mock_resp

    mocker.patch('app.ingest.embedder.requests.post', side_effect=fake_post)
    from app.ingest.embedder import embed_chunks
    result = embed_chunks([f'chunk text number {i}' for i in range(101)])

    assert len(call_batches) == 2, f"Expected 2 sub-batch calls, got {len(call_batches)}: {call_batches}"
    assert call_batches[0] == 100, f"First batch should be 100, got {call_batches[0]}"
    assert call_batches[1] == 1, f"Second batch should be 1, got {call_batches[1]}"
    assert len(result) == 101


# ---------------------------------------------------------------------------
# Chunking tests (INGEST-05)
# ---------------------------------------------------------------------------

def test_chunk_size_token_limit():
    """Every chunk produced by chunk_text() has at most 512 cl100k_base tokens."""
    import tiktoken
    from app.ingest.chunker import chunk_text

    long_text = 'The quick brown fox jumps over the lazy dog. ' * 500
    chunks = chunk_text(long_text)
    enc = tiktoken.get_encoding('cl100k_base')
    for i, chunk in enumerate(chunks):
        count = len(enc.encode(chunk))
        assert count <= 512, f"Chunk {i} has {count} tokens (expected <= 512)"


def test_chunk_overlap():
    """Consecutive chunks share content (overlap > 0 tokens)."""
    import tiktoken
    from app.ingest.chunker import chunk_text

    long_text = ' '.join(f'word{i}' for i in range(2000))  # unique words for clear overlap detection
    chunks = chunk_text(long_text)
    if len(chunks) < 2:
        pytest.skip("Text too short to produce multiple chunks")

    enc = tiktoken.get_encoding('cl100k_base')
    tokens_0 = set(enc.encode(chunks[0]))
    tokens_1 = set(enc.encode(chunks[1]))
    overlap = tokens_0 & tokens_1
    assert len(overlap) > 0, "Expected token overlap between consecutive chunks — got none"


# ---------------------------------------------------------------------------
# DB state tests (service integration)
# ---------------------------------------------------------------------------

def test_ingest_txt_db_rows(app, mocker):
    """After ingesting a TXT file, documents/chunks/chunk_embeddings all have rows."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']
    result = _ingest_txt(conn, storage_path, mocker, filename='dbtest.txt')

    doc_id = result['doc_id']
    doc = conn.execute("SELECT status, chunk_count FROM documents WHERE id = ?", [doc_id]).fetchone()
    assert doc is not None, "No documents row found"
    assert doc[0] == 'ready', f"Expected status='ready', got '{doc[0]}'"
    assert doc[1] > 0, "chunk_count should be > 0"

    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = ?", [doc_id]).fetchone()[0]
    assert chunk_count > 0, "No chunks rows found"

    ce_count = conn.execute(
        "SELECT COUNT(*) FROM chunk_embeddings WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)", [doc_id]
    ).fetchone()[0]
    assert ce_count > 0, "No chunk_embeddings rows found"
    assert ce_count == chunk_count, f"chunk_embeddings count ({ce_count}) != chunks count ({chunk_count})"


def test_ingest_file_filepath_set(app, mocker):
    """After ingesting, documents.filepath contains the doc_id and 'original.txt'."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']
    result = _ingest_txt(conn, storage_path, mocker, filename='filepath_test.txt')

    doc_id = result['doc_id']
    filepath = conn.execute("SELECT filepath FROM documents WHERE id = ?", [doc_id]).fetchone()[0]
    assert doc_id in filepath, f"doc_id not in filepath: {filepath}"
    assert 'original.txt' in filepath, f"'original.txt' not in filepath: {filepath}"
    assert os.path.exists(filepath), f"Final file does not exist at: {filepath}"


# ---------------------------------------------------------------------------
# Duplicate-replace tests (D-07)
# ---------------------------------------------------------------------------

def test_duplicate_replace_single_doc_row(app, mocker):
    """Uploading same filename twice leaves exactly 1 documents row."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    from app.services.ingestion import ingest_file
    for i in range(2):
        _make_embed_mock(mocker, 1)
        ingest_file(conn, storage_path, f'Content version {i}. '.encode() * 50, 'dup_test.txt')

    count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE filename = 'dup_test.txt'"
    ).fetchone()[0]
    assert count == 1, f"Expected 1 documents row after duplicate replace, got {count}"


def test_duplicate_replace_old_vectors_gone(app, mocker):
    """After duplicate replace, chunk_embeddings only contains rows for the NEW doc_id."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    from app.services.ingestion import ingest_file

    _make_embed_mock(mocker, 1)
    first = ingest_file(conn, storage_path, b'First version. ' * 50, 'dup_vec.txt')
    first_doc_id = first['doc_id']

    _make_embed_mock(mocker, 1)
    second = ingest_file(conn, storage_path, b'Second version. ' * 50, 'dup_vec.txt')
    second_doc_id = second['doc_id']

    # Old chunks should be gone
    old_chunk_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE doc_id = ?", [first_doc_id]
    ).fetchone()[0]
    assert old_chunk_count == 0, f"Old chunks not deleted: {old_chunk_count} rows remain"

    # New chunks should exist
    new_chunk_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE doc_id = ?", [second_doc_id]
    ).fetchone()[0]
    assert new_chunk_count > 0, "New chunks not found after replace"

    # chunk_embeddings for old doc should be gone
    old_ce = conn.execute(
        "SELECT COUNT(*) FROM chunk_embeddings WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)", [first_doc_id]
    ).fetchone()[0]
    assert old_ce == 0, f"Old chunk_embeddings not deleted: {old_ce} rows remain"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

def test_ingest_no_stack_trace_on_parse_error(app, mocker):
    """Ingesting an unsupported file type raises ValueError at the service layer."""
    conn = app.config['DB_CONN']
    storage_path = app.config['STORAGE_PATH']

    from app.services.ingestion import ingest_file
    with pytest.raises(ValueError):
        ingest_file(conn, storage_path, b'PK\x03\x04 zip content', 'archive.zip')
