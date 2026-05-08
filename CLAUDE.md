# DocChat RAG Pipeline

## Project Overview

An embeddable RAG chatbot widget for social-automate.com. Visitors ask questions; the system answers from a curated document library. Admin manages docs via a web UI. Embeds on any site with a single `<script>` tag.

See `.planning/PROJECT.md` for full context and `.planning/ROADMAP.md` for phase structure.

## GSD Workflow

This project uses the GSD (Get Shit Done) workflow system.

**Current phase:** Phase 1 — Infrastructure & Deployment Validation
**Next command:** `/gsd-discuss-phase 1` or `/gsd-plan-phase 1`

**Workflow commands:**
- `/gsd-plan-phase N` — create a plan for phase N
- `/gsd-execute-phase N` — execute the plan for phase N
- `/gsd-progress` — check project status
- `/gsd-discuss-phase N` — discuss approach before planning

## Key Technical Decisions

- **Framework:** Flask 3.x (not FastAPI — Passenger is WSGI, FastAPI is ASGI)
- **Vector store:** sqlite-vec (not ChromaDB — RAM limits on shared hosting)
- **LLM:** OpenRouter API — `google/gemma-3-27b-it:free` (primary), `qwen/qwen3-next-80b-a3b-instruct:free` (fallback)
- **Embeddings:** OpenRouter `text-embedding-3-small` API (not local — PyTorch OOM risk)
- **Hosting:** SiteGround shared hosting via cPanel Python Selector (Passenger WSGI)
- **Widget:** Vanilla JS, Shadow DOM, single `<script>` tag embed

## Hard Rules

- **NEVER** add `torch`, `transformers`, or `sentence-transformers` to requirements — OOM kill on shared hosting
- **NEVER** store data files under `public_html/` — use `~/dochat/storage/`
- **NEVER** hardcode secrets — all from `.env`
- **ALWAYS** initialize sqlite-vec with WAL mode and 10s busy timeout
- FastAPI is disqualified — use Flask only
