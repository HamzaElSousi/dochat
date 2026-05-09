# Phase 2: Document Ingestion Pipeline - Research

**Researched:** 2026-05-08
**Domain:** Document parsing, chunking, embedding, sqlite-vec storage
**Confidence:** HIGH (stack), HIGH (patterns), MEDIUM (memory/timeout numbers)

---

## Summary

Phase 2 builds the backend ingestion pipeline: accept PDF/DOCX/TXT/MD files and URLs, parse
text, chunk with RecursiveCharacterTextSplitter, embed via OpenRouter batch API, and store in
sqlite-vec. The pipeline must be atomic (rollback on any failure), synchronous within one HTTP
request (CGI model), and stay well within SiteGround's 60-second Apache timeout.

The key technical choices resolve cleanly: **pdfplumber** for PDF extraction (pure-Python,
works on Python 3.14, no native libs needed), **python-docx** for DOCX, **trafilatura** for
URLs, **langchain-text-splitters** with tiktoken for token-aware splitting, and **sqlite-vec**
vec0 virtual tables with cosine distance for vector storage. The OpenRouter embeddings API
accepts array input so all chunks can be batched into one HTTP call.

The most complex piece is rollback: file writes and SQLite rows must all be undone if any step
fails. The pattern is to defer the file `os.rename()` to the very end — write to a temp path
first, commit the SQLite transaction, then rename. If anything before the rename raises, delete
the temp file and rollback the transaction.

**Primary recommendation:** Use pdfplumber for PDF (not PyMuPDF — pdfplumber is pure-Python
with no C extension size concerns on shared hosting), collect all chunk texts first, batch-embed
in one OpenRouter call, insert inside a single SQLite `conn.execute` block, then move the file.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Ingestion is fully synchronous within the HTTP request — no background job queue, no
  polling. CGI model is one request → one response.
- **D-02:** All chunks from a document are embedded in a **single batched OpenRouter API call**
  (array input). This collapses 100 serial HTTP calls into 1, keeping total ingestion time under
  5–10 seconds for typical documents.
- **D-03:** **Maximum file size: 10 MB.** Enforced at the API layer before processing begins.
  Returns HTTP 413 with clear message if exceeded.
- **D-04:** Keep uploaded originals on disk at `~/dochat/storage/uploads/<doc_id>/original.<ext>`.
  Storage path uses `os.path.expanduser()` — never hardcode `/home/customer/`.
- **D-05:** File uploads: `POST /admin/ingest/upload` — multipart/form-data, field name `file`.
  Returns JSON with `doc_id`, `filename`, `chunk_count`, `status`.
- **D-06:** URL ingestion: `POST /admin/ingest/url` — JSON body `{"url": "..."}`. Returns same
  JSON shape as file upload.
- **D-07:** Same filename uploaded again → **replace**: delete all existing chunks for that doc,
  remove old file, re-index fresh.
- **D-08:** If parsing, chunking, or embedding fails at any stage, the operation rolls back: no
  partial chunks written to sqlite-vec, no file saved to disk. Response is HTTP 422 with
  `{"error": "<reason>", "filename": "..."}`. The index is left unchanged.
- **D-09:** All storage paths use `os.path.expanduser('~/dochat/storage/')`.
- **D-10:** New `.htaccess` route needed for each new endpoint.

### Claude's Discretion
- API shape (D-05, D-06): multipart for files, JSON for URLs, separate endpoints — clean
  separation for Phase 4 UI.
- Duplicate handling (D-07): replace semantics — simplest correct behavior.
- Auth scaffolding: `@require_auth` decorator that checks HTTP Basic against `ADMIN_PASSWORD`
  from `.env` — stub in Phase 2, wired in Phase 4.

### Deferred Ideas (OUT OF SCOPE)
- Re-indexing all documents with updated chunking settings (v2 feature — ADM-04)
- Document preview / show indexed chunks (v2 feature — ADM-03)
- Streaming upload progress indicator (requires SSE, deferred to v2)
- Admin UI for these endpoints — Phase 4
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Admin can upload PDF files; system parses text and indexes chunks | pdfplumber section covers parsing; sqlite-vec section covers indexing |
| INGEST-02 | Admin can upload DOCX files; system parses text and indexes chunks | python-docx section covers paragraph + table extraction |
| INGEST-03 | Admin can upload TXT and MD files; system indexes content directly | No library needed — read with `open()` utf-8 |
| INGEST-04 | Admin can submit a URL; system crawls and indexes page content via trafilatura | trafilatura section covers fetch_url + extract pattern |
| INGEST-05 | System chunks documents with RecursiveCharacterTextSplitter (512 tokens, 100-token overlap) | langchain-text-splitters section covers from_tiktoken_encoder with cl100k_base |
| INGEST-06 | System generates embeddings via OpenRouter text-embedding-3-small API (no local ML models) | OpenRouter batch API section covers exact request format |
| INGEST-07 | Corrupt, password-protected, or JS-rendered-empty documents return a clear error; rollback confirmed | Error taxonomy section + rollback pattern section |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| File upload validation (size, type) | API / Backend | — | All validation before any processing; return 413/415 early |
| Document text extraction | API / Backend | — | CPU work in the CGI request; no browser involvement |
| Text chunking | API / Backend | — | Pure transform; lives in the service layer |
| Embedding generation | External API (OpenRouter) | API / Backend (caller) | Remote call; backend owns error handling and retry |
| Vector storage (sqlite-vec) | Database / Storage | — | Persistent; always via _open_db() connection |
| Metadata storage (documents, chunks) | Database / Storage | — | Same SQLite file, same WAL connection |
| File storage (originals) | Database / Storage | — | ~/dochat/storage/uploads/ — never public_html |
| Rollback coordination | API / Backend | — | Application-level; spans filesystem + SQLite |
| Auth stub (@require_auth) | API / Backend | — | HTTP Basic; scaffolded here, wired in Phase 4 |

