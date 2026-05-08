# Technology Stack

**Project:** DocChat RAG Pipeline
**Researched:** 2026-05-07
**Confidence:** HIGH (all critical decisions verified against official sources and community evidence)

---

## Decision Summary (TL;DR)

| Layer | Decision | Rationale |
|-------|----------|-----------|
| Web framework | **Flask** | Native WSGI — drops straight into Passenger with zero workarounds |
| Vector DB | **sqlite-vec** | Pure C extension, prebuilt Linux wheels, ~0 RAM overhead vs ChromaDB's HNSW-in-RAM requirement |
| PDF parsing | **PyMuPDF (pymupdf)** | Fastest, most consistent across doc types, pure pip install |
| DOCX parsing | **python-docx** | De-facto standard, no alternatives worth considering |
| URL scraping | **trafilatura** | Highest F1 accuracy, actively maintained, no errors on malformed HTML |
| LLM | **google/gemma-3-27b-it:free** (primary) + **qwen/qwen3-next-80b-a3b-instruct:free** (fallback) | Free, 128K–262K context, RAG-appropriate, proven quality |
| Embeddings | **OpenAI text-embedding-3-small via OpenRouter** | No RAM cost, 1536-dim, $0.02/M tokens — trivially cheap at <100 q/day |

---

## Recommended Stack

### Core Framework: Flask

**Chosen over:** FastAPI

