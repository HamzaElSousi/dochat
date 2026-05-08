# Architecture Patterns: DocChat RAG Pipeline

**Domain:** Embeddable RAG chatbot widget on shared hosting
**Researched:** 2026-05-07
**Overall confidence:** HIGH (core patterns) / MEDIUM (SiteGround-specific paths)

---

## System Overview

Two independent pipelines share one backend process: **Ingestion** (admin-triggered, async-ish)
and **Query** (visitor-triggered, synchronous request/response). They share the vector store and
the document metadata store, but nothing else.

```
                       ┌─────────────────────────────────────────┐
                       │          FastAPI Backend (Passenger)     │
  Admin Browser ───────┤  /admin/*  (password-protected HTML UI) │
                       │                                         │
  Visitor Widget ──────┤  /api/chat    /api/widget-config        │
  (any website)        │                                         │
                       │  ┌─────────────┐  ┌──────────────────┐ │
                       │  │  Ingestion  │  │  Query Pipeline  │ │
                       │  │  Pipeline   │  │                  │ │
                       │  └──────┬──────┘  └────────┬─────────┘ │
                       │         │                   │           │
                       │  ┌──────▼───────────────────▼────────┐ │
                       │  │     ChromaDB (SQLite on disk)     │ │
                       │  └───────────────────────────────────┘ │
                       │  ┌────────────────────────────────────┐ │
                       │  │  Doc metadata (SQLite, via JSON)  │ │
                       │  └────────────────────────────────────┘ │
                       └─────────────────────────────────────────┘
                                        │
                              OpenRouter API (external)
                              ├── Embeddings endpoint
                              └── Chat completion endpoint
```

---

## 1. Ingestion Pipeline

**Trigger:** Admin uploads a file or submits a URL via the admin UI.

**Steps:**

```
Admin POST /admin/documents
       │
       ▼
1. Receive & validate file (type check: PDF/DOCX/TXT/MD/URL)
       │
       ▼
2. Save raw file to disk
   → /home/<user>/dochat/storage/raw/<uuid>_<original_filename>
       │
       ▼
3. Parse to plain text
   ├── PDF  → pdfplumber (layout-aware) or pypdf (simpler)
   ├── DOCX → python-docx
   ├── TXT/MD → read directly
   └── URL  → httpx fetch + trafilatura (extracts article text, strips nav/ads)
       │
       ▼
4. Chunk text
   Strategy: RecursiveCharacterTextSplitter
   - chunk_size: 512 tokens (~2000 chars)
   - chunk_overlap: 64 tokens
   - Split hierarchy: paragraph → sentence → word
   This is the standard production-proven approach for mixed document types.
       │
       ▼
5. Embed each chunk
   POST https://openrouter.ai/api/v1/embeddings
   - model: "text-embedding-3-small" (or equivalent available on OpenRouter)
   - batch up to 100 chunks per API call
   - Use cosine similarity (OpenRouter recommendation)
       │
       ▼
6. Store in ChromaDB
   - Collection: "documents"
   - Each record: {embedding, text, metadata: {doc_id, chunk_index, source_filename, page_num}}
       │
       ▼
7. Write doc metadata record
   - SQLite table (or JSON file): doc_id, filename, type, status, chunk_count, uploaded_at
       │
       ▼
8. Return success + doc_id to admin UI
```

**Key decision — synchronous ingestion at v1:** For <100 docs and shared hosting (no Celery/Redis
workers available), run ingestion synchronously in the request handler. Set a generous timeout.
File upload is the admin path, not user-facing — slow is acceptable. Add a loading state to the
admin UI. If a document causes a timeout (very large PDF), move to chunked processing per
sub-document.

**Key decision — OpenRouter for embeddings, not local sentence-transformers:**
Shared hosting has tight RAM per process (typically 256–512 MB on SiteGround). Loading
sentence-transformers (~90–500 MB model weights) risks OOM kills. OpenRouter's embeddings API
offloads computation. The API call adds ~200ms latency per batch, acceptable for admin ingestion.
For the query pipeline, embedding a single user message is one fast API call.

---

## 2. Query Pipeline

**Trigger:** Visitor sends a message via the chat widget.

**Steps:**

