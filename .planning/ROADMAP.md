# ROADMAP: DocChat RAG Pipeline

**Project:** DocChat RAG Pipeline
**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.
**Milestone:** v1 — Embeddable RAG chatbot on SiteGround shared hosting
**Created:** 2026-05-07
**Granularity:** standard

---

## Phases

- [ ] **Phase 1: Infrastructure & Deployment Validation** — Confirm SiteGround compatibility (Passenger WSGI, sqlite-vec, RAM, SQLite version) before writing any application logic
- [x] **Phase 2: Document Ingestion Pipeline** — Admin can upload PDF/DOCX/TXT/MD files and submit URLs; system parses, chunks, embeds, and indexes all content *(completed 2026-05-09)*
- [x] **Phase 3: Query Pipeline & RAG Logic** — Visitor messages are embedded, searched, gated by similarity threshold, and answered by LLM with session history *(completed 2026-05-09)*
- [ ] **Phase 4: Admin UI** — Password-protected web UI for document management, URL submission, and lead review
- [x] **Phase 5: Chat Widget** — Embeddable vanilla JS widget with Shadow DOM isolation, theming, and full UX polish *(completed 2026-05-10)*
- [ ] **Phase 6: Lead Capture** — Similarity fallback triggers inline lead form; captured leads stored, emailed, and viewable by admin

---

## Phase Details

### Phase 1: Infrastructure & Deployment Validation
**Goal:** The Flask app boots on SiteGround shared hosting with all runtime constraints confirmed — so every subsequent phase builds on a known-good foundation.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. A minimal Flask app responds to an HTTP request through Passenger WSGI on SiteGround (no 500 errors, no WSGI misconfiguration)
  2. sqlite-vec initializes with WAL mode and 10s busy timeout; a test vector insert and retrieval succeeds
  3. All data files (DB, uploads) are confirmed to live at `~/dochat/storage/` — nothing written under `public_html/`
  4. All secrets (API key, admin password) are loaded from `.env` and verified absent from source files
**Plans:** 2 plans

Plans:
- [ ] 01-01-PLAN.md — Build project scaffold locally: passenger_wsgi.py, Flask factory, sqlite-vec db.py with WAL + fallback, /health route, pytest suite
- [ ] 01-02-PLAN.md — Deploy scaffold to SiteGround via SSH + git pull, configure cPanel Python Selector, verify live /health endpoint

### Phase 2: Document Ingestion Pipeline
**Goal:** Admin can submit any supported document or URL and the system indexes it — so there is a populated knowledge base for the query pipeline to search.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06, INGEST-07
**Success Criteria** (what must be TRUE):
  1. Admin uploads a PDF file and the system successfully parses, chunks, embeds, and stores its content in sqlite-vec
  2. Admin uploads a DOCX file and a TXT/MD file — both are indexed without error
  3. Admin submits a URL; trafilatura crawls the page and indexes the extracted text as plain text
  4. A corrupt, password-protected, or JS-rendered-empty document returns a clear error message to admin and leaves the index unchanged (rollback confirmed)
  5. Chunks are created with 512-token size and 100-token overlap using RecursiveCharacterTextSplitter; embeddings come from OpenRouter `text-embedding-3-small` (no local ML model invoked)
**Plans:** 4 plans

Plans:
- [x] 02-01-PLAN.md — DB schema (4 tables incl. vec_items cosine), auth stub decorator, 6 new pip dependencies
- [x] 02-02-PLAN.md — File ingestion slice: parser/chunker/embedder utilities + ingestion service (atomic rollback) + upload route + upload tests
- [x] 02-03-PLAN.md — URL ingestion slice: fetch_and_extract_url + /admin/ingest/url route + URL tests
- [x] 02-04-PLAN.md — Service-layer correctness tests: rollback, chunking, batching, duplicate-replace

**Wave dependency notes:**
- **Wave 1** — 02-01 (DB schema + auth stub)
- **Wave 2** *(blocked on Wave 1 completion)* — 02-02 (file ingest slice)
- **Wave 3** *(blocked on Wave 2 completion)* — 02-03, 02-04 (URL slice + service tests, parallel)