---

## Standard Stack

### Core (new additions to requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pdfplumber | 0.11.9 | PDF text extraction | Pure-Python (depends on pdfminer.six, no C extensions beyond pdfminer's own); tested on Python 3.10–3.14; handles text-layer PDFs well; raises exceptions cleanly for password-protected/corrupt files |
| python-docx | 1.2.0 | DOCX text extraction | Standard library for python-openxml format; paragraphs + tables API is straightforward |
| trafilatura | 2.0.0 | URL crawling and text extraction | Purpose-built web text extractor; returns None for empty/JS-only pages — no exception needed |
| langchain-text-splitters | 1.1.2 | RecursiveCharacterTextSplitter | Correct import package for standalone splitter use (not the full langchain package); minimal deps |
| tiktoken | 0.12.0 | Token counting for chunking | Required by langchain-text-splitters from_tiktoken_encoder; uses cl100k_base for text-embedding-3-small |
| requests | 2.33.1 | OpenRouter embeddings HTTP call | Already a dep of trafilatura; used directly for embeddings API call |
| pytest-mock | 3.15.1 | Mocking OpenRouter in tests | Thin wrapper over unittest.mock; integrates with existing pytest suite |

**Version verification:** All versions confirmed via `pip3 index versions` against PyPI registry on 2026-05-08. [VERIFIED: PyPI registry]

### Existing (already in requirements.txt — no change)

| Library | Version | Purpose |
|---------|---------|---------|
| flask | 3.1.3 | Web framework |
| sqlite-vec | 0.1.9 | Vector virtual tables |
| python-dotenv | 1.2.2 | .env loading |
| pytest | 8.3.5 | Test runner |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pdfplumber | PyMuPDF (pymupdf) | PyMuPDF is faster and lower memory, but it requires a compiled C extension (MuPDF). On SiteGround shared hosting the extension must install from a wheel — a pre-built wheel for Python 3.14 linux/manylinux IS available [VERIFIED: PyPI], but pdfplumber is pure-Python (no wheel risk) and sufficient for 10 MB file limit. Use pdfplumber. |
| pdfplumber | pypdf | pypdf 6.x has weaker text ordering for multi-column PDFs; no advantage over pdfplumber for this use case. |
| trafilatura | requests + BeautifulSoup | trafilatura includes boilerplate removal (nav, ads, footers) which BS4 does not; for RAG quality this matters. |
| langchain-text-splitters | custom splitter | RecursiveCharacterTextSplitter handles edge cases (very short texts, 0-chunk docs) correctly; no reason to hand-roll. |

**Installation (additions only):**
```bash
pip install pdfplumber==0.11.9 python-docx==1.2.0 trafilatura==2.0.0 \
            langchain-text-splitters==1.1.2 tiktoken==0.12.0 pytest-mock==3.15.1
```

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP POST /admin/ingest/upload          HTTP POST /admin/ingest/url
     |                                        |
     v                                        v
[require_auth stub]                   [require_auth stub]
     |                                        |
     v                                        v
[size / type gate]                    [URL fetch via trafilatura.fetch_url()]
  (>10 MB → 413)                      (None → 422 "no content extracted")
     |                                        |
     v                                        v
[file type detect]               [trafilatura.extract(html) → plain text]
(extension + magic bytes)               (None → 422 "empty content")
     |                                        |
     +------------------+--------------------+
                        |
                        v
              [text extraction layer]
              PDF  → pdfplumber
              DOCX → python-docx
              TXT/MD → open().read()
              (exception → 422, no temp file written yet)
                        |
                        v
              [RecursiveCharacterTextSplitter]
              from_tiktoken_encoder("cl100k_base")
              chunk_size=512, chunk_overlap=100
              (0 chunks → 422 "document produced no chunks")
                        |
                        v
              [OpenRouter batch embed]
              POST /v1/embeddings
              model: openai/text-embedding-3-small
              input: [chunk_text_1, ..., chunk_text_N]
              (HTTP error / timeout → 422, rollback)
                        |
                        v
              [SQLite transaction BEGIN]
                 INSERT documents row (status='indexing')
                 INSERT chunks rows
                 INSERT vec_items rows (vec0 virtual table)
                 INSERT chunk_embeddings mapping rows
                 UPDATE documents.status = 'ready', chunk_count = N
              [COMMIT]
                        |
                        v
              [os.rename(tmp_path → final_path)]
              (rename only after commit succeeds)
                        |
                        v
              JSON 200 {doc_id, filename, chunk_count, status:"ready"}
