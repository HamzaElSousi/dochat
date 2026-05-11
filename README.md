# DocChat — Embeddable RAG Chatbot for Shared Hosting

A production-ready Retrieval-Augmented Generation (RAG) chatbot built to run inside the hard constraints of SiteGround shared hosting. Visitors ask questions; the system answers from a curated document library managed by the site admin. Embeds on any website with a single `<script>` tag.

**Live deployment:** social-automate.com  
**Stack:** Python · Flask · SQLite + sqlite-vec · OpenRouter API · Vanilla JS (Shadow DOM)

---

## What It Does

- Admin uploads PDF, DOCX, TXT, or a URL → system parses, chunks, embeds, and indexes it
- Visitor opens the chat widget, asks a question → system retrieves relevant document chunks, sends them to an LLM, returns a grounded answer
- If no document chunk is similar enough (cosine similarity below threshold), the widget shows an inline lead capture form instead of hallucinating
- Captured leads (name, email, phone, question) are stored in SQLite and emailed to admin via SMTP
- Admin reviews documents and leads through a password-protected web UI

---

## Why We Built It This Way

### The Constraint: SiteGround Shared Hosting

Most RAG tutorials assume you control your infrastructure — a VPS, a cloud VM, Docker, GPU access. This project was built for SiteGround cPanel shared hosting, which imposes hard limits that invalidate the standard stack:

| Constraint | Standard approach | What we did instead |
|---|---|---|
| No Passenger / mod_wsgi | FastAPI (ASGI) or Gunicorn | `wsgiref.handlers.CGIHandler` — Apache spawns a fresh Python process per HTTP request |
| ~256 MB RAM per process | ChromaDB, FAISS, Pinecone | `sqlite-vec` — vector search inside SQLite, single `.db` file, no server process |
| No GPU, no PyTorch | `sentence-transformers`, local embedding models | OpenRouter API for embeddings (`text-embedding-3-small`) |
| No persistent process memory | In-memory caches, background threads | All state in SQLite with WAL mode; cron-based session archival |
| Files outside `public_html/` for security | Serve from web root | All data lives in `~/dochat/storage/` (not web-accessible); only the app and widget JS are public |

The result is a system that genuinely works on the cheapest tier of shared hosting without any DevOps overhead.

### CGI Deployment

Each HTTP request is a fresh `python3` process invoked by Apache via `app.cgi`. The Flask app is created, handles one request, and exits. This means:

- No in-process caching across requests — everything reads from SQLite on every request
- WAL mode + `PRAGMA wal_checkpoint(TRUNCATE)` after writes ensures cross-process reads see fresh data
- Fresh SQLite connections per request (vs. a connection pool) — no thread-safety concerns

### Vector Store: sqlite-vec

