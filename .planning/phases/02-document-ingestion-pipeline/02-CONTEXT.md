# Phase 2: Document Ingestion Pipeline - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Admin submits a file (PDF, DOCX, TXT, MD) or URL → system parses, chunks, embeds, and stores in sqlite-vec. Phase 2 is complete when the vector index has content the query pipeline (Phase 3) can search. No UI — backend API only. Phase 4 builds the admin UI on top of these endpoints.

</domain>

<decisions>
## Implementation Decisions

### Sync Ingestion Strategy (D-01 to D-03)
- **D-01:** Ingestion is fully synchronous within the HTTP request — no background job queue, no polling. CGI model is one request → one response.
- **D-02:** All chunks from a document are embedded in a **single batched OpenRouter API call** (array input). This collapses 100 serial HTTP calls into 1, keeping total ingestion time under 5-10 seconds for typical documents.
- **D-03:** **Maximum file size: 10 MB.** Enforced at the API layer before processing begins. Returns HTTP 413 with clear message if exceeded.

### File Storage (D-04)
- **D-04:** Keep uploaded originals on disk at `~/dochat/storage/uploads/<doc_id>/original.<ext>`. Originals allow re-chunking and re-embedding when pipeline improves in later versions. Storage path uses `os.path.expanduser()` — never hardcode `/home/customer/`.

### API Endpoints (D-05 to D-06) — Claude's discretion
- **D-05:** File uploads: `POST /admin/ingest/upload` — multipart/form-data, field name `file`. Returns JSON with `doc_id`, `filename`, `chunk_count`, `status`.
- **D-06:** URL ingestion: `POST /admin/ingest/url` — JSON body `{"url": "..."}`. Returns same JSON shape as file upload.
- Both endpoints require auth (ADMIN-01 — HTTP Basic Auth from `.env`, implemented in Phase 4 but scaffolded here as a decorator).

### Duplicate Handling (D-07) — Claude's discretion
- **D-07:** Same filename uploaded again → **replace**: delete all existing chunks for that doc, remove old file, re-index fresh. No silent accumulation of stale data. Duplicate detection keyed on filename.

### Error Handling and Rollback (D-08)
- **D-08:** If parsing, chunking, or embedding fails at any stage, the operation rolls back: no partial chunks written to sqlite-vec, no file saved to disk. Response is HTTP 422 with `{"error": "<reason>", "filename": "..."}`. The index is left unchanged.

### Deployment-specific constraints (D-09)
- **D-09:** All storage paths use `os.path.expanduser('~/dochat/storage/')`. The server resolves `~` to `/home/customer/` — never hardcode this. Validated in Phase 1.
- **D-10:** New `.htaccess` route needed for each new endpoint: `RewriteRule ^admin/ingest/upload/?$ /app.cgi/admin/ingest/upload [QSA,L]` and same for `/admin/ingest/url`.

### Claude's Discretion
- API shape (D-05, D-06): multipart for files, JSON for URLs, separate endpoints — clean separation for Phase 4 UI
- Duplicate handling (D-07): replace semantics — simplest correct behavior
- Auth scaffolding: `@require_auth` decorator that checks HTTP Basic against `ADMIN_PASSWORD` from `.env` — stub in Phase 2, wired in Phase 4

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Document Ingestion — INGEST-01 through INGEST-07 (all 7 requirements scoped to this phase)
- `.planning/ROADMAP.md` §Phase 2 — success criteria, dependency on Phase 1

### Phase 1 context (patterns and constraints to carry forward)
- `.planning/phases/01-infrastructure-deployment-validation/01-CONTEXT.md` — CGI deployment decisions, storage path conventions, sqlite-vec WAL init pattern
- `.planning/phases/01-infrastructure-deployment-validation/01-02-SUMMARY.md` — confirmed environment facts: Python 3.14.3, `/home/customer/` home path, no Passenger, CGI via wsgiref

### Existing code to read before writing new code
- `app/db.py` — sqlite-vec init, WAL mode, `_open_db()` pattern — extend for document/chunk tables
- `app/__init__.py` — Flask factory, `STORAGE_PATH` config key using `os.path.expanduser`
- `app.cgi` — CGI entry point shebang (`/home/customer/dochat/venv/bin/python3`) — reference for any new CGI concerns
- `passenger_wsgi.py` — load_dotenv pattern — replicate in any new entry points

### Deployment
- `~/www/staging.social-automate.com/public_html/.htaccess` — must add new rewrite rules for each new route (on server, not in git)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/db.py → _open_db()`: Returns a WAL-mode connection with 10s busy timeout. All new DB code should call this — never open a raw `sqlite3.connect()`.
- `app/__init__.py → create_app()`: Flask factory. New blueprints (e.g., `ingest_bp`) registered here.
- `app/routes/health.py`: Blueprint pattern to follow for new route files.

### Established Patterns
- Storage path: always `app.config['STORAGE_PATH']` (set via `os.path.expanduser` in factory) — never construct paths manually.
- Secrets: always `os.environ.get('KEY')` — never hardcode. `.env` loaded by `app.cgi` before app import.
- CGI deployment: every new Flask route needs a corresponding `.htaccess` RewriteRule on the server. Document these in deployment notes.

### Integration Points
- Phase 2 creates: `documents` table + `chunks` table + `embeddings` virtual table in sqlite-vec
- Phase 3 reads: `embeddings` virtual table for vector search
- Phase 4 reads: `documents` table for document list UI

### New DB tables needed (for planner)
```sql
documents (id TEXT PK, filename TEXT, filetype TEXT, uploaded_at TEXT, status TEXT, chunk_count INT, filepath TEXT)
chunks (id TEXT PK, doc_id TEXT FK, content TEXT, chunk_index INT)
-- embeddings stored in sqlite-vec virtual table: vec_items(embedding float[1536])
-- with a mapping: chunk_embeddings (chunk_id TEXT, vec_rowid INT)
```

</code_context>

<specifics>
## Specific Ideas

- Embedding model is locked: `text-embedding-3-small` via OpenRouter (produces 1536-dim vectors) — confirmed in REQUIREMENTS.md INGEST-06
- trafilatura for URL crawling — confirmed in REQUIREMENTS.md INGEST-04
- Chunking: RecursiveCharacterTextSplitter, 512 tokens, 100-token overlap — confirmed in REQUIREMENTS.md INGEST-05
- Batch embedding: submit all chunk texts as an array in one OpenRouter API call, not one call per chunk

</specifics>

<deferred>
## Deferred Ideas

- Re-indexing all documents with updated chunking settings (v2 feature — ADM-04)
- Document preview / show indexed chunks (v2 feature — ADM-03)
- Streaming upload progress indicator (requires SSE, deferred to v2)
- Admin UI for these endpoints — Phase 4

</deferred>

---

*Phase: 2-Document Ingestion Pipeline*
*Context gathered: 2026-05-09*
