# DocChat RAG Pipeline

## What This Is

An embeddable RAG (Retrieval-Augmented Generation) chatbot widget that lets website visitors ask questions and get answers sourced from a curated document library. Built for social-automate.com (software consulting business) and designed to be dropped into any website with a single `<script>` tag. The admin manages documents via a simple web UI; visitors get instant, accurate answers without waiting for a human response.

## Core Value

A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.

## Requirements

### Validated

- [x] System answers questions using content retrieved from the document library (Phase 3 — handle_chat() with cosine similarity gate + LLM context grounding)
- [x] Chat history is maintained within a session (Phase 3 — SQLite sessions table, 10-turn window, MySQL archival cron)
- [x] Backend runs on SiteGround shared hosting via cPanel Python Selector (Phase 1 — CGI deployment confirmed)
- [x] LLM answers are generated via OpenRouter API (Phase 3 — primary google/gemma-3-27b-it:free, fallback qwen/qwen3-next-80b-a3b-instruct:free)
- [x] Admin can upload PDFs, Word docs, plain text, and markdown files via web UI (Phase 2 — ingest pipeline complete)
- [x] Admin can add web pages/URLs for the system to crawl and index (Phase 2 — trafilatura URL crawl)
- [x] Admin can remove documents from the library (Phase 4 — DELETE /dochat/admin/docs/<id> with file + vector cleanup)
- [x] Admin UI is password-protected (Phase 4 — HTTP Basic Auth via ADMIN_PASSWORD env var)
- [x] Admin can upload PDFs, Word docs, plain text, and markdown files via web UI (Phase 4 — drag-drop + URL form at /dochat/admin/docs)

### Active

- [ ] Visitor can ask questions via a branded chat widget embedded on any webpage
- [ ] Widget is themeable (colors, logo) to match any site's brand

### Current State

Phase 4 complete — Admin UI live on staging at /dochat/admin. Pico.css v2 styled, Basic Auth protected, document upload/delete/URL ingest working, leads table ready for Phase 6. 76/76 tests passing.

### Out of Scope

- User accounts / multi-tenant document libraries — admin controls one shared library, not per-user
- Real-time streaming responses — v1 uses standard request/response; streaming is v2
- Analytics dashboard — defer to v2 after validating the core chatbot
- Mobile app / native widget — web widget only
- Self-hosted LLM (Ollama/GPU) — too complex for shared hosting; use OpenRouter API
- Document version history — admin deletes and re-uploads to update docs

## Context

- **Business site**: social-automate.com — software consulting/solutions agency. The chatbot should represent the brand well and give accurate answers to potential clients.
- **Hosting**: SiteGround shared hosting with SSH access. SiteGround supports Python WSGI apps via cPanel's Python Selector (Phusion Passenger), enabling persistent FastAPI/Flask processes without a VPS.
- **Fallback**: User also has a VPS available if SiteGround proves too constrained.
- **LLM**: OpenRouter (leaning free models like Mistral/Llama). Research will validate the best model for Q&A tasks.
- **Scale**: <100 queries/day at launch — cost is not a concern, latency and correctness are.
- **Embeddability**: The widget must work with a `<script>` tag on any site (WordPress, static HTML, Webflow, etc.) — no framework dependency.
- **Doc formats**: PDF, DOCX, TXT, MD, and URL crawl. Admin-only uploads.

## Constraints

- **Hosting**: SiteGround shared hosting — no Docker, no root access, limited RAM per process. Must use Python Selector (Passenger WSGI) or prove it needs the VPS.
- **Vector DB**: Must be file-based — SiteGround shared hosting has MySQL only (no PostgreSQL/pgvector). ChromaDB (SQLite-backed) or FAISS are the candidates — no DB server required for either.
- **Budget**: Minimize recurring costs. OpenRouter free tier for LLM; no paid vector DB service needed.
- **Embeddings**: Either use OpenRouter's embedding endpoint or a lightweight local model (sentence-transformers) — prefer API to avoid RAM limits.
- **Widget compatibility**: Must work on sites that can't install npm packages — plain JS, no build step required for embedding.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI on SiteGround via Passenger | Shared hosting supports WSGI Python apps — no VPS needed for v1 | — Pending |
| ChromaDB for vector storage | File-based SQLite backend, zero infra cost, Python-native | — Pending |
| OpenRouter for LLM | Free-tier models available; avoids vendor lock-in; research may refine model choice | — Pending |
| Script-tag widget (no npm) | Embeddable on any site including WordPress without a build step | — Pending |
| Admin-only doc management | Single tenant simplicity — one library, one admin, no auth complexity | — Pending |

## Current State

Phase 3 complete — the RAG query pipeline is fully operational. `POST /chat` is a live endpoint, `handle_chat()` embeds queries, vector-searches with cosine similarity gate, calls the LLM with context restriction, retries on failure, and persists session history. 62/62 tests passing.

**Phase 4 (Admin UI)** is next — password-protected web interface for document management.

Last updated: 2026-05-09 — Phase 3 completion

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-07 after initialization*