FastAPI is ASGI-native. Passenger WSGI (used by SiteGround's cPanel Python Selector) is a WSGI interface. The two are not directly compatible. The only way to run FastAPI on Passenger is to spin a background Uvicorn process and reverse-proxy to it via `.htaccess` — a brittle approach that dies when the terminal closes and has no automatic process resurrection on shared hosting.

Flask is a native WSGI app. Deployment to Passenger is a two-file operation:

```python
# passenger_wsgi.py
from app import app as application
```

Flask's memory footprint is ~50–60 MB, which is well within shared hosting limits. At <100 queries/day there is no performance argument for FastAPI's async throughput.

| | Flask | FastAPI |
|---|---|---|
| Passenger WSGI compat | Native — zero config | Requires Uvicorn workaround; unreliable on shared hosting |
| RAM footprint | ~50–60 MB | ~80–100 MB + Uvicorn process |
| Async benefit at <100 req/day | None | None |
| Deployment risk | Low | HIGH — process management problem on shared hosting |

**Version:** `Flask>=3.0,<4`
**Versions to also install:** `Werkzeug>=3.0` (auto-pulled by Flask)

---

### Vector Database: sqlite-vec

**Chosen over:** ChromaDB, FAISS, LanceDB

This is the most consequential decision for shared hosting viability.

**ChromaDB disqualifier:** ChromaDB's core index (HNSW via chroma-hnswlib) requires a C++ compiler to build from source if prebuilt wheels are absent, and the HNSW index must reside entirely in RAM to function. For a corpus of N million 1536-dim vectors, RAM requirement is roughly `N / 0.245` GB. More critically, SiteGround's shared hosting uses per-process RAM caps (typically 512–768 MB total per process including Python interpreter and all libraries). ChromaDB loads its full HNSW index into RAM on startup — on a small corpus this is acceptable, but combined with PyTorch/sentence-transformers it exceeds shared hosting limits. Multiple GitHub issues confirm installation failures without build tools.

**FAISS disqualifier:** FAISS is an index library, not a database. It has no persistence layer — save/load must be implemented manually. It also requires native compilation. Not suitable for this context.

**LanceDB consideration:** LanceDB supports disk-based indexes (does not require full index in RAM), is pip-installable, and uses the Lance columnar format for efficient disk operations. It is a strong second choice. However, sqlite-vec edges it out because:
  - sqlite-vec ships prebuilt manylinux wheels (glibc 2.17+ x86-64) — guaranteed pip-only install with zero compilation
  - sqlite-vec piggybacks on Python's built-in `sqlite3` module — no additional binary runtime needed
  - For a corpus of <10K chunks (realistic for a business site), sqlite-vec's linear scan or simple ANN index is perfectly fast
  - The entire vector store is a single `.db` file — trivially backed up, moved, and versioned

**sqlite-vec specifics:**
- Install: `pip install sqlite-vec` — prebuilt wheels, no C++ compiler needed
- Requires SQLite ≥ 3.41 (check SiteGround's Python environment; most modern Linux systems have 3.40+; if not, use `pysqlite3-binary` as a drop-in)
- RAM: Only vectors you explicitly query are loaded; no full-index-in-RAM requirement
- Persistence: Single SQLite `.db` file
- LangChain integration: `langchain-community` includes `SQLiteVecVectorStore`

```python
import sqlite3
import sqlite_vec

db = sqlite3.connect("vectors.db")
sqlite_vec.load(db)
db.enable_load_extension(False)  # security: lock after loading
```

**Version:** `sqlite-vec>=0.1.6` (stable release; check PyPI for latest)

---

### Embeddings: text-embedding-3-small via OpenRouter API

**Chosen over:** sentence-transformers (local)

sentence-transformers/all-MiniLM-L6-v2 is genuinely lightweight (~80 MB download, ~43 MB model weights in FP16). However, loading it requires PyTorch, which adds ~200–400 MB of additional RAM to the process. On shared hosting with a ~512–768 MB per-process limit, PyTorch + Flask + sqlite-vec + PyMuPDF leaves no headroom and risks OOM kills on document ingestion.

OpenRouter now supports an embeddings endpoint (`POST /api/v1/embeddings`) accepting OpenAI-compatible requests. `text-embedding-3-small` costs $0.02 per million input tokens. At <100 queries/day with ~500 tokens per query, monthly embedding cost is under $0.01. For document ingestion (one-time per document), the cost is similarly negligible.

The embedding call is made at query time and at document upload time — both are admin or user-triggered, never concurrent, so API latency (~100–200 ms) is acceptable.

```python
import openai

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

response = client.embeddings.create(
    model="openai/text-embedding-3-small",
    input=text_chunks,
)
embeddings = [item.embedding for item in response.data]
```

**Dimensions:** 1536 (default) — compatible with sqlite-vec
**Version:** `openai>=1.0` (used as the OpenRouter client; OpenRouter is OpenAI-API-compatible)

---

### LLM: google/gemma-3-27b-it:free (primary)

**Fallback:** qwen/qwen3-next-80b-a3b-instruct:free

**Context window:** 131,072 tokens (Gemma 3 27B) / 262,144 tokens (Qwen3 Next 80B)
**Cost:** $0 per token on free tier
**Rate limit:** ~20 requests/minute, ~200 requests/day per model on OpenRouter free tier

Gemma 3 27B is released March 2025 by Google, available free on OpenRouter. It supports structured outputs, function calling, and 140+ languages. The 128K context window comfortably holds retrieved chunks plus conversation history. For a consulting business chatbot, Gemma 3 27B provides coherent, well-formatted responses and follows instructions reliably.

The Qwen3 Next 80B A3B model is flagged as explicitly RAG-optimized by Alibaba/Qwen documentation, with a 262K context window. It serves as the fallback when Gemma is rate-limited or unavailable.

**Rate limit strategy:** At <100 queries/day the 200/day limit is not a concern. However, implement a simple in-memory per-model request counter to switch between primary and fallback if the primary hits its daily cap.

```python
# In passenger_wsgi.py / config
LLM_PRIMARY = "google/gemma-3-27b-it:free"
LLM_FALLBACK = "qwen/qwen3-next-80b-a3b-instruct:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
```

---

### PDF Parsing: PyMuPDF (pymupdf)

**Chosen over:** pdfplumber

PyMuPDF consistently outperforms pdfplumber in extraction speed (0.12s vs 0.10s for simple docs, but PyMuPDF wins on complex layouts) and shows the most consistent recall across document categories in 2025 benchmarks. For a consulting business uploading proposal PDFs, contracts, and case studies, PyMuPDF's layout-aware extraction is more reliable.

pdfplumber's advantage is table extraction precision — but for RAG chunk ingestion, table data is typically converted to text anyway, and the RAG use case does not require preserving tabular structure.

PyMuPDF installs as a pure Python wheel with prebuilt binaries:

```bash
pip install pymupdf
```

No native compilation required. Provides `fitz` as the import name.

```python
import fitz  # PyMuPDF

def extract_pdf_text(path: str) -> str:
    doc = fitz.open(path)
    return "\n".join(page.get_text() for page in doc)
```

**Version:** `pymupdf>=1.24`

---

### DOCX Parsing: python-docx

No meaningful alternative. The de-facto standard for `.docx` extraction in Python. Pure Python, pip-installable, no native dependencies.

```bash
pip install python-docx
```

```python
from docx import Document

def extract_docx_text(path: str) -> str:
    doc = Document(path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
```

**Version:** `python-docx>=1.1`

---

### URL Crawling: trafilatura

**Chosen over:** newspaper3k, beautifulsoup4 + requests

trafilatura achieves F1 of 0.945 vs newspaper3k's 0.912 in independent benchmarks, and newspaper3k raises errors on malformed HTML (common in real-world sites). trafilatura is actively maintained; newspaper3k has had intermittent maintenance gaps.

trafilatura handles both downloading and content extraction in one call, with built-in language detection, boilerplate removal, and respect for `robots.txt`.

```bash
pip install trafilatura
```

```python
import trafilatura

def crawl_url(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    return trafilatura.extract(downloaded)  # returns None if extraction fails
```

**Version:** `trafilatura>=1.12`

---

## Full requirements.txt

```
# Web framework
Flask>=3.0,<4
Werkzeug>=3.0

# Vector store
sqlite-vec>=0.1.6

# LLM + embeddings client (OpenRouter is OpenAI-API-compatible)
openai>=1.0

# Document parsing
pymupdf>=1.24
python-docx>=1.1
trafilatura>=1.12

# RAG utilities (chunking, token counting)
langchain-text-splitters>=0.2
tiktoken>=0.7

# Admin auth (password-protect admin UI)
Flask-HTTPAuth>=4.8
```

Note: Do NOT add `torch`, `transformers`, or `sentence-transformers` — these pull in PyTorch and will exceed shared hosting RAM limits.

---

## Installation Notes for SiteGround cPanel Python Selector

1. Use cPanel Python Selector to create a Python 3.11+ virtual environment in the app directory.
2. Set the "Application startup file" to `passenger_wsgi.py`.
3. In the virtualenv, run `pip install -r requirements.txt`. All packages listed above have prebuilt Linux manylinux wheels — no C++ compiler is needed.
4. If `sqlite3` on the host system is older than 3.41, add `pysqlite3-binary` to requirements and patch the import:
   ```python
   # At top of app, before any sqlite_vec import
   import pysqlite3
   import sys
   sys.modules["sqlite3"] = pysqlite3
   ```
5. Store `vectors.db` and uploaded documents inside the app directory (writable by Passenger process). Do not store in `/tmp` — it may be cleared between process restarts.

---

## Alternatives Considered

| Category | Chosen | Rejected | Reason Rejected |
|----------|--------|----------|-----------------|
| Framework | Flask | FastAPI | FastAPI is ASGI; Passenger is WSGI — incompatible without unreliable workaround |
| Vector DB | sqlite-vec | ChromaDB | ChromaDB HNSW index loads entirely into RAM; build deps require C++ compiler on some environments |
| Vector DB | sqlite-vec | LanceDB | LanceDB is a strong second; sqlite-vec wins on installation simplicity and single-file persistence |
| Vector DB | sqlite-vec | FAISS | No persistence layer; requires native compilation |
| Embeddings | OpenRouter API | sentence-transformers | PyTorch RAM footprint (~400 MB) would exhaust shared hosting limits |
| PDF | PyMuPDF | pdfplumber | PyMuPDF faster and more consistent across document types for text extraction |
| URL scraping | trafilatura | newspaper3k | trafilatura higher accuracy, better error handling on malformed HTML, actively maintained |

---

## Sources

- [Phusion Passenger Python quickstart — native WSGI support](https://www.phusionpassenger.com/library/walkthroughs/start/python.html)
- [FastAPI on cPanel — unreliable workaround via Uvicorn background process](https://dev.to/cmanish049/how-to-deploy-fastapi-on-shared-hosting-cpanel-7ch)
- [ChromaDB RAM model: HNSW must reside fully in system RAM](https://cookbook.chromadb.dev/core/resources/)
- [ChromaDB chroma-hnswlib build failures without C++ compiler](https://github.com/chroma-core/chroma/issues/1122)
- [sqlite-vec stable release v0.1.0 announcement](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html)
- [sqlite-vec Python usage guide](https://alexgarcia.xyz/sqlite-vec/python.html)
- [sqlite-vec PyPI page — prebuilt manylinux wheels confirmed](https://pypi.org/project/sqlite-vec/)
- [OpenRouter Embeddings API documentation](https://openrouter.ai/docs/api/reference/embeddings)
- [OpenRouter free models collection (as of 2026-05)](https://openrouter.ai/collections/free-models)
- [Gemma 3 27B on OpenRouter](https://openrouter.ai/google/gemma-3-27b-it:free)
- [Qwen3 Next 80B A3B (free) on OpenRouter](https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free)
- [PyMuPDF vs pdfplumber 2025 benchmark](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257)
- [Trafilatura accuracy evaluation](https://trafilatura.readthedocs.io/en/latest/evaluation.html)
- [Trafilatura vs newspaper3k comparison](https://webscraping.fyi/lib/compare/python-newspaper-vs-python-trafilatura/)
- [sentence-transformers/all-MiniLM-L6-v2 RAM requirements discussion](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/discussions/22)
- [SQLite vs Chroma comparative analysis](https://dev.to/stephenc222/sqlite-vs-chroma-a-comparative-analysis-for-managing-vector-embeddings-4i76)
