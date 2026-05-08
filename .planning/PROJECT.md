# DocChat RAG Pipeline

## What This Is

An embeddable RAG (Retrieval-Augmented Generation) chatbot widget that lets website visitors ask questions and get answers sourced from a curated document library. Built for social-automate.com (software consulting business) and designed to be dropped into any website with a single `<script>` tag. The admin manages documents via a simple web UI; visitors get instant, accurate answers without waiting for a human response.

## Core Value

A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Visitor can ask questions via a branded chat widget embedded on any webpage
- [ ] System answers questions using content retrieved from the document library
- [ ] Admin can upload PDFs, Word docs, plain text, and markdown files via web UI
- [ ] Admin can add web pages/URLs for the system to crawl and index
- [ ] Admin can remove documents from the library
- [ ] Widget is themeable (colors, logo) to match any site's brand
- [ ] Backend runs on SiteGround shared hosting via cPanel Python Selector
- [ ] LLM answers are generated via OpenRouter API (free-tier models)
- [ ] Chat history is maintained within a session
- [ ] Admin UI is password-protected

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