**Cross-cutting constraints:** `os.path.expanduser` for all storage paths; `_open_db()` for all DB connections; Manual `BEGIN`/`COMMIT`/`ROLLBACK` only (no `with conn:`); no torch/transformers in deps.

### Phase 3: Query Pipeline & RAG Logic
**Goal:** A visitor question produces a correct, context-grounded answer — or a clean "I don't know" fallback — with session continuity across turns.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** QUERY-01, QUERY-02, QUERY-03, QUERY-04, QUERY-05
**Success Criteria** (what must be TRUE):
  1. A visitor question triggers a vector search returning the top-4 most relevant chunks from the index
  2. A question with no relevant documents (cosine similarity below ~0.35) returns the configured fallback message — no hallucinated answer
  3. The LLM answer is demonstrably restricted to indexed context (a question about unindexed topics returns the fallback, not fabricated knowledge)
  4. A multi-turn conversation retains the last 10 turns of history in LLM context; earlier turns are dropped gracefully
  5. When the primary model (`google/gemma-3-27b-it:free`) returns a 429 or error, the system automatically retries with `qwen/qwen3-next-80b-a3b-instruct:free` and the visitor receives an answer
**Plans:** 5 plans

Plans:
- [x] 03-01-PLAN.md — DB foundation: sessions table in app/db.py, embed_query() wrapper in embedder.py, chat_bp stub in app/__init__.py
- [x] 03-02-PLAN.md — Query service: app/services/query.py with full handle_chat() pipeline (embed → search → gate → LLM retry → session save)
- [x] 03-03-PLAN.md — Chat route: full app/routes/chat.py with CORS handling, .env.example Phase 3 vars
- [x] 03-04-PLAN.md — MySQL archival cron: scripts/archive_sessions.py standalone script + PyMySQL dependency
- [x] 03-05-PLAN.md — Chat endpoint tests: tests/test_chat.py with 10 behavioral test cases

**Wave dependency notes:**
- **Wave 1** — 03-01 (DB foundation + embed wrapper)
- **Wave 2** — 03-02 (query service, depends 03-01), 03-04 (archive cron, depends 03-01, parallel with 03-02)
- **Wave 3** — 03-03 (chat route, depends 03-02)
- **Wave 4** — 03-05 (tests, depends 03-03 + 03-04)

**Cross-cutting constraints:** Manual `BEGIN`/`COMMIT`/`ROLLBACK` only; all storage via STORAGE_PATH; no torch/transformers; no `with conn:`; serialize_f32 imported from app.services.ingestion (not redefined).

### Phase 4: Admin UI
**Goal:** Admin can manage the full document library and review captured leads through a password-protected web interface — without touching the filesystem or command line.
**Mode:** mvp
**Depends on:** Phase 2, Phase 3
**Requirements:** ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06
**Success Criteria** (what must be TRUE):
  1. Accessing any `/dochat/admin/*` route without credentials returns a 401 prompt; valid credentials from `.env` grant access
  2. Admin drags and drops a PDF onto the upload area and the document appears in the document list with filename, type, upload date, status, and chunk count
  3. Admin submits a URL via text input and the crawled page appears in the document list
  4. Admin deletes a document — it disappears from the list, its file is removed from disk, and its chunks are gone from the vector index
  5. Admin views the leads table showing name, email, question asked, and timestamp for every captured lead
**Plans:** 4 plans