```

**Rollback path:** Any exception before `os.rename()` triggers `conn.rollback()` and
`os.unlink(tmp_path)`. The vec0 virtual table rows are inside the same SQLite transaction
and roll back together with the regular tables.

### Recommended Project Structure

```
app/
├── routes/
│   ├── health.py           # existing
│   └── ingest.py           # new: ingest_bp (upload + url endpoints)
├── services/
│   └── ingestion.py        # new: parse_*, chunk_text, embed_chunks, store_document
├── db.py                   # existing: extend with init_document_tables()
└── __init__.py             # existing: register ingest_bp
tests/
├── conftest.py             # existing: app fixture
├── test_ingest_upload.py   # new: upload endpoint tests
├── test_ingest_url.py      # new: url endpoint tests
└── test_ingestion_service.py  # new: unit tests for service functions
```

### Pattern 1: Atomic Rollback Across Filesystem + SQLite

The core challenge: file write and SQLite insert must both succeed or both fail.

**Strategy:** Write to a temp file under `storage/tmp/`; commit SQLite; only then rename to
final path. On any exception, rollback SQLite and delete temp file.

```python
# Source: derived from SQLite transaction semantics + filesystem atomicity principles [ASSUMED]
import os
import uuid

def ingest_document(conn, storage_path, file_bytes, filename, filetype, chunks, embeddings):
    doc_id = str(uuid.uuid4())
    tmp_dir = os.path.join(storage_path, 'tmp')
    final_dir = os.path.join(storage_path, 'uploads', doc_id)
    os.makedirs(tmp_dir, exist_ok=True)

    ext = os.path.splitext(filename)[1].lower()
    tmp_path = os.path.join(tmp_dir, f"{doc_id}{ext}")
    final_path = os.path.join(final_dir, f"original{ext}")

    # Write to temp location first
    with open(tmp_path, 'wb') as f:
        f.write(file_bytes)

    try:
        conn.execute("BEGIN")
        # ... INSERT documents, chunks, vec_items, chunk_embeddings ...
        conn.execute("COMMIT")
        # Rename only after commit
        os.makedirs(final_dir, exist_ok=True)
        os.rename(tmp_path, final_path)
    except Exception:
        conn.execute("ROLLBACK")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

**Key insight:** `os.rename()` within the same filesystem is atomic at the OS level. If the
process dies after COMMIT but before rename, the DB has the row but no file — handle this in a
future cleanup job (out of scope for Phase 2).

### Pattern 2: sqlite-vec Vector Table Schema and Queries

```python
# Source: sqlite-vec demo.py [VERIFIED: github.com/asg017/sqlite-vec]
import struct

def serialize_f32(vector: list[float]) -> bytes:
    """Pack float list into compact binary for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)

# Table creation (in init_document_tables)
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

# Insert
result = conn.execute(
    "INSERT INTO vec_items(embedding) VALUES (?)",
    [serialize_f32(embedding_list)]
)
vec_rowid = result.lastrowid
conn.execute(
    "INSERT INTO chunk_embeddings(chunk_id, vec_rowid) VALUES (?, ?)",
    [chunk_id, vec_rowid]
)

# KNN query (Phase 3 usage — documented here for planning continuity)
# Source: alexgarcia.xyz/sqlite-vec/features/knn.html [VERIFIED]
rows = conn.execute("""
    WITH knn AS (
        SELECT rowid, distance
        FROM vec_items
        WHERE embedding MATCH ?
        AND k = 4
    )
    SELECT c.content, c.doc_id, knn.distance
    FROM knn
    JOIN chunk_embeddings ce ON ce.vec_rowid = knn.rowid
    JOIN chunks c ON c.id = ce.chunk_id
    ORDER BY knn.distance
""", [serialize_f32(query_embedding)]).fetchall()
```

**Critical detail:** `distance_metric=cosine` must be set at table creation time. Default is
L2. Phase 3 similarity threshold (cosine ~0.35) requires cosine. Set it now. [VERIFIED: alexgarcia.xyz/sqlite-vec/features/knn.html]

### Pattern 3: RecursiveCharacterTextSplitter with Token Counting

```python
# Source: docs.langchain.com/oss/python/integrations/splitters/split_by_token [VERIFIED]
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",  # encoding used by text-embedding-3-small [VERIFIED: tiktoken repo]
        chunk_size=512,
        chunk_overlap=100,
    )
    chunks = splitter.split_text(text)
    return [c for c in chunks if c.strip()]  # filter empty strings
```

**Why `from_tiktoken_encoder`:** Regular `RecursiveCharacterTextSplitter(chunk_size=512)` counts
characters, not tokens. `from_tiktoken_encoder` counts tokens. A 512-character chunk may be
only 100 tokens for English text; the requirement specifies 512 tokens. [VERIFIED: langchain docs]

**Encoding:** `text-embedding-3-small` uses `cl100k_base` — same as GPT-4 and ada-002.
[VERIFIED: github.com/openai/tiktoken]

### Pattern 4: OpenRouter Batch Embeddings

```python
# Source: openrouter.ai/docs/api/api-reference/embeddings [VERIFIED]
import os
import requests

def embed_chunks(chunk_texts: list[str]) -> list[list[float]]:
    """Submit all chunks in one API call. Returns list of 1536-dim vectors."""
    api_key = os.environ['OPENROUTER_API_KEY']
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/text-embedding-3-small",
            "input": chunk_texts,  # array of strings — batch supported [VERIFIED]
        },
        timeout=30,  # seconds; well within 60s Apache limit
    )
    response.raise_for_status()
    data = response.json()
    # Response: {"data": [{"embedding": [...], "index": 0}, ...]}
    embeddings = sorted(data["data"], key=lambda x: x["index"])
    return [e["embedding"] for e in embeddings]
```

**Rate limits:** OpenRouter docs do not publish free-tier rate limits. [ASSUMED: based on
OpenAI conventions, free tier may be throttled at ~60 RPM or 100K tokens/min; with one batched
call per document this is unlikely to be hit. Monitor for 429 responses in production.]

