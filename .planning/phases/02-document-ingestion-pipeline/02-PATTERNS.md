# Phase 2: Document Ingestion Pipeline - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 9 new/modified files
**Analogs found:** 7 / 9 (2 files are new with no direct role analog — use RESEARCH.md patterns)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/db.py` | model/config | CRUD | `app/db.py` itself (extend) | exact — same file |
| `app/__init__.py` | config | request-response | `app/__init__.py` itself (extend) | exact — same file |
| `app/routes/ingest.py` | controller | request-response | `app/routes/health.py` | role-match |
| `app/services/ingestion.py` | service | file-I/O + request-response | `app/routes/health.py` (partial) | partial — no service layer exists yet |
| `app/ingest/parser.py` | utility | file-I/O | `app/routes/health.py` (partial) | partial — no utility layer exists yet |
| `app/ingest/chunker.py` | utility | transform | none | no analog |
| `app/ingest/embedder.py` | utility | request-response | `app/routes/health.py` (partial) | partial |
| `tests/test_ingest_upload.py` | test | request-response | `tests/test_health.py` | role-match |
| `requirements.txt` | config | — | `requirements.txt` itself (extend) | exact — same file |

---

## Pattern Assignments

### `app/db.py` — extend with document/chunk/vector tables

**Analog:** `app/db.py` (lines 1–57 — full file, extend do not replace)

**Existing imports pattern** (`app/db.py` lines 1–3):
```python
import os
import sqlite3
import flask
```

**Existing _open_db() pattern** (`app/db.py` lines 6–14) — ALL new DB code calls this, never raw `sqlite3.connect()`:
```python
def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  # 10 000 ms = 10 seconds
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn
```

**Existing init_db() pattern** (`app/db.py` lines 40–57) — new `init_document_tables(conn)` follows the same call structure, invoked from `init_db()` after `_load_sqlite_vec()`:
```python
def init_db(app: flask.Flask) -> None:
    storage_path = app.config['STORAGE_PATH']
    os.makedirs(storage_path, exist_ok=True)
    db_path = os.path.join(storage_path, 'dochat.db')
    conn = _open_db(db_path)
    mode = _load_sqlite_vec(conn)
    app.config['DB_CONN'] = conn
    app.config['SQLITE_VEC_MODE'] = mode
    app.config['DB_PATH'] = db_path
```

**New function to add — `init_document_tables(conn)`** (from RESEARCH.md Pattern 2 / Code Examples):
```python
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

**Critical:** `distance_metric=cosine` MUST be specified at CREATE time. Omitting it defaults to L2 — Phase 3 cosine threshold will break silently.

**Transaction pattern** — for all DB writes in Phase 2, use manual BEGIN/COMMIT/ROLLBACK, NOT `with conn:`. Mixing them causes `sqlite3.OperationalError: cannot start a transaction within a transaction` (RESEARCH.md Pitfall 6):
```python
# CORRECT — manual transaction
conn.execute("BEGIN")
# ... INSERTs ...
conn.execute("COMMIT")

# WRONG — never combine with conn.execute("BEGIN")
with conn:
    conn.execute("INSERT ...")
```

---

### `app/__init__.py` — register ingest_bp

**Analog:** `app/__init__.py` (lines 1–18 — full file, extend)

**Existing pattern** (`app/__init__.py` lines 1–18):
```python
import os
from flask import Flask
from .db import init_db
from .routes.health import health_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    # os.path.expanduser is required — Python does not auto-expand ~ in strings.
    app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')
    init_db(app)
    app.register_blueprint(health_bp)
    return app
```

**Change required — add two lines** (import + register, matching the health_bp pattern exactly):
```python
from .routes.ingest import ingest_bp   # add after health_bp import
# ...
app.register_blueprint(ingest_bp)       # add after health_bp register
```

**Storage path rule** (`app/__init__.py` line 12): always `os.path.expanduser('~/dochat/storage')` — never hardcode `/home/customer/`. All new paths derive from `app.config['STORAGE_PATH']`.

---

### `app/routes/ingest.py` — POST /admin/ingest/upload and POST /admin/ingest/url