Plans:
- [ ] 04-01-PLAN.md — DB foundation: leads table DDL in app/db.py, admin_bp + admin_api_bp blueprint stubs registered in app factory
- [ ] 04-02-PLAN.md — Admin page routes (GET /dochat/admin/*) + all Jinja2 templates + static/admin.js (8 JS functions)
- [ ] 04-03-PLAN.md — Admin API routes: POST /dochat/admin/ingest/upload, POST /dochat/admin/ingest/url, DELETE /dochat/admin/docs/<doc_id>
- [ ] 04-04-PLAN.md — Admin test suite (tests/test_admin.py) + .htaccess rewrite rules for staging server

**Wave dependency notes:**
- **Wave 1** — 04-01 (DB schema + blueprint stubs)
- **Wave 2** *(blocked on Wave 1)* — 04-02 (page routes + templates + JS)
- **Wave 3** *(blocked on Wave 1 + 04-02)* — 04-03 (API routes)
- **Wave 4** *(blocked on Wave 2 + Wave 3)* — 04-04 (tests + .htaccess, has human checkpoint)

**Cross-cutting constraints:** Route prefix `/dochat/admin` (not `/admin`); `@require_auth` on all admin handlers; `current_app.config['DB_CONN']` for all DB access; manual `BEGIN`/`COMMIT`/`ROLLBACK` only; no `with conn:`; no torch/transformers.

### Phase 5: Chat Widget
**Goal:** A visitor on any website can open the chat widget, ask a question, and receive an answer — with the widget isolated from host-site CSS and branded to match the site.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** WIDGET-01, WIDGET-02, WIDGET-03, WIDGET-04, WIDGET-05, WIDGET-06, WIDGET-07, WIDGET-08
**Success Criteria** (what must be TRUE):
  1. Pasting a single `<script>` tag onto a plain HTML page, a WordPress page, and a Webflow page renders the floating FAB button — no npm, no build step required
  2. Clicking the FAB opens the chat panel; clicking again closes it; conversation history remains visible within the session
  3. While waiting for the LLM response, animated typing dots appear; after the response arrives, three follow-up question chips are shown
  4. The widget renders inside Shadow DOM — injecting conflicting CSS rules into the host page does not alter widget appearance
  5. The widget is fully operable on a 375px-wide mobile screen with all touch targets measuring at least 44px
  6. Setting `window.DocChatConfig = { primaryColor: '#ff0000', logo: '...' }` before the script tag changes widget colors and logo accordingly
**Plans:** 3 plans

Plans:
- [x] 05-01-PLAN.md — Backend chips: modify query.py (_parse_chips helper + chip prompt) + chat.py docstring + tests/test_chat_chips.py (9 tests)
- [x] 05-02-PLAN.md — Widget JS: create app/static/widget.js (full Shadow DOM widget, ~350+ lines, IIFE, zero deps)
- [x] 05-03-PLAN.md — Widget delivery: /dochat/widget.js Flask route in app/__init__.py + staging_widget_htaccess_patch.txt + tests/test_widget_delivery.py (5 tests) + human embed verification

**Wave dependency notes:**
- **Wave 1** — 05-01 (backend chips), 05-02 (widget JS) — parallel, no shared files
- **Wave 2** *(blocked on Wave 1)* — 05-03 (delivery + integration, depends on both 05-01 and 05-02)

**Cross-cutting constraints:** No torch/transformers; no npm/build step; widget.js is a single IIFE (no ES module imports); Shadow DOM isolation mandatory; secrets from .env only; Flask only.

### Phase 6: Lead Capture
**Goal:** When the RAG pipeline cannot answer a visitor's question, the widget captures the visitor's contact information and notifies admin — so no potential lead is lost.
**Mode:** mvp
**Depends on:** Phase 3, Phase 5
**Requirements:** LEADS-01, LEADS-02, LEADS-03, LEADS-04
**Success Criteria** (what must be TRUE):
  1. When similarity threshold is not met, the widget displays an inline form with name, email, and phone fields (no external redirect, no page reload)
  2. After form submission, a "Book a Call" CTA button appears with the URL configured via admin Settings tab
  3. Submitting the form triggers an email notification to admin via SMTP (email arrives within 60 seconds)
  4. The captured lead (name, email, phone, question, timestamp) appears in the leads SQLite table and is visible in the admin UI leads view
**Plans:** 4 plans

Plans:
- [ ] 06-01-PLAN.md — DB migrations (phone column + settings table) + app/services/email.py SMTP service
- [ ] 06-02-PLAN.md — Backend routes: POST /dochat/api/leads + GET /dochat/api/settings + GET/POST /dochat/admin/settings
- [ ] 06-03-PLAN.md — Admin Settings UI (base.html nav tab + settings.html + admin.js) + widget.js lead form (_leadSubmitted, fetchSettings, addLeadForm, CTA)
- [ ] 06-04-PLAN.md — Test suite (tests/test_leads.py, 16 tests) + staging_htaccess_patch_phase6.txt + human staging checkpoint

**Wave dependency notes:**
- **Wave 1** — 06-01 (DB + email service foundation)
- **Wave 2** *(both blocked on Wave 1, parallel with each other)* — 06-02 (backend routes), 06-03 (admin UI + widget JS)
- **Wave 3** *(blocked on all Wave 2)* — 06-04 (tests + .htaccess + human checkpoint)

**Cross-cutting constraints:** No torch/transformers; manual `BEGIN`/`COMMIT`/`ROLLBACK` only; no `with conn:`; all DB via `_open_db()`; CORS on public widget endpoints; `@require_auth` on all `/dochat/admin/*` routes; SMTP failure is non-fatal (lead saved, log to stderr); CGI deployment — no background workers.

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Deployment Validation | 2/2 | Complete | 2026-05-09 |
| 2. Document Ingestion Pipeline | 4/4 | Complete | 2026-05-09 |
| 3. Query Pipeline & RAG Logic | 5/5 | Complete | 2026-05-09 |
| 4. Admin UI | 0/4 | In progress | - |
| 5. Chat Widget | 3/3 | Complete | 2026-05-10 |
| 6. Lead Capture | 0/4 | Planning complete | - |

---

## Coverage Map

| Requirement | Phase |
|-------------|-------|
| INFRA-01 | Phase 1 |
| INFRA-02 | Phase 1 |
| INFRA-03 | Phase 1 |
| INFRA-04 | Phase 1 |
| INGEST-01 | Phase 2 |
| INGEST-02 | Phase 2 |
| INGEST-03 | Phase 2 |
| INGEST-04 | Phase 2 |
| INGEST-05 | Phase 2 |
| INGEST-06 | Phase 2 |
| INGEST-07 | Phase 2 |
| QUERY-01 | Phase 3 |
| QUERY-02 | Phase 3 |
| QUERY-03 | Phase 3 |
| QUERY-04 | Phase 3 |
| QUERY-05 | Phase 3 |
| ADMIN-01 | Phase 4 |
| ADMIN-02 | Phase 4 |
| ADMIN-03 | Phase 4 |
| ADMIN-04 | Phase 4 |
| ADMIN-05 | Phase 4 |
| ADMIN-06 | Phase 4 |
| WIDGET-01 | Phase 5 |
| WIDGET-02 | Phase 5 |
| WIDGET-03 | Phase 5 |
| WIDGET-04 | Phase 5 |
| WIDGET-05 | Phase 5 |
| WIDGET-06 | Phase 5 |
| WIDGET-07 | Phase 5 |
| WIDGET-08 | Phase 5 |
| LEADS-01 | Phase 6 |
| LEADS-02 | Phase 6 |
| LEADS-03 | Phase 6 |
| LEADS-04 | Phase 6 |

**Coverage: 34/34 v1 requirements mapped.**

---
*Roadmap created: 2026-05-07*
*Last updated: 2026-05-08 — Phase 1 plans created (01-01-PLAN.md, 01-02-PLAN.md)*
*Updated: 2026-05-08 — Phase 2 plans created (02-01 through 02-04)*
*Updated: 2026-05-08 — Phase 2 Plan 01 complete (DB schema + auth foundation); Phase 1 marked complete (2/2 plans)*
*Updated: 2026-05-09 — Phase 2 Plans 02–04 complete (file ingest + URL ingest + service tests; 50/50 tests pass); Phase 2 marked complete*
*Updated: 2026-05-09 — Phase 3 plans created (03-01 through 03-05); 5 plans in 4 waves*
*Updated: 2026-05-09 — Phase 3 Plan 01 complete (sessions table, embed_query wrapper, chat_bp stub; 50/50 tests pass)*
*Updated: 2026-05-09 — Phase 3 complete (5/5 plans; handle_chat RAG pipeline, /chat route, CORS, archive cron, 62/62 tests pass)*
*Updated: 2026-05-09 — Phase 4 plans created (04-01 through 04-04); 4 plans in 4 waves*
*Updated: 2026-05-09 — Phase 5 plans created (05-01 through 05-03); 3 plans in 2 waves*
*Updated: 2026-05-10 — Phase 6 plans created (06-01 through 06-04); 4 plans in 3 waves*