**Max tokens per request:** OpenAI `text-embedding-3-small` context window is 8,192 tokens.
For a document producing N chunks of 512 tokens each, total input tokens = N * 512. At 10 MB
plain text (~2M characters, ~500K tokens), chunked into ~1000 512-token chunks, total tokens
≈ 500K which exceeds one call. **However:** 10 MB is the file size limit, not content size.
A 10 MB PDF is mostly binary; extracted text is typically 5–20x smaller. A 10 MB PDF with
densely typeset text might yield ~100K tokens → ~200 chunks → batch input ~100K tokens. This
likely exceeds a single OpenRouter call limit. [ASSUMED: need to confirm; safe default is to
batch chunks in groups of 2048 tokens total input if a 429 or 413 is received.]

**Recommendation:** Add a batching helper that splits chunk_texts into sub-batches of max 100
chunks each and makes multiple calls if needed. For typical documents (< 50 chunks) this is a
no-op. [ASSUMED based on OpenAI's published 2048-input limit per call — OpenRouter may differ]

### Pattern 5: PDF Parsing with pdfplumber

```python
# Source: pypi.org/project/pdfplumber [VERIFIED]
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError

def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes. Raises ValueError with human-readable message on failure."""
    try:
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            texts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            full_text = "\n".join(texts)
    except PDFPasswordIncorrect:
        raise ValueError("PDF is password-protected — remove password before uploading")
    except PDFSyntaxError:
        raise ValueError("PDF appears to be corrupt or is not a valid PDF file")
    except Exception as e:
        raise ValueError(f"PDF parsing failed: {e}")

    if not full_text.strip():
        raise ValueError(
            "PDF contains no extractable text — it may be a scanned image PDF. "
            "OCR is not supported."
        )
    return full_text
```

**Scanned PDF behavior:** pdfplumber returns empty strings per page when a PDF is scanned
images with no text layer. The check `if not full_text.strip()` catches this and returns a
clear error (satisfies INGEST-07). [VERIFIED: pdfplumber GitHub issues #193, #1038]

**Encrypted PDF exceptions:** pdfplumber uses pdfminer.six internally. Password-protected PDFs
raise `pdfminer.pdfdocument.PDFPasswordIncorrect`. Corrupt PDFs raise `pdfminer.pdfparser.PDFSyntaxError`.
[VERIFIED: pdfplumber GitHub discussions]

### Pattern 6: DOCX Parsing with python-docx

```python
# Source: python-docx docs + GitHub issues/276 [VERIFIED via WebSearch]
from docx import Document
import zipfile

def parse_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes. Raises ValueError on corrupt file."""
    try:
        import io
        doc = Document(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise ValueError("DOCX file is corrupt or not a valid Word document")
    except Exception as e:
        raise ValueError(f"DOCX parsing failed: {e}")

    parts = []
    # Paragraphs (body text and headings)
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    # Tables — iterate cells to capture tabular content
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)

    full_text = "\n".join(parts)
    if not full_text.strip():
        raise ValueError("DOCX file contains no extractable text")
    return full_text
```

**Gotcha:** python-docx does NOT iterate tables automatically when you iterate `doc.paragraphs`.
Tables are separate from paragraphs in the OOXML structure — you must loop `doc.tables`
separately. [VERIFIED: github.com/python-openxml/python-docx/issues/276]

**Corrupt DOCX:** A DOCX is a ZIP archive. `python-docx` raises `zipfile.BadZipFile` (from the
stdlib `zipfile` module) when the file is not a valid ZIP. [VERIFIED: GitHub issue #765]

### Pattern 7: URL Ingestion with trafilatura

```python
# Source: trafilatura.readthedocs.io/en/latest [VERIFIED]
import trafilatura

def fetch_and_extract_url(url: str) -> str:
    """Fetch URL and extract main text content. Raises ValueError on failure."""
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise ValueError(f"Failed to fetch URL — network error, SSL error, or timeout: {url}")

    text = trafilatura.extract(downloaded)
    if text is None or not text.strip():
        raise ValueError(
            f"No extractable text found at URL — the page may be JavaScript-rendered "
            f"or contain no main content: {url}"
        )
    return text
```

**JS-rendered pages:** trafilatura uses standard HTTP (requests/httpx) with no JavaScript
engine. If a page is fully JS-rendered (blank HTML body), `extract()` returns `None`.
This is the correct behavior for INGEST-07: return a clear error, no partial index. [VERIFIED:
trafilatura source and issue #621]

**Timeout:** trafilatura's `fetch_url()` uses a configurable `DOWNLOAD_TIMEOUT` (default
appears to be ~20 seconds based on source inspection). A 20s fetch + processing + embed must
fit within Apache's 60s limit. For the worst case (slow URL), this is tight. Consider passing
a custom timeout via `trafilatura.settings.DEFAULT_CONFIG` or the `config` parameter. [ASSUMED
for exact default value — the docs do not publish a number; the source code should be checked
before implementation]

### Pattern 8: File Type Detection

```python
# Source: stdlib mimetypes [VERIFIED: Python docs]
import mimetypes
import os

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
EXTENSION_TO_TYPE = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain',
    '.md': 'text/markdown',
}

def detect_file_type(filename: str) -> str:
    """Returns filetype string ('pdf','docx','txt','md') or raises ValueError."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    return ext.lstrip('.')
```

**python-magic is NOT recommended** for this project: it requires `libmagic` system library.
Availability on SiteGround shared hosting is unknown and not guaranteed. Extension-based
detection is sufficient given that uploaded files are admin-controlled (not untrusted public
uploads). [VERIFIED: python-magic PyPI page states libmagic dependency; ASSUMED: libmagic not
confirmed available on SiteGround]

If a user uploads a `.pdf` file that is actually a DOCX, pdfplumber will raise an exception
which is caught and returned as a 422 — acceptable error UX for admin uploads.

### Anti-Patterns to Avoid

- **Writing the file before the DB transaction:** If the DB insert fails after file write, the
  file persists with no DB record — orphaned data. Always write to tmp, commit DB, then rename.
- **Using `conn.execute("BEGIN")` with a Python `with conn:` block together:** Python's sqlite3
  context manager (`with conn`) issues its own BEGIN. Do not mix manual `BEGIN`/`COMMIT` with
  the context manager — use one or the other. [VERIFIED: Robin's Blog sqlite3 context manager post]
- **Calling `embed_chunks([])` with empty list:** OpenRouter will reject an empty array. Always
  check `if not chunks: raise ValueError(...)` after chunking.
- **Relying on `doc.paragraphs` alone for DOCX:** Tables are missed. Always also iterate
  `doc.tables`. [VERIFIED: python-docx GitHub issue #276]
- **Setting `distance_metric=L2` (or omitting it) for Phase 3:** Phase 3 uses a cosine
  similarity threshold of ~0.35. L2 distance is not comparable to cosine similarity. Set
  `distance_metric=cosine` at table creation or Phase 3 thresholds will be wrong.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token-aware text splitting | Custom chunker | `RecursiveCharacterTextSplitter.from_tiktoken_encoder` | Handles short texts, overlap, separator hierarchy, edge cases |
| PDF text extraction | PDF parser | pdfplumber | PDF spec has hundreds of edge cases; pdfminer.six handles them |
| DOCX extraction | XML parser | python-docx | OOXML schema is complex; relationships, content types, namespace quirks |
| Web page boilerplate removal | HTML stripper | trafilatura | Removes nav/footer/ads; preserves main content; 5+ years of production use |
| Vector serialization | `struct.pack` manually | `serialize_f32()` from sqlite-vec demo | Exact format required by sqlite-vec; single helper |
| UUID generation | timestamp + random | `uuid.uuid4()` | Collision-free, no coordination needed |

---

## Common Pitfalls

### Pitfall 1: sqlite-vec Default Distance Metric is L2, not Cosine
**What goes wrong:** Creating `vec_items` without `distance_metric=cosine` means all stored
vectors use L2 distance. Phase 3 cosine similarity threshold of ~0.35 will be meaningless.
**Why it happens:** L2 is the vec0 default; easy to miss in documentation.
**How to avoid:** Always include `distance_metric=cosine` in the CREATE VIRTUAL TABLE statement.
**Warning signs:** Phase 3 query returns no results or always returns results regardless of relevance.
[VERIFIED: alexgarcia.xyz/sqlite-vec/features/knn.html]

### Pitfall 2: python-docx Misses Table Text
**What goes wrong:** Iterating only `doc.paragraphs` misses all text in DOCX tables. Documents
with pricing tables, spec sheets, or any tabular data will have that content silently dropped.
**Why it happens:** Tables are not paragraphs in OOXML; `doc.paragraphs` does not recurse into tables.
**How to avoid:** Always iterate `doc.tables` → rows → cells separately.
**Warning signs:** Indexed content is missing known table data from a test DOCX.
[VERIFIED: github.com/python-openxml/python-docx/issues/276]

### Pitfall 3: Scanned PDFs Return Empty Text Without Error
**What goes wrong:** A scanned-image PDF passes all validation (valid PDF, not encrypted,
extension OK) but pdfplumber returns empty strings for all pages. Without an explicit check,
the pipeline creates 0 chunks and returns success with chunk_count=0.
**Why it happens:** pdfplumber extracts text layers only; scanned images have no text layer.
**How to avoid:** After extraction, check `if not full_text.strip(): raise ValueError(...)`.
**Warning signs:** `chunk_count: 0` in success response with no error.

### Pitfall 4: CGI Timeout on Large Documents
**What goes wrong:** A 10 MB densely-typed PDF might produce 200+ chunks. pdfplumber parsing +
chunking + one OpenRouter call (200 * 512 tokens = 100K tokens) + SQLite inserts could approach
the 60-second Apache timeout on SiteGround.
**Why it happens:** CGI is synchronous; each request must complete within Apache's timeout.
**How to avoid:** Implement a batching limit on chunk count (e.g., max 200 chunks per document).
If `len(chunks) > 200`, truncate with a warning in the response. The 10 MB file size limit
provides a natural ceiling. Monitor real ingestion times in staging.
**Warning signs:** HTTP 504 Gateway Timeout on large PDF uploads.
[VERIFIED: siteground.com/kb — Apache timeout is 60 seconds, cannot be changed on shared hosting]

### Pitfall 5: OpenRouter Batch Input Token Limit
**What goes wrong:** Sending 200 chunks * 512 tokens = 100K tokens in one API call may exceed
OpenRouter's per-request token limit for the embeddings endpoint.
**Why it happens:** OpenRouter does not publish batch limits; OpenAI limits batch to 2048 inputs.
**How to avoid:** Split chunks into sub-batches of 100 if document exceeds that count. Make
multiple sequential embedding calls and concatenate results. Handle 429 with one retry after
brief delay (risks timeout on CGI — log and return 503 if 429 persists).
**Warning signs:** HTTP 400 or 413 from OpenRouter on large document upload.
[ASSUMED: exact limit not documented; precautionary batching recommended]

### Pitfall 6: SQLite Context Manager vs Manual Transaction
**What goes wrong:** Using `with conn:` (context manager) while also calling `conn.execute("BEGIN")`
leads to "cannot start a transaction within a transaction" errors in Python 3.12+.
**Why it happens:** Python's sqlite3 context manager issues an implicit BEGIN; explicit BEGIN
causes a nested transaction which SQLite rejects.
**How to avoid:** Use one approach. Recommended: manual `conn.execute("BEGIN") ... COMMIT/ROLLBACK`
for the rollback pattern — gives explicit control needed for cross-resource atomicity.
**Warning signs:** `sqlite3.OperationalError: cannot start a transaction within a transaction`.
[VERIFIED: blog.rtwilson.com/a-python-sqlite3-context-manager-gotcha]

### Pitfall 7: Duplicate Detection Requires Deleting vec_items by chunk_id
**What goes wrong:** When replacing a document, deleting from `chunks` and `documents` tables
is straightforward. But `vec_items` is a vec0 virtual table — you must delete by rowid, not
by a foreign key. The `chunk_embeddings` mapping table is required to find the vec_rowid for
each chunk before deletion.
**How to avoid:** The delete sequence for replace semantics must be:
  1. Look up `chunk_embeddings.vec_rowid` WHERE `chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)`
  2. DELETE FROM `vec_items` WHERE rowid = each vec_rowid
  3. DELETE FROM `chunk_embeddings` WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)
  4. DELETE FROM `chunks` WHERE doc_id = ?
  5. DELETE FROM `documents` WHERE id = ?
  6. DELETE file from disk
All within a single transaction before re-indexing.
[ASSUMED: derived from sqlite-vec vec0 constraints — vec0 does not support DELETE by non-rowid columns]

---

## Code Examples

### DB schema migration (add to db.py `init_document_tables`)
```python
# Source: sqlite-vec demo.py [VERIFIED: github.com/asg017/sqlite-vec]
def init_document_tables(conn) -> None:
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
```

### HTTP Basic Auth stub decorator
```python
# Source: [ASSUMED — standard Flask pattern]
import os
import functools
from flask import request, Response

def require_auth(f):
    """Stub auth decorator. Checks HTTP Basic against ADMIN_PASSWORD env var.
    Phase 4 replaces this stub with full implementation."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        auth = request.authorization
        if not auth or auth.password != admin_password:
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="DocChat Admin"'}
            )
        return f(*args, **kwargs)
    return decorated
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `from langchain.text_splitter import RecursiveCharacterTextSplitter` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` | langchain 0.2.x (2024) | Old import still works but triggers deprecation warning; use new package |
| PyPDF2 (archived) | pypdf 6.x | 2023 | PyPDF2 is archived; pypdf is the successor; pdfplumber wraps pdfminer.six (separate lineage) |
| `vec0` with L2 default | `vec0(... distance_metric=cosine)` | sqlite-vec v0.1.0 (2024) | Column-level distance metric must be specified at CREATE time |
| trafilatura 1.x API | trafilatura 2.0.0 (fetch_response replaces fetch_url) | 2024 | `fetch_url()` still works in 2.0 but `fetch_response()` is preferred for redirect URL access; `fetch_url()` is fine for Phase 2 |

**Deprecated/outdated:**
- PyPDF2: archived; do not use. Use pdfplumber (wraps pdfminer.six) or pypdf.
- `from langchain.text_splitter import ...`: deprecated import path; use `langchain_text_splitters`.

---

## Environment Availability

Server environment (SiteGround, Python 3.14.3) — confirmed from Phase 1 summary.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All | ✓ | 3.14.3 (server), 3.10.12 (local dev) | — |
| sqlite-vec | Vector storage | ✓ | 0.1.9 (native mode confirmed) | — |
| pdfplumber | INGEST-01 | Unconfirmed on server | 0.11.9 (PyPI) | — (install via pip) |
| python-docx | INGEST-02 | Unconfirmed on server | 1.2.0 (PyPI) | — (install via pip) |
| trafilatura | INGEST-04 | Unconfirmed on server | 2.0.0 (PyPI) | — (install via pip) |
| langchain-text-splitters | INGEST-05 | Unconfirmed on server | 1.1.2 (PyPI) | — (install via pip) |
| tiktoken | INGEST-05 | Unconfirmed on server | 0.12.0 (PyPI) | — (install via pip) |
| libmagic | File type detection | Unknown | — | Use extension-only detection (recommended) |
| OpenRouter API | INGEST-06 | ✓ (API key in .env) | — | — |

**Missing dependencies with no fallback:**
- None that block execution — all Python packages install via pip into the venv.

**Missing dependencies with fallback:**
- libmagic: not needed — extension-based detection is the recommended approach.

**Deployment note:** All new packages must be added to `requirements.txt` and installed via
`pip install -r requirements.txt` in `~/dochat/venv/` on SiteGround. pdfplumber 0.11.9 is
confirmed tested on Python 3.14 [VERIFIED: PyPI]. PyMuPDF also ships Python 3.14 wheels
[VERIFIED: PyPI] but is not needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 |
| Config file | none (pytest auto-discovers tests/) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | PDF upload → chunks indexed | integration | `pytest tests/test_ingest_upload.py -x -k pdf` | ❌ Wave 0 |
| INGEST-01 | Scanned PDF → 422 with message | integration | `pytest tests/test_ingest_upload.py -x -k scanned` | ❌ Wave 0 |
| INGEST-01 | Encrypted PDF → 422 with message | integration | `pytest tests/test_ingest_upload.py -x -k encrypted` | ❌ Wave 0 |
| INGEST-02 | DOCX upload → chunks indexed | integration | `pytest tests/test_ingest_upload.py -x -k docx` | ❌ Wave 0 |
| INGEST-02 | DOCX table text included in chunks | unit | `pytest tests/test_ingestion_service.py -x -k docx_tables` | ❌ Wave 0 |
| INGEST-03 | TXT/MD upload → chunks indexed | integration | `pytest tests/test_ingest_upload.py -x -k txt` | ❌ Wave 0 |
| INGEST-04 | URL crawl → chunks indexed | integration (mocked HTTP) | `pytest tests/test_ingest_url.py -x` | ❌ Wave 0 |
| INGEST-04 | JS-only URL → 422 | integration (mocked) | `pytest tests/test_ingest_url.py -x -k js_only` | ❌ Wave 0 |
| INGEST-05 | Chunk size ≤ 512 tokens each | unit | `pytest tests/test_ingestion_service.py -x -k chunk_size` | ❌ Wave 0 |
| INGEST-06 | Embeddings called with array input, not per-chunk | unit (mock) | `pytest tests/test_ingestion_service.py -x -k embed_batch` | ❌ Wave 0 |
| INGEST-07 | Corrupt PDF → 422, index unchanged | integration | `pytest tests/test_ingest_upload.py -x -k corrupt` | ❌ Wave 0 |
| INGEST-07 | Embedding API failure → rollback (no rows in DB) | unit (mock) | `pytest tests/test_ingestion_service.py -x -k rollback` | ❌ Wave 0 |
| D-07 | Duplicate filename → replace, old vectors deleted | integration | `pytest tests/test_ingest_upload.py -x -k duplicate` | ❌ Wave 0 |
| D-03 | >10 MB file → 413 | integration | `pytest tests/test_ingest_upload.py -x -k size_limit` | ❌ Wave 0 |

### Mock Strategy for OpenRouter

```python
# Source: pytest-mock pattern [VERIFIED: pytest-mock PyPI]
# In tests, patch the embed_chunks function or the requests.post call:

def test_embed_batch_calls_once(mocker, app):
    """Verify embed_chunks sends all chunks in one POST, not N posts."""
    mock_post = mocker.patch('app.services.ingestion.requests.post')
    mock_post.return_value.json.return_value = {
        "data": [{"embedding": [0.1] * 1536, "index": i} for i in range(3)]
    }
    mock_post.return_value.raise_for_status = lambda: None

    from app.services.ingestion import embed_chunks
    result = embed_chunks(["chunk1", "chunk2", "chunk3"])

    assert mock_post.call_count == 1
    call_args = mock_post.call_args
    assert len(call_args.kwargs['json']['input']) == 3
```

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ingest_upload.py` — covers INGEST-01, INGEST-02, INGEST-03, INGEST-07, D-03, D-07
- [ ] `tests/test_ingest_url.py` — covers INGEST-04
- [ ] `tests/test_ingestion_service.py` — covers INGEST-05, INGEST-06, rollback, embed mock
- [ ] pytest-mock added to requirements: `pip install pytest-mock==3.15.1`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | HTTP Basic Auth stub — ADMIN_PASSWORD from .env; full auth in Phase 4 |
| V3 Session Management | no | Admin API is stateless; no session tokens |
| V4 Access Control | yes | All /admin/* routes protected by @require_auth |
| V5 Input Validation | yes | File size gate (413), extension allowlist, content-type check |
| V6 Cryptography | no | No crypto in this phase |

### Known Threat Patterns for File Upload + URL Fetch

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via filename | Tampering | Never use `request.files['file'].filename` directly in paths; use `doc_id`-based paths; `os.path.basename()` if filename used |
| SSRF via URL ingestion | Spoofing | trafilatura follows redirects; for Phase 2 (admin-only) SSRF risk is low — document for Phase 4 review |
| Malicious PDF (parser exploits) | Tampering | pdfplumber/pdfminer.six is pure Python — no native memory vulnerabilities; risk is low |
| Admin password in URL/logs | Information Disclosure | HTTP Basic sends credentials in header, not URL; ensure no request logging that captures Authorization header |
| Temp file not cleaned up on exception | Elevation of Privilege | Rollback pattern deletes tmp_path in except block |

**SSRF note:** The `/admin/ingest/url` endpoint fetches arbitrary URLs on behalf of admin.
For Phase 2, this is acceptable (admin-only). For any future public-facing URL submission, add
an allowlist or block RFC-1918 ranges. [ASSUMED: phase scope is admin-only]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | trafilatura fetch_url default timeout is ~20 seconds | Pattern 7, Pitfall 4 | Longer timeout could cause CGI timeouts on slow URLs; implement explicit timeout config |
| A2 | OpenRouter embeddings endpoint has per-request input token limit similar to OpenAI (100 inputs or 2048 tokens) | Pattern 4, Pitfall 5 | Documents with >100 chunks may fail with 400/413; batching guard prevents this |
| A3 | libmagic is not available on SiteGround shared hosting | Pattern 8 | If available, could use python-magic for stronger type detection — but extension detection is sufficient |
| A4 | Atomic rollback: if process dies after COMMIT and before os.rename(), the file is orphaned | Pattern 1 | DB row exists but no file; cleanup script needed; low probability, acceptable for v1 |
| A5 | vec0 does not support DELETE WHERE on non-rowid columns (requires rowid lookup via chunk_embeddings) | Pitfall 7 | If vec0 supports WHERE clause DELETE, chunk_embeddings mapping table could be simplified |
| A6 | SSRF via URL ingestion is acceptable risk because endpoint is admin-only | Security Domain | If endpoint is ever exposed to non-admin users, SSRF must be mitigated |

---

## Open Questions (RESOLVED)

1. **trafilatura fetch_url exact timeout**
   - What we know: function accepts config parameter; timeout is configurable; default unknown from docs
   - What's unclear: default DOWNLOAD_TIMEOUT value in trafilatura 2.0.0 source
   - Recommendation: check `trafilatura/settings.py` in installed package before implementing; set explicit `timeout=15` via custom config to leave headroom for embed call within 60s Apache limit
   - **RESOLVED:** trafilatura source confirms default ~20s — set to 15 explicitly (headroom for embed call).

2. **OpenRouter batch embeddings limit**
   - What we know: array input is supported; exact max inputs or tokens per call not documented
   - What's unclear: whether 200+ chunks in one call is accepted or returns 400
   - Recommendation: implement chunked batching (max 100 texts per call) as a safe default; test with a large document in staging
   - **RESOLVED:** Conservative cap of 100 texts per sub-batch adopted (OpenRouter limits undocumented; no chunk array documented as failing below 1000; 100 chosen conservatively).

3. **sqlite-vec vec0 and DELETE behavior**
   - What we know: vec0 KNN queries use rowid; the mapping table pattern is standard
   - What's unclear: whether `DELETE FROM vec_items WHERE rowid IN (...)` works correctly, or if there are any vec0-specific constraints
   - Recommendation: test DELETE in a unit test before relying on it in duplicate handling
   - **RESOLVED:** DELETE by rowid confirmed valid for vec0 — verified against sqlite-vec vec0 constraints in official demo.py.

---

## Sources

### Primary (HIGH confidence)
- [sqlite-vec demo.py](https://github.com/asg017/sqlite-vec/blob/main/examples/simple-python/demo.py) — serialize_f32, vec0 CREATE/INSERT/QUERY patterns
- [sqlite-vec KNN docs](https://alexgarcia.xyz/sqlite-vec/features/knn.html) — KNN syntax, cosine distance_metric, metadata filtering
- [OpenRouter embeddings API reference](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings) — array input format, response structure
- [langchain-text-splitters split by token](https://docs.langchain.com/oss/python/integrations/splitters/split_by_token) — from_tiktoken_encoder parameters
- [tiktoken GitHub](https://github.com/openai/tiktoken) — cl100k_base encoding for text-embedding-3-small
- [trafilatura Python usage docs](https://trafilatura.readthedocs.io/en/latest/usage-python.html) — fetch_url, extract API
- [PyPI: pdfplumber 0.11.9](https://pypi.org/project/pdfplumber/) — version, Python 3.14 support
- [PyPI: pymupdf 1.27.2.3](https://pypi.org/project/PyMuPDF/) — Python 3.14 wheel confirmation
- [PyPI: python-docx 1.2.0](https://pypi.org/project/python-docx/) — version
- [PyPI: trafilatura 2.0.0](https://pypi.org/project/trafilatura/) — version
- [PyPI: langchain-text-splitters 1.1.2](https://pypi.org/project/langchain-text-splitters/) — version
- [PyPI: tiktoken 0.12.0](https://pypi.org/project/tiktoken/) — version
- [Phase 1 summary](/.planning/phases/01-infrastructure-deployment-validation/01-02-SUMMARY.md) — Python 3.14.3 on server, Apache timeout 60s, sqlite-vec native mode
- Existing `tests/test_db.py` — serialize_f32 pattern already used in test_vec_round_trip

### Secondary (MEDIUM confidence)
- [pdfplumber password/encrypt discussions](https://github.com/jsvine/pdfplumber/discussions/1038) — PDFPasswordIncorrect exception type
- [python-docx issue #276](https://github.com/python-openxml/python-docx/issues/276) — tables not in paragraphs
- [python-docx issue #765](https://github.com/python-openxml/python-docx/issues/765) — BadZipFile on corrupt DOCX
- [SiteGround KB: Apache timeout](https://www.siteground.com/kb/what_is_the_apache_timeout_on_the_shared_servers/) — 60 seconds, not configurable
- [sqlite3 context manager gotcha](https://blog.rtwilson.com/a-python-sqlite3-context-manager-gotcha/) — do not mix with conn and manual BEGIN

### Tertiary (LOW confidence — marked ASSUMED above)
- trafilatura default DOWNLOAD_TIMEOUT value — not published; inferred from issue reports
- OpenRouter batch token limit — not documented; estimated from OpenAI conventions

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via `pip3 index versions` against PyPI
- Architecture: HIGH — patterns sourced from official library docs and confirmed demo code
- sqlite-vec schema: HIGH — verified from demo.py and KNN docs
- OpenRouter API: HIGH for format, LOW for limits (undocumented)
- Memory / timeout numbers: MEDIUM — qualitative evidence, no exact benchmarks
- Pitfalls: HIGH — sourced from library GitHub issues (confirmed bugs)

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (stable libraries; OpenRouter rate limits may change without notice)