**Analog:** `app/routes/health.py` (lines 1–47 — full file)

**Blueprint declaration pattern** (`app/routes/health.py` lines 1–4):
```python
import os
from flask import Blueprint, jsonify, current_app

health_bp = Blueprint('health', __name__)
```

**Adapt for ingest:**
```python
from flask import Blueprint, request, jsonify, current_app
from ..services.ingestion import ingest_file, ingest_url
from ..auth import require_auth

ingest_bp = Blueprint('ingest', __name__)
```

**URL prefix pattern** — the health blueprint uses no prefix. The ingest blueprint should declare routes with the full path to match `.htaccess` rewrite rules (D-10):
```python
@ingest_bp.route('/admin/ingest/upload', methods=['POST'])
@require_auth
def upload():
    ...

@ingest_bp.route('/admin/ingest/url', methods=['POST'])
@require_auth
def url_ingest():
    ...
```

**Config access pattern** (`app/routes/health.py` lines 8–9) — access app config via `current_app.config`, not a module-level reference:
```python
storage_path = current_app.config.get('STORAGE_PATH', '')
conn = current_app.config.get('DB_CONN')
```

**Error response pattern** (`app/routes/health.py` lines 13–20) — try/except, never expose stack traces:
```python
try:
    # operation
    storage_ok = True
except OSError:
    storage_ok = False
```

**Adapt for ingest 422/413 responses:**
```python
try:
    result = ingest_file(conn, storage_path, file_bytes, filename)
    return jsonify(result), 200
except ValueError as e:
    return jsonify({"error": str(e), "filename": filename}), 422
except Exception:
    return jsonify({"error": "Internal server error", "filename": filename}), 500
```

**File size gate** (D-03, before any processing):
```python
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
file = request.files.get('file')
if file is None:
    return jsonify({"error": "No file field in request"}), 400
file_bytes = file.read()
if len(file_bytes) > MAX_FILE_BYTES:
    return jsonify({"error": "File exceeds 10 MB limit", "filename": file.filename}), 413
```

**Security note:** Never use `file.filename` directly in file paths. Use `doc_id`-based paths; apply `os.path.basename()` if the filename is stored as metadata only (RESEARCH.md Security Domain).

---

### `app/services/ingestion.py` — orchestrate parse + chunk + embed + store

**No direct role analog in codebase** — this is the first service-layer file. Use RESEARCH.md Pattern 1 (atomic rollback) as the primary structural guide.

**Import pattern** — follow the style of `app/db.py` (stdlib first, then third-party):
```python
import os
import uuid
import struct
import sqlite3
from datetime import datetime, timezone
```

**Storage path pattern** (from `app/__init__.py` line 12 and CONTEXT.md D-09) — all paths derived from the passed-in `storage_path` parameter (which comes from `current_app.config['STORAGE_PATH']`):
```python
tmp_dir = os.path.join(storage_path, 'tmp')
final_dir = os.path.join(storage_path, 'uploads', doc_id)
os.makedirs(tmp_dir, exist_ok=True)
```

**Atomic rollback pattern** (RESEARCH.md Pattern 1) — write temp, commit DB, rename last:
```python
tmp_path = os.path.join(tmp_dir, f"{doc_id}{ext}")
final_path = os.path.join(final_dir, f"original{ext}")

with open(tmp_path, 'wb') as f:
    f.write(file_bytes)

try:
    conn.execute("BEGIN")
    # ... INSERT documents, chunks, vec_items, chunk_embeddings ...
    conn.execute("COMMIT")
    os.makedirs(final_dir, exist_ok=True)
    os.rename(tmp_path, final_path)
except Exception:
    conn.execute("ROLLBACK")
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise
```

**Secrets pattern** (from `app.cgi` and `passenger_wsgi.py`) — always `os.environ.get('KEY')`, never hardcoded:
```python
api_key = os.environ.get('OPENROUTER_API_KEY', '')
```