```
POST /api/chat
{session_id, message}
       │
       ▼
1. Load conversation history for session_id
   (from in-memory dict, keyed by session_id)
       │
       ▼
2. Embed the user message
   POST openrouter.ai/api/v1/embeddings
   (single text, ~100ms round-trip)
       │
       ▼
3. Vector search in ChromaDB
   collection.query(query_embeddings=[user_vec], n_results=5)
   Returns top-5 most relevant chunks with their text + metadata
       │
       ▼
4. Context assembly
   Build a string: join retrieved chunks with separators
   Cap total context at ~3000 tokens to leave room for answer
   Format: "Source: <filename>\n<chunk_text>\n---\n..."
       │
       ▼
5. Build LLM prompt
   System: "You are a helpful assistant for social-automate.com.
            Answer using ONLY the provided context. If the answer
            isn't in the context, say so clearly. Do not fabricate."
   Context: [assembled chunks]
   History: [last N turns from session dict]
   User: [current message]
       │
       ▼
6. Call OpenRouter chat completion
   POST openrouter.ai/api/v1/chat/completions
   model: "mistralai/mistral-7b-instruct" or "meta-llama/llama-3-8b-instruct"
   (free tier on OpenRouter)
       │
       ▼
7. Update session history
   Append {role: "user", content: message} and {role: "assistant", content: answer}
   Keep last 10 turns (sliding window). Do NOT store in DB at v1.
       │
       ▼
8. Return JSON: {answer, sources: [{filename, chunk_preview}]}
```

---

## 3. Component Boundaries

### Python Backend (FastAPI)

Everything that touches data, models, or business logic lives here. The backend is the only
component that knows about ChromaDB, the LLM API, and the file system.

| Responsibility | Notes |
|---|---|
| Document parsing (PDF/DOCX/TXT/MD/URL) | pdfplumber, python-docx, trafilatura |
| Chunking | langchain-text-splitters (standalone, no LangChain overhead) |
| Embedding generation | httpx calls to OpenRouter embeddings API |
| Vector store read/write | chromadb Python client |
| LLM calls | httpx calls to OpenRouter chat completions API |
| Session history storage | Python dict in process memory |
| Document metadata tracking | SQLite table or JSON file on disk |
| Admin auth | HTTP Basic Auth or hardcoded token in env var |
| File storage management | os/pathlib for disk operations |
| CORS headers | FastAPI CORSMiddleware, allow all origins (public widget) |
| Widget config endpoint | Returns theme colors, title, etc. from env/config file |

### Client-Side JavaScript (Vanilla)

The widget is a display layer only. It holds no business logic and no secrets.

| Responsibility | Notes |
|---|---|
| Render chat UI (bubble, panel, messages) | Pure DOM manipulation |
| Manage input state (typing, disabled during fetch) | Local JS state |
| Send/receive API calls to backend | fetch() with JSON |
| Store session_id for conversation continuity | localStorage or in-memory var |
| Apply theme (colors from /api/widget-config) | CSS custom properties |
| Show source citations | Render sources array from response |
| Handle errors gracefully | Show fallback message on network failure |

**The widget never calls OpenRouter directly.** All AI logic goes through the backend.

### Admin UI

Served as static HTML from the FastAPI backend itself (FastAPI can serve static files and
Jinja2 templates). No separate frontend build step needed.

| Responsibility | Notes |
|---|---|
| File upload form | HTML multipart form → POST /admin/documents |
| Document list | GET /admin/documents, rendered server-side or via JS fetch |
| Delete document | DELETE /admin/documents/{id} |
| URL submission | Form with URL field → same ingestion endpoint |
| Auth gate | HTTP Basic Auth header, checked in FastAPI dependency |

---

## 4. File Storage Layout

SiteGround cPanel Python Selector creates the app under `/home/<cpanel_username>/`.
The app root (set in cPanel) becomes the working directory for the Passenger process.

**Recommended directory layout:**

```
/home/<cpanel_username>/
├── dochat/                         ← App root (set in cPanel Python Selector)
│   ├── passenger_wsgi.py           ← Passenger entry point (WSGI adapter)
│   ├── main.py                     ← FastAPI app
│   ├── requirements.txt
│   ├── .env                        ← Secrets: OPENROUTER_API_KEY, ADMIN_PASSWORD
│   ├── config.py
│   ├── routers/
│   │   ├── chat.py
│   │   ├── admin.py
│   │   └── widget.py
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   └── llm.py
│   ├── static/                     ← Widget JS, admin CSS/JS (served by FastAPI)
│   │   ├── widget.js               ← The embeddable script
│   │   └── admin/
│   │       └── index.html
│   └── storage/                    ← NOT under public_html — private data
│       ├── raw/                    ← Uploaded source files (PDF, DOCX, etc.)
│       │   └── <uuid>_filename.pdf
│       ├── chroma_db/              ← ChromaDB SQLite files
│       │   ├── chroma.sqlite3
│       │   └── <collection-uuid>/
│       └── metadata.db             ← SQLite doc metadata (or metadata.json)
│
└── public_html/                    ← Static HTML for the main site (not the app)
```