[sqlite-vec](https://github.com/asg017/sqlite-vec) is a SQLite extension that stores and queries float32 embeddings. It gives us cosine similarity search inside a single `.db` file with no external service, no RAM overhead beyond what SQLite already uses, and zero operational complexity. ChromaDB would have demanded 400+ MB for its HNSW index alone — the process would be OOM-killed.

Vectors are stored as `float[1536]` (matching OpenAI's `text-embedding-3-small` output dimension) with `distance_metric=cosine`. The similarity threshold (~0.35 cosine distance) gates whether a question gets an LLM answer or falls through to lead capture.

### LLM: OpenRouter with Automatic Failover

Primary model: `google/gemma-3-27b-it:free`  
Fallback model: `qwen/qwen3-next-80b-a3b-instruct:free`

When the primary model returns a 429 or error, the pipeline automatically retries with the fallback. OpenRouter's unified API makes this a single `if` statement rather than managing two SDK clients.

### Chunking

Documents are chunked with LangChain's `RecursiveCharacterTextSplitter` using `from_tiktoken_encoder` (GPT-2 tokenizer). Chunk size is 511 tokens (not 512 — LangChain has an off-by-one that produces 513-token chunks at exactly 512; 511 keeps everything within the embedding model's context window). Overlap is 100 tokens.

### Widget: Shadow DOM Isolation

The embeddable widget is a single vanilla JS IIFE (~800 lines, zero dependencies, no build step). It injects a Shadow DOM host into the page — the widget's CSS is completely isolated from the host site's styles. Embedding is:

```html
<script>
  window.DocChatConfig = {
    apiUrl: 'https://your-site.com/dochat/chat',
    primaryColor: '#3b82f6',
    title: 'Ask us anything'
  };
</script>
<script src="https://your-site.com/dochat/widget.js"></script>
```

---

## Architecture

```
Visitor browser
    │
    │  GET /dochat/widget.js          POST /dochat/api/chat
    │  ─────────────────────          ───────────────────────────────────
    ▼                                 ▼
Apache .htaccess  ──────────────►  app.cgi  ──►  Flask app (create_app())
                                      │
                    ┌─────────────────┼─────────────────────┐
                    ▼                 ▼                       ▼
             embed_query()     vector_search()          _call_llm_with_retry()
             (OpenRouter API)  (sqlite-vec cosine)      (OpenRouter → Gemma / Qwen)
                    │                 │                       │
                    └─────────────────┴───────────────────────┘
                                      │
                              SQLite  dochat.db
                         ┌────────────┴────────────┐
                         │  documents  chunks       │
                         │  vec_items  sessions     │
                         │  leads      settings     │
                         └─────────────────────────┘

Admin browser
    │
    │  GET /dochat/admin/*  (password-protected)
    │  POST /dochat/admin/ingest/upload
    │  POST /dochat/admin/ingest/url
    │  POST /dochat/admin/docs/<id>/delete
    │  GET/POST /dochat/admin/settings
    ▼
  Flask admin routes  ──►  ingest pipeline  ──►  SQLite + ~/dochat/storage/
```

---

## Features

**Document management**
- Upload PDF, DOCX, TXT/MD files (up to 10 MB)
- Submit URLs for automatic web crawling via trafilatura
- Atomic ingestion: parse → chunk → embed → index in a single transaction; rollback on any failure
- Delete documents with full cleanup (file, DB row, all vector embeddings)

**Query pipeline**
- Embed visitor question → cosine search → top-4 chunks → LLM with context window
- Multi-turn conversation: last 10 turns carried in LLM context
- Similarity threshold gating: questions with no good match trigger lead form, not hallucination
- Automatic LLM failover (primary → fallback on 429/error)
- Follow-up chip suggestions generated with each answer

**Lead capture**
- Inline lead form (no redirect, no page reload) on similarity fallback
- Fields: name, email, phone (optional), question captured automatically
- SMTP email notification to admin (non-fatal: lead is saved even if email fails)
- "Book a Call" CTA button with configurable URL (admin Settings tab)
- Admin-configurable via `/dochat/admin/settings`

**Widget**
- Shadow DOM isolation — zero CSS bleed from host page
- Theming via `window.DocChatConfig` (color, logo, title, font)
- Mobile-responsive with `svh` units for iOS Safari compatibility
- Animated: spring panel open/close, directional message slide-in, bouncing typing dots
- Accessible: ARIA roles, 44px touch targets, keyboard navigation, reduced-motion support

**Admin UI**
- Password-protected (HTTP Basic Auth via `.env`)
- Document list with status, chunk count, upload date
- Leads table with name, email, phone, question, timestamp
- Settings page for Book-a-Call URL
- `Cache-Control: no-store` on all admin routes (prevents LiteSpeed cache staleness)

**Session management**
- Sessions stored in SQLite (`sessions` table, JSON message history)
- Cron-compatible archival script (`scripts/archive_sessions.py`) — moves sessions older than 24h to MySQL, no Flask context required

---

## Project Structure

```
.
├── app/
│   ├── __init__.py          # Flask factory (create_app), widget.js route
│   ├── auth.py              # @require_auth decorator (HTTP Basic)
│   ├── db.py                # _open_db(), init_* functions, sqlite-vec loader
│   ├── ingest/
│   │   ├── parser.py        # PDF/DOCX/TXT/URL extraction
│   │   ├── chunker.py       # RecursiveCharacterTextSplitter (tiktoken, 511 tokens)
│   │   └── embedder.py      # OpenRouter embeddings API, batch retry
│   ├── routes/
│   │   ├── admin.py         # GET /dochat/admin/* (password-protected pages)
│   │   ├── admin_api.py     # POST/DELETE admin API + public /api/leads + /api/settings
│   │   ├── chat.py          # POST /dochat/api/chat (CORS, session, RAG dispatch)
│   │   ├── health.py        # GET /dochat/health
│   │   └── ingest.py        # (legacy) direct ingest routes
│   ├── services/
│   │   ├── ingestion.py     # ingest_file(), ingest_url(), _delete_document()
│   │   ├── query.py         # handle_chat() — full RAG pipeline
│   │   └── email.py         # send_lead_notification() via SMTP
│   └── static/
│       ├── widget.js        # Embeddable Shadow DOM widget (~800 lines, zero deps)
│       └── admin.js         # Admin UI JS (document CRUD, settings save)
├── templates/
│   └── admin/               # Jinja2 templates (base, docs, leads, settings)
├── tests/                   # ~200 pytest tests across 14 files
├── scripts/
│   └── archive_sessions.py  # Standalone cron script for session archival
├── app.cgi                  # Apache CGI entry point (wsgiref.handlers.CGIHandler)
├── passenger_wsgi.py        # Passenger shim (fallback, not used on SiteGround)
├── requirements.txt
└── .env.example
```

---

## Local Development

```bash
# 1. Clone and set up venv
git clone <repo>
cd dochat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set OPENROUTER_API_KEY, ADMIN_PASSWORD, SECRET_KEY, SMTP_* vars

# 3. Run locally (Flask dev server)
export FLASK_APP=app
export FLASK_ENV=development
flask run

# 4. Run tests
pytest -v
```

The app uses `STORAGE_PATH` from `.env` (or `./storage/` by default) for the SQLite DB and uploaded files. The dev server will create `storage/dochat.db` on first request to `/dochat/health`.

---

## SiteGround Deployment

```bash
# On the server (SSH)
cd ~/dochat
git pull origin master
source venv/bin/activate
pip install -r requirements.txt

# cPanel Python Selector:
# - Python version: 3.14.x
# - Application root: ~/dochat
# - Application URL: /dochat
# - Application startup file: app.cgi

# Apply .htaccess patch (route /dochat/* to CGI, protect /health)
# See staging_htaccess_patch.txt, staging_widget_htaccess_patch.txt,
# and staging_htaccess_patch_phase6.txt for the exact RewriteRule blocks.
```

Key SiteGround-specific notes:
- The home directory resolves as `/home/customer/` (symlink) — all shebangs use this path
- No Passenger, no mod_wsgi — Apache CGI only via `wsgiref.handlers.CGIHandler`
- `enable_load_extension` is available — sqlite-vec runs in native mode (not Python fallback)
- `STORAGE_PATH` is derived from `__file__` in `create_app()`, not `HOME` — Passenger/CGI resolves the home directory differently from SSH

---

## Environment Variables

```env
SECRET_KEY=<random string>
ADMIN_PASSWORD=<password for /dochat/admin>

OPENROUTER_API_KEY=<your key>
PRIMARY_MODEL=google/gemma-3-27b-it:free
FALLBACK_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
EMBEDDING_MODEL=text-embedding-3-small

STORAGE_PATH=~/dochat/storage       # absolute path to DB + uploads dir
ALLOWED_ORIGINS=https://your-site.com,https://www.your-site.com

# SMTP (for lead notifications — optional, non-fatal if unset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=<app password>
SMTP_TO=you@yourdomain.com

# Session archival (optional)
MYSQL_HOST=...
MYSQL_DB=...
MYSQL_USER=...
MYSQL_PASS=...
```

---

## Test Suite

```bash
pytest -v                          # all ~200 tests
pytest tests/test_chat.py -v       # RAG pipeline + fallback
pytest tests/test_leads.py -v      # lead capture (16 tests)
pytest tests/test_ingest_upload.py # file ingestion
pytest tests/test_widget_delivery.py
```

Tests use `pytest-mock` to stub OpenRouter API calls and SMTP — no external services needed during testing. The DB is an in-memory SQLite instance initialized fresh per test via `conftest.py`.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Flask over FastAPI | FastAPI is ASGI; SiteGround's Apache CGI only supports WSGI |
| sqlite-vec over ChromaDB/Pinecone | No external service, no RAM spike; single `.db` file, native SQLite extension |
| OpenRouter API for embeddings | `sentence-transformers` / PyTorch would OOM-kill the CGI process |
| CGI over Passenger WSGI | SiteGround shared hosting has neither Passenger nor mod_wsgi |
| WAL mode + checkpoint after writes | CGI = separate processes per request; WAL ensures cross-process reads see fresh data |
| `chunk_size=511` not 512 | LangChain off-by-one produces 513-token chunks at exactly 512 |
| Manual `BEGIN/COMMIT/ROLLBACK` | `with conn:` uses SQLite's implicit transaction semantics, which conflict with the setup here |
| Shadow DOM for widget | Complete CSS isolation from host site; no build step; embeds with one `<script>` tag |
| Data outside `public_html/` | `~/dochat/storage/` is not web-accessible; prevents direct file download |
| `Cache-Control: no-store` on admin routes | SiteGround LiteSpeed cache would otherwise serve stale admin HTML |

---

## License

MIT