**Duplicate-replace delete sequence** (RESEARCH.md Pitfall 7) — vec0 only supports DELETE by rowid, NOT by foreign key column:
```python
# 1. Look up vec rowids for existing doc's chunks
rows = conn.execute(
    "SELECT vec_rowid FROM chunk_embeddings WHERE chunk_id IN "
    "(SELECT id FROM chunks WHERE doc_id = ?)", [existing_doc_id]
).fetchall()
# 2. Delete from vec_items by rowid
for (vec_rowid,) in rows:
    conn.execute("DELETE FROM vec_items WHERE rowid = ?", [vec_rowid])
# 3. Delete mapping, chunks, document rows, then file
conn.execute("DELETE FROM chunk_embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)", [existing_doc_id])
conn.execute("DELETE FROM chunks WHERE doc_id = ?", [existing_doc_id])
conn.execute("DELETE FROM documents WHERE id = ?", [existing_doc_id])
```

**vec_items serialize pattern** (from `tests/test_db.py` lines 64–67 — already used in codebase):
```python
import struct

def serialize_f32(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)
```

---

### `app/ingest/parser.py` — PDF/DOCX/TXT/MD text extraction

**No direct role analog** — first utility module. Follow `app/db.py` structure: module-level helpers, no Flask imports, no side effects at import time.

**Module structure pattern** (adapted from `app/db.py` lines 1–14):
```python
# stdlib imports first
import io
import os
import zipfile

# third-party imports second
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from docx import Document
import trafilatura
```

**Error convention** — raise `ValueError` with a human-readable message; let the caller (service layer) catch and translate to HTTP response. Never raise HTTPException from a utility module:
```python
def parse_pdf(file_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            texts = [page.extract_text() for page in pdf.pages if page.extract_text()]
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

**DOCX table extraction** (RESEARCH.md Pattern 6 — Pitfall 2: `doc.paragraphs` alone misses tables):
```python
def parse_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise ValueError("DOCX file is corrupt or not a valid Word document")
    except Exception as e:
        raise ValueError(f"DOCX parsing failed: {e}")

    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    # MUST also iterate tables — they are not included in doc.paragraphs
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

**TXT/MD pattern** — no library, open() utf-8:
```python
def parse_text(file_bytes: bytes) -> str:
    try:
        full_text = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        full_text = file_bytes.decode('latin-1', errors='replace')
    if not full_text.strip():
        raise ValueError("File contains no text content")
    return full_text
```

**File type dispatch** (RESEARCH.md Pattern 8):
```python
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}

def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    return ext.lstrip('.')
```

---

### `app/ingest/chunker.py` — RecursiveCharacterTextSplitter wrapping

**No analog in codebase.** Follow the `app/db.py` pure-function module style (no Flask, no side effects).

**Core pattern** (RESEARCH.md Pattern 3):
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str) -> list[str]:
    if not text.strip():
        raise ValueError("Cannot chunk empty text")
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=512,
        chunk_overlap=100,
    )
    chunks = splitter.split_text(text)
    chunks = [c for c in chunks if c.strip()]
    if not chunks:
        raise ValueError("Document produced no chunks after splitting")
    return chunks
```

**Key:** `from_tiktoken_encoder` counts tokens, not characters. `chunk_size=512` means 512 tokens, not characters. Using plain `RecursiveCharacterTextSplitter(chunk_size=512)` would count characters — wrong.

---

### `app/ingest/embedder.py` — OpenRouter batch embedding call

**No direct analog.** Closest pattern: `app/routes/health.py` lines 22–31 show the project's try/except pattern and use of `current_app.config`. However, the embedder is a pure utility (not a route), so follow `app/db.py` module style instead.

**Core pattern** (RESEARCH.md Pattern 4 — confirmed OpenRouter API):
```python
import os
import requests

def embed_chunks(chunk_texts: list[str]) -> list[list[float]]:
    if not chunk_texts:
        raise ValueError("Cannot embed empty chunk list")
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/text-embedding-3-small",
            "input": chunk_texts,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    embeddings = sorted(data["data"], key=lambda x: x["index"])
    return [e["embedding"] for e in embeddings]