**Critical:** `storage/` must NOT be under `public_html/`. Place it inside the app root
(`dochat/storage/`), which Passenger serves as the application root but does not directly
expose to HTTP — only FastAPI routes control access.

**ChromaDB path in code:**

```python
import chromadb
CHROMA_PATH = Path(__file__).parent / "storage" / "chroma_db"
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
```

**Raw file path in code:**

```python
RAW_UPLOAD_DIR = Path(__file__).parent / "storage" / "raw"
RAW_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
```

---

## 5. Widget-Backend Communication (CORS + API Endpoints)

The widget loads on third-party sites (e.g., social-automate.com, client WordPress sites).
The browser enforces CORS — the backend must explicitly permit cross-origin requests.

**CORS configuration (FastAPI):**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Public widget: allow any site to embed it
    allow_credentials=False,      # No cookies — session_id passed in request body
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

Note: `allow_credentials=True` cannot be combined with `allow_origins=["*"]`. Since the widget
uses no cookies (session_id is in the JSON body), credentials=False is correct.

**Public API endpoints (no auth required):**

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Send message, get answer |
| `/api/widget-config` | GET | Returns theme, title, placeholder text |

**Admin endpoints (auth required — HTTP Basic Auth or Bearer token):**

| Endpoint | Method | Purpose |
|---|---|---|
| `/admin/documents` | GET | List all indexed documents |
| `/admin/documents` | POST | Upload file or submit URL |
| `/admin/documents/{id}` | DELETE | Remove document + its vectors |
| `/admin/` | GET | Serve admin HTML UI |

**Widget embed pattern:**

```html
<!-- On any website -->
<script>
  window.DocChatConfig = {
    backendUrl: "https://api.social-automate.com",
    widgetTitle: "Ask Us Anything"
  };
</script>
<script src="https://api.social-automate.com/static/widget.js" defer></script>
```

The widget JS reads `window.DocChatConfig`, fetches `/api/widget-config` for dynamic theme
values, then renders the chat bubble into the page DOM.

---

## 6. Session / Conversation History

**Approach: In-process dict with sliding window**

At <100 queries/day on a persistent Passenger process, an in-memory dict keyed by session_id
is the right v1 choice. No Redis, no DB writes, no operational overhead.

```python
# In FastAPI app state (module-level dict)
from collections import defaultdict

conversation_history: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_TURNS = 10  # 10 pairs = 20 messages

def get_history(session_id: str) -> list[dict]:
    return conversation_history[session_id]

def append_to_history(session_id: str, user_msg: str, assistant_msg: str):
    history = conversation_history[session_id]
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    # Sliding window: keep last N turns
    if len(history) > MAX_HISTORY_TURNS * 2:
        conversation_history[session_id] = history[-(MAX_HISTORY_TURNS * 2):]
```

**session_id generation:**

The widget generates a UUID on first load and stores it in `sessionStorage` (clears on tab
close, which is the right UX — each session is a fresh visit).

```javascript
// In widget.js
const sessionId = sessionStorage.getItem('dochat_session_id')
  || (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem('dochat_session_id', id);
    return id;
  })();
```

**Caveats to document:**

- Memory resets when Passenger restarts the process (deployments, crashes, idle timeout).
  This is acceptable — conversation context is session-scoped, not persistent.
- Passenger may spawn multiple worker processes. Sessions are not shared across workers.
  On SiteGround shared hosting, Passenger typically runs a single worker for low-traffic apps,
  making this a non-issue at v1 scale. Flag this for v2 if horizontal scaling is needed.
- Session dict grows unboundedly if never cleaned. Add a simple TTL cleanup task using
  Python's `threading.Timer` or rely on Passenger process restarts to flush.

---

## 7. Passenger WSGI Bridge

FastAPI is ASGI. Phusion Passenger (used by SiteGround cPanel) expects WSGI.
Use `a2wsgi` to bridge them — it is more actively maintained than `asgiref.wsgi` for this use.

```python
# passenger_wsgi.py
from a2wsgi import ASGIMiddleware
from main import app  # your FastAPI instance

application = ASGIMiddleware(app)
```

Install: `pip install a2wsgi`

This runs FastAPI synchronously inside a WSGI container — async endpoints work but concurrency
is limited compared to a native uvicorn deployment. At <100 queries/day this is not a
bottleneck. If latency becomes an issue, the VPS fallback with uvicorn + nginx is the upgrade path.

---

## 8. Anti-Patterns to Avoid

