# Requirements: DocChat RAG Pipeline

**Defined:** 2026-05-07
**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: Flask app runs on SiteGround via Passenger WSGI (`passenger_wsgi.py`, single-worker)
- [ ] **INFRA-02**: sqlite-vec database initializes with WAL mode and 10s busy timeout at startup
- [ ] **INFRA-03**: All data files (vector DB, uploads) stored outside `public_html/` at `~/dochat/storage/`
- [ ] **INFRA-04**: All secrets (API keys, admin password) loaded from `.env` file, never hardcoded

### Document Ingestion

- [ ] **INGEST-01**: Admin can upload PDF files; system parses text and indexes chunks
- [ ] **INGEST-02**: Admin can upload DOCX files; system parses text and indexes chunks
- [ ] **INGEST-03**: Admin can upload TXT and MD files; system indexes content directly
- [ ] **INGEST-04**: Admin can submit a URL; system crawls and indexes page content via trafilatura
- [ ] **INGEST-05**: System chunks documents with RecursiveCharacterTextSplitter (512 tokens, 100-token overlap)
- [ ] **INGEST-06**: System generates embeddings via OpenRouter `text-embedding-3-small` API (no local ML models)
- [ ] **INGEST-07**: Corrupt, password-protected, or JS-rendered-empty documents return a clear error to admin; indexing rolls back

### Query Pipeline

- [ ] **QUERY-01**: Visitor message is embedded and vector-searched against document index (top-k=4)
- [ ] **QUERY-02**: Similarity threshold gate (cosine ~0.35) blocks hallucination — returns fallback when no relevant chunks found
- [ ] **QUERY-03**: LLM system prompt restricts answers to indexed context only (no training knowledge)
- [ ] **QUERY-04**: Session chat history (up to 10 turns) included in LLM context per session
- [ ] **QUERY-05**: Primary LLM (`google/gemma-3-27b-it:free`) with automatic fallback to `qwen/qwen3-next-80b-a3b-instruct:free` on 429/error

### Chat Widget

- [ ] **WIDGET-01**: Floating FAB button (fixed bottom-right) opens and closes the chat panel
- [ ] **WIDGET-02**: Typing indicator (animated dots) displays while awaiting LLM response
- [ ] **WIDGET-03**: Three suggested follow-up question chips rendered after each bot answer
- [ ] **WIDGET-04**: Current conversation history visible within the chat panel
- [ ] **WIDGET-05**: Widget renders inside Shadow DOM so host site CSS cannot break it
- [ ] **WIDGET-06**: Widget is fully usable on mobile (responsive layout, touch targets ≥ 44px)
- [ ] **WIDGET-07**: Widget colors and logo configurable via `window.DocChatConfig` before script load
- [ ] **WIDGET-08**: Widget embeds on any website with a single `<script>` tag, no build step

### Lead Capture

- [ ] **LEADS-01**: When similarity threshold not met, widget displays inline lead capture form (name + email fields)
- [ ] **LEADS-02**: After form submission, widget displays a "Book a call" CTA link (URL configurable in `DocChatConfig`)
- [ ] **LEADS-03**: Captured lead triggers an email notification to admin (SMTP/sendmail from `.env`)
- [ ] **LEADS-04**: Leads stored in SQLite table (name, email, question, timestamp)

### Admin UI

- [ ] **ADMIN-01**: All admin routes protected with HTTP Basic Auth (single credential from `.env`)
- [ ] **ADMIN-02**: Admin can upload documents via drag-and-drop file input (PDF, DOCX, TXT, MD)
- [ ] **ADMIN-03**: Admin can submit a URL for crawling via text input field
- [ ] **ADMIN-04**: Admin sees document list with filename, type, upload date, status, and chunk count
- [ ] **ADMIN-05**: Admin can delete a document — removes file from disk and all associated vectors from index
- [ ] **ADMIN-06**: Admin can view leads table (name, email, question asked, timestamp)

---

## v2 Requirements

### Answer Quality

- **QUAL-01**: Source citations shown below each answer (document name + relevant excerpt)
- **QUAL-02**: Cross-encoder re-ranking of retrieved chunks before LLM call (improves precision)
- **QUAL-03**: Hybrid search combining vector similarity and BM25 keyword matching

### Widget UX

- **UX-01**: Streaming responses via SSE (words appear progressively, not all at once)
- **UX-02**: User can rate answers (thumbs up/down) for quality feedback
- **UX-03**: Widget supports multiple languages (auto-detect visitor language)

### Admin

- **ADM-01**: Analytics dashboard — queries/day, top questions, fallback rate
- **ADM-02**: Bulk document upload (zip file)
- **ADM-03**: Document preview (show indexed chunks for a doc)
- **ADM-04**: Index rebuild (re-chunk and re-embed all documents with updated settings)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-tenant (per-user doc libraries) | Single admin controls one shared library — no user auth complexity |
| Self-hosted LLM (Ollama/GPU) | Incompatible with shared hosting RAM limits |
| Local embedding models (sentence-transformers) | PyTorch adds 200–420 MB RAM — OOM kill risk on shared hosting |
| PostgreSQL / pgvector | SiteGround shared hosting has MySQL only; sqlite-vec is the solution |
| Real-time streaming in v1 | SSE requires careful Passenger config; negligible UX benefit at <100 queries/day |
| Voice input | Out of scope for text-focused consulting chatbot |
| Document version history | Admin deletes and re-uploads to update docs |
| Mobile native app | Web widget embeds everywhere; no native app needed |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INGEST-01 | Phase 2 | Pending |
| INGEST-02 | Phase 2 | Pending |
| INGEST-03 | Phase 2 | Pending |
| INGEST-04 | Phase 2 | Pending |
| INGEST-05 | Phase 2 | Pending |
| INGEST-06 | Phase 2 | Pending |
| INGEST-07 | Phase 2 | Pending |
| QUERY-01 | Phase 3 | Pending |
| QUERY-02 | Phase 3 | Pending |
| QUERY-03 | Phase 3 | Pending |
| QUERY-04 | Phase 3 | Pending |
| QUERY-05 | Phase 3 | Pending |
| ADMIN-01 | Phase 4 | Pending |
| ADMIN-02 | Phase 4 | Pending |
| ADMIN-03 | Phase 4 | Pending |
| ADMIN-04 | Phase 4 | Pending |
| ADMIN-05 | Phase 4 | Pending |
| ADMIN-06 | Phase 4 | Pending |
| WIDGET-01 | Phase 5 | Pending |
| WIDGET-02 | Phase 5 | Pending |
| WIDGET-03 | Phase 5 | Pending |
| WIDGET-04 | Phase 5 | Pending |
| WIDGET-05 | Phase 5 | Pending |
| WIDGET-06 | Phase 5 | Pending |
| WIDGET-07 | Phase 5 | Pending |
| WIDGET-08 | Phase 5 | Pending |
| LEADS-01 | Phase 6 | Pending |
| LEADS-02 | Phase 6 | Pending |
| LEADS-03 | Phase 6 | Pending |
| LEADS-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34 (all mapped)
- Unmapped: 0

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-07 after roadmap creation — traceability populated*