```

**Batching guard** — if `len(chunk_texts) > 100`, split into sub-batches of 100 and concatenate results (RESEARCH.md Pitfall 5). The single-call path is the no-op case for typical documents (< 50 chunks).

**Secrets access pattern** (from `app.cgi` lines 6–8 and `passenger_wsgi.py` lines 9–10): `os.environ.get('OPENROUTER_API_KEY', '')` — never import from a config object, always from env.

---

### `tests/test_ingest_upload.py` — integration tests for upload endpoint

**Analog:** `tests/test_health.py` (lines 1–37 — full file) and `tests/conftest.py` (lines 1–32 — full file)

**Test file structure pattern** (`tests/test_health.py` lines 1–10):
```python
import json

def test_health_returns_json(client):
    """GET /health must return a JSON response — covers INFRA-01."""
    response = client.get('/health')
    assert response.content_type == 'application/json'
```

**Adapt for ingest tests:**
```python
import io
import json
import pytest

def test_upload_pdf_returns_doc_id(client, mocker):
    """POST /admin/ingest/upload with valid PDF returns doc_id — covers INGEST-01."""
    mocker.patch('app.services.ingestion.embed_chunks', return_value=[[0.1] * 1536])
    data = {'file': (io.BytesIO(b'%PDF-1.4 fake'), 'test.pdf')}
    response = client.post(
        '/admin/ingest/upload',
        data=data,
        content_type='multipart/form-data',
        headers={'Authorization': 'Basic dGVzdDp0ZXN0LXBhc3N3b3Jk'}  # test:test-password
    )
    body = json.loads(response.data)
    assert 'doc_id' in body
```

**App fixture pattern** (`tests/conftest.py` lines 4–27) — already sets `OPENROUTER_API_KEY` and `ADMIN_PASSWORD`, no change needed:
```python
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-do-not-use-in-prod')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-password')
    # patches STORAGE_PATH to tmp_path/storage ...
```

**Mock OpenRouter pattern** (RESEARCH.md Validation Architecture / Mock Strategy):
```python
def test_embed_batch_calls_once(mocker, app):
    mock_post = mocker.patch('app.ingest.embedder.requests.post')
    mock_post.return_value.json.return_value = {
        "data": [{"embedding": [0.1] * 1536, "index": i} for i in range(3)]
    }
    mock_post.return_value.raise_for_status = lambda: None

    from app.ingest.embedder import embed_chunks
    result = embed_chunks(["chunk1", "chunk2", "chunk3"])

    assert mock_post.call_count == 1
```

**No-stack-trace pattern** (from `tests/test_health.py` lines 34–37) — apply to all error response tests:
```python
def test_upload_corrupt_pdf_no_stack_trace(client):
    response = client.post(...)
    body = response.data.decode()
    assert 'Traceback' not in body
    assert 'File "' not in body
```

---

### `requirements.txt` — add new dependencies

**Analog:** `requirements.txt` (lines 1–4 — full file, extend)

**Existing format** (`requirements.txt` lines 1–4):
```
flask==3.1.3
sqlite-vec==0.1.9
python-dotenv==1.2.2
pytest==8.3.5
```

**Lines to append** (exact versions from RESEARCH.md Standard Stack):
```
pdfplumber==0.11.9
python-docx==1.2.0
trafilatura==2.0.0
langchain-text-splitters==1.1.2
tiktoken==0.12.0
pytest-mock==3.15.1
```

**Never add:** `torch`, `transformers`, `sentence-transformers`, `PyMuPDF`, `python-magic` — OOM kill risk or libmagic availability unknown on SiteGround (CLAUDE.md Hard Rules + RESEARCH.md Alternatives Considered).

---

## Shared Patterns

### Storage Path Construction
**Source:** `app/__init__.py` line 12, `app/db.py` lines 48–51
**Apply to:** `app/routes/ingest.py`, `app/services/ingestion.py`

```python
# In create_app() — the canonical source of truth
app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')

# In route handlers — access via current_app, never reconstruct
storage_path = current_app.config['STORAGE_PATH']