### Anti-Pattern 1: Loading sentence-transformers at startup
**What happens:** The process loads 90–500 MB of model weights into RAM at import time.
On SiteGround shared hosting with per-process RAM limits, this causes OOM kills (SIGKILL 15)
and the Passenger process crashes on every request after restart.
**Instead:** Use OpenRouter's embeddings API. The extra ~200ms per embed call is irrelevant
compared to the LLM call latency (1–5 seconds).

### Anti-Pattern 2: Storing ChromaDB inside public_html
**What happens:** The SQLite files are directly downloadable by anyone who knows the path.
Your entire knowledge base (document text + embeddings) is publicly exposed.
**Instead:** Keep `storage/` inside the app root, outside `public_html/`.

### Anti-Pattern 3: Per-request ChromaDB client instantiation
**What happens:** Each request creates a new PersistentClient, which acquires a file lock on
the SQLite DB. Under concurrent requests this causes lock contention and errors.
**Instead:** Create the ChromaDB client once at module level (or FastAPI startup event) and
share it across requests. ChromaDB's PersistentClient is safe to use across threads.

### Anti-Pattern 4: Sending full conversation history to the LLM without capping
**What happens:** History grows across a session. A long conversation exceeds the model's
context window, causing API errors or silently dropping earlier messages.
**Instead:** Use a sliding window (10 most recent turns) and track token count if possible.

### Anti-Pattern 5: Embedding the OPENROUTER_API_KEY in widget.js
**What happens:** The key is visible in browser DevTools. Anyone can copy it and use your
quota or rack up charges.
**Instead:** The key lives only in `.env` on the server. The widget calls your backend;
your backend calls OpenRouter. The widget never touches OpenRouter directly.

---

## 9. Build Order

Build in this sequence to validate each layer before adding the next:

**Phase 1: Backend skeleton + ingestion**
1. FastAPI app with `passenger_wsgi.py` bridge — confirm it runs on SiteGround
2. `/admin/documents POST` — file upload, save to `storage/raw/`
3. Parser module (PDF, DOCX, TXT, MD) — confirm text extraction works
4. Chunker (RecursiveCharacterTextSplitter from `langchain-text-splitters`)
5. OpenRouter embedding call — confirm API works, store embeddings in ChromaDB
6. Document metadata storage (SQLite table)
7. `/admin/documents GET` — list documents with chunk count
8. `/admin/documents/{id} DELETE` — remove file + delete ChromaDB entries by doc_id

**Phase 2: Query pipeline**
1. `/api/chat POST` — embed query, search ChromaDB, assemble context
2. OpenRouter chat completion call — return answer + sources
3. Session history dict — inject last N turns into prompt

**Phase 3: Admin UI**
1. Static HTML served by FastAPI at `/admin/`
2. File upload form, document list, delete button
3. HTTP Basic Auth dependency on all `/admin/*` routes

**Phase 4: Widget**
1. Minimal vanilla JS chat bubble — POST to `/api/chat`, display response
2. CORS configured and tested from a different origin (test with a simple HTML file on another domain or port)
3. `/api/widget-config` endpoint for theme values
4. Polish: typing indicator, error states, source citations, theming

**Phase 5: URL ingestion**
1. `/admin/documents POST` with `url` field instead of file
2. `trafilatura` for content extraction from URLs
3. Same chunking/embedding pipeline as file ingestion

Build Phase 1 end-to-end before touching the widget. Knowing the ingestion and retrieval work
correctly is the riskiest unknown — validate it first.

---

## Sources

- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [FastAPI WSGI integration](https://fastapi.tiangolo.com/advanced/wsgi/)
- [a2wsgi on PyPI](https://pypi.org/project/a2wsgi/)
- [Phusion Passenger Python quickstart](https://www.phusionpassenger.com/library/walkthroughs/start/python.html)
- [OpenRouter Embeddings API](https://openrouter.ai/docs/api/reference/embeddings)
- [ChromaDB PersistentClient](https://python.langchain.com/docs/integrations/vectorstores/chroma/)
- [Chunking strategies for RAG (Unstructured)](https://unstructured.io/blog/chunking-for-rag-best-practices)
- [How to deploy FastAPI on cPanel (DEV Community)](https://dev.to/cmanish049/how-to-deploy-fastapi-on-shared-hosting-cpanel-7ch)
- [Embeddable chat widget design (Medium)](https://medium.com/@dailysandbox/how-to-design-an-embeddable-chat-module-5e6475184abb)
- [RAG with conversation history (LangChain)](https://medium.com/@eric_vaillancourt/mastering-langchain-rag-integrating-chat-history-part-2-4c80eae11b43)
