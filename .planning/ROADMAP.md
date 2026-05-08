# ROADMAP: DocChat RAG Pipeline

**Project:** DocChat RAG Pipeline
**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.
**Milestone:** v1 — Embeddable RAG chatbot on SiteGround shared hosting
**Created:** 2026-05-07
**Granularity:** standard

---

## Phases

- [ ] **Phase 1: Infrastructure & Deployment Validation** — Confirm SiteGround compatibility (Passenger WSGI, sqlite-vec, RAM, SQLite version) before writing any application logic
- [ ] **Phase 2: Document Ingestion Pipeline** — Admin can upload PDF/DOCX/TXT/MD files and submit URLs; system parses, chunks, embeds, and indexes all content
- [ ] **Phase 3: Query Pipeline & RAG Logic** — Visitor messages are embedded, searched, gated by similarity threshold, and answered by LLM with session history
- [ ] **Phase 4: Admin UI** — Password-protected web UI for document management, URL submission, and lead review
- [ ] **Phase 5: Chat Widget** — Embeddable vanilla JS widget with Shadow DOM isolation, theming, and full UX polish
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
**Plans:** TBD

### Phase 2: Document Ingestion Pipeline
**Goal:** Admin can submit any supported document or URL and the system indexes it — so there is a populated knowledge base for the query pipeline to search.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06, INGEST-07
**Success Criteria** (what must be TRUE):
  1. Admin uploads a PDF file and the system successfully parses, chunks, embeds, and stores its content in sqlite-vec
  2. Admin uploads a DOCX file and a TXT/MD file — both are indexed without error
  3. Admin submits a URL; trafilatura crawls the page and indexes the extracted text as chunks
  4. A corrupt, password-protected, or JS-rendered-empty document returns a clear error message to admin and leaves the index unchanged (rollback confirmed)
  5. Chunks are created with 512-token size and 100-token overlap using RecursiveCharacterTextSplitter; embeddings come from OpenRouter `text-embedding-3-small` (no local ML model invoked)
**Plans:** TBD

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
**Plans:** TBD

### Phase 4: Admin UI
**Goal:** Admin can manage the full document library and review captured leads through a password-protected web interface — without touching the filesystem or command line.
**Mode:** mvp
**Depends on:** Phase 2, Phase 3
**Requirements:** ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06
**Success Criteria** (what must be TRUE):
  1. Accessing any `/admin/*` route without credentials returns a 401 prompt; valid credentials from `.env` grant access
  2. Admin drags and drops a PDF onto the upload area and the document appears in the document list with filename, type, upload date, status, and chunk count
  3. Admin submits a URL via text input and the crawled page appears in the document list
  4. Admin deletes a document — it disappears from the list, its file is removed from disk, and its chunks are gone from the vector index
  5. Admin views the leads table showing name, email, question asked, and timestamp for every captured lead
**Plans:** TBD
**UI hint**: yes

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
**Plans:** TBD
**UI hint**: yes

### Phase 6: Lead Capture
**Goal:** When the RAG pipeline cannot answer a visitor's question, the widget captures the visitor's contact information and notifies admin — so no potential lead is lost.
**Mode:** mvp
**Depends on:** Phase 3, Phase 5
**Requirements:** LEADS-01, LEADS-02, LEADS-03, LEADS-04
**Success Criteria** (what must be TRUE):
  1. When similarity threshold is not met, the widget displays an inline form with name and email fields (no external redirect, no page reload)
  2. After form submission, a "Book a call" CTA link appears with the URL configured in `DocChatConfig`
  3. Submitting the form triggers an email notification to admin via SMTP/sendmail (email arrives within 60 seconds)
  4. The captured lead (name, email, question, timestamp) appears in the leads SQLite table and is visible in the admin UI leads view
**Plans:** TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Deployment Validation | 0/? | Not started | - |
| 2. Document Ingestion Pipeline | 0/? | Not started | - |
| 3. Query Pipeline & RAG Logic | 0/? | Not started | - |
| 4. Admin UI | 0/? | Not started | - |
| 5. Chat Widget | 0/? | Not started | - |
| 6. Lead Capture | 0/? | Not started | - |

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
*Last updated: 2026-05-07 after initial creation*