# In service layer — accept as parameter, never reconstruct
def ingest_file(conn, storage_path, file_bytes, filename): ...
```

Never call `os.path.expanduser('~/dochat/storage')` outside of `create_app()`. Never hardcode `/home/customer/`.

### Secrets Access
**Source:** `app.cgi` lines 6–8, `passenger_wsgi.py` lines 9–10, `app/__init__.py` line 10
**Apply to:** `app/routes/ingest.py`, `app/ingest/embedder.py`, `app/auth.py`

```python
# Pattern from passenger_wsgi.py — load_dotenv before any import
from dotenv import load_dotenv
load_dotenv(os.path.join(APP_DIR, '.env'))

# Pattern from app/__init__.py line 10 — os.environ[] for required, .get() for optional
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']           # required — raises KeyError if missing
api_key = os.environ.get('OPENROUTER_API_KEY', '')            # optional — returns '' if missing
```

### Error Response Format
**Source:** `app/routes/health.py` lines 34–47 (jsonify pattern)
**Apply to:** `app/routes/ingest.py`

```python
# Success
return jsonify({"status": "ok", ...}), 200

# Error — never expose stack traces
return jsonify({"error": "human-readable message", "filename": filename}), 422

# JSON content type — always jsonify(), never json.dumps()
```

### Test Client Access Pattern
**Source:** `tests/conftest.py` lines 30–32, `tests/test_health.py` lines 4–6
**Apply to:** `tests/test_ingest_upload.py`, `tests/test_ingest_url.py`, `tests/test_ingestion_service.py`

```python
# conftest.py already provides app and client fixtures — import not needed in test files
def test_something(client):       # uses conftest client fixture
    response = client.get('/health')

def test_something_else(app):     # uses conftest app fixture for direct DB/config access
    conn = app.config['DB_CONN']
```

### DB Connection Access
**Source:** `app/routes/health.py` lines 25–27
**Apply to:** `app/routes/ingest.py`

```python
conn = current_app.config.get('DB_CONN')
# Always use the shared connection from app.config — never open a new connection in a route
```

### Auth Stub Decorator
**Source:** RESEARCH.md Code Examples (HTTP Basic Auth stub — standard Flask pattern, no codebase analog yet)
**Apply to:** `app/routes/ingest.py` (all endpoints), place decorator in `app/auth.py`

```python
import os
import functools
from flask import request, Response

def require_auth(f):
    """Stub auth decorator. Phase 4 replaces with full implementation."""
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

## No Analog Found

Files with no close match in the codebase (planner uses RESEARCH.md patterns directly):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/ingest/chunker.py` | utility | transform | No text-splitting utilities exist yet; use RESEARCH.md Pattern 3 exactly |
| `app/ingest/embedder.py` | utility | request-response | No external API call utilities exist; use RESEARCH.md Pattern 4 exactly |
| `app/auth.py` | middleware | request-response | No auth layer exists; use RESEARCH.md Code Examples (HTTP Basic Auth stub) |

---

## Anti-Patterns to Avoid

These are confirmed pitfalls for this specific codebase:

| Anti-Pattern | Where It Bites | Correct Pattern |
|---|---|---|
| `with conn:` mixed with `conn.execute("BEGIN")` | `app/services/ingestion.py` | Use only manual BEGIN/COMMIT/ROLLBACK — see `app/db.py` style |
| `os.path.expanduser('~/dochat/storage')` outside `create_app()` | Any new file | Derive paths from `app.config['STORAGE_PATH']` only |
| `sqlite3.connect(...)` in route or service | Any new file | Always call `app/db.py:_open_db()` or use `current_app.config['DB_CONN']` |
| `request.files['file'].filename` in file paths | `app/routes/ingest.py` | Use `doc_id`-based paths; `os.path.basename()` for display only |
| `vec0` CREATE without `distance_metric=cosine` | `app/db.py:init_document_tables()` | Always include — Phase 3 cosine threshold is incompatible with L2 |
| `doc.paragraphs` without `doc.tables` | `app/ingest/parser.py` | Always iterate both — tables are not in paragraphs (OOXML structure) |
| `embed_chunks([])` with empty list | `app/services/ingestion.py` | Check `if not chunks: raise ValueError(...)` after chunking |

---

## Metadata

**Analog search scope:** `app/`, `tests/`
**Files scanned:** 10 (all Python files in project)
**Pattern extraction date:** 2026-05-08
