# Project Research Summary

**Project:** DocChat RAG Pipeline
**Domain:** Embeddable RAG chatbot for a software consulting website (single-tenant, shared hosting)
**Researched:** 2026-05-07
**Confidence:** HIGH

## Executive Summary

DocChat is a single-tenant, admin-managed RAG chatbot widget that lets visitors ask questions answered from a curated knowledge base of uploaded PDFs, DOCX files, and crawled URLs. The system must run on SiteGround shared hosting (Passenger WSGI + CloudLinux RAM caps), which is the single most constraining factor in every technology decision. Every stack decision follows one principle: offload heavy compute (embeddings, LLM inference) to external APIs and keep the local process footprint minimal.

The recommended approach: **Flask** (native WSGI, no deployment workarounds), **sqlite-vec** (single-file vector store, zero RAM overhead), and **OpenRouter** for both embeddings (`text-embedding-3-small`) and LLM inference (`google/gemma-3-27b-it:free`, `qwen/qwen3-next-80b-a3b-instruct:free` fallback). Two independent pipelines share one Flask process: ingestion (admin-triggered) and query (visitor-triggered).

---

## Recommended Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Web framework | Flask 3.x | Native WSGI — works on Passenger with zero config. FastAPI is ASGI and incompatible. |
| Vector store | sqlite-vec | Single `.db` file, no RAM index, zero build deps (prebuilt wheels). ChromaDB's HNSW needs too much RAM. |
| LLM | Gemma 3 27B via OpenRouter (free) | 131K context, strong Q&A, free tier. Qwen3 80B as fallback. |
| Embeddings | text-embedding-3-small via OpenRouter API | ~$0.01/month at this scale. PyTorch/sentence-transformers adds 200–420 MB RAM — OOM risk. |
| PDF parsing | PyMuPDF 1.24+ | Fastest, best recall, prebuilt binary wheel. |
| DOCX parsing | python-docx 1.1+ | De facto standard, pure Python, no native deps. |
| URL crawling | trafilatura 1.12+ | Highest F1 accuracy (0.945), handles malformed HTML. |
| Chunking | langchain-text-splitters (RecursiveCharacterTextSplitter) | 512 tokens, 100-token overlap. No PyTorch needed. |
| Token counting | tiktoken | Lightweight, no ML deps. |

**Critical exclusion:** Never add `torch`, `transformers`, or `sentence-transformers` to requirements. OOM kill on shared hosting.

---

## Expected Features

### Table Stakes (must have)
- Accurate answers with explicit "I don't know" fallback
- Source citations on every answer (document name + chunk context)
- Session-based chat history (in-memory)
- Typing indicator, sub-5-second response
- Responsive mobile widget (bottom-right FAB)
- Branded appearance via CSS custom properties
- Admin password protection

### Differentiators (high ROI)
- Document name + section citation line below each answer — trust signal
- Out-of-scope redirect with CTA ("book a call") — converts dead-ends into leads
- Suggested follow-up question chips — reduces user effort
- Shadow DOM isolation — prevents host site CSS from breaking widget
- Similarity threshold gate (cosine ~0.35) — prevents hallucination on off-topic queries

### Defer to v2+
- Streaming responses (SSE) — infra complexity on Passenger
- Analytics dashboard — no users to analyze yet
- Hybrid search (BM25 + vector) — dense-only sufficient for small corpus
- Cross-encoder re-ranking — memory budget unknown
- Multi-tenant, voice input, multilingual

---

## Architecture Summary

**Two pipelines, one Flask process:**

**Ingestion (admin-triggered):**
`file upload / URL → parse → RecursiveCharacterTextSplitter (512t/100t overlap) → OpenRouter embeddings API (batched) → sqlite-vec`

**Query (visitor-triggered):**
`user message → embed → sqlite-vec top-k=4 search → similarity threshold gate → context assembly (tiktoken-bounded) → 10-turn history → OpenRouter LLM → answer + citations`

**Component boundaries:**
- Flask backend: all business logic, API keys, vector store access
- sqlite-vec `.db` file: vectors + metadata table in one file, stored outside `public_html/`
- Vanilla JS widget: display layer only — no API keys, sends/receives JSON to `/api/chat`
- Admin UI: Jinja2 templates, HTTP Basic Auth gate on all `/admin/*` routes
- `passenger_wsgi.py`: two-line WSGI entry, `from app import app as application`

---

## Top Pitfalls

| # | Pitfall | Severity | Prevention |
|---|---------|----------|------------|
| 1 | OOM from PyTorch/sentence-transformers | CRITICAL | Never add to requirements; use OpenRouter embeddings API |
| 2 | SQLite write contention ("database is locked") | CRITICAL | WAL mode + 10s busy timeout at startup; single Passenger worker |
| 3 | Embedding model mismatch after model change | CRITICAL | Store model name in metadata; assert on startup |
| 4 | Hallucination on off-topic queries | HIGH | Similarity threshold gate; return fallback if no chunk passes |
| 5 | OpenRouter free tier exhausted (50 req/day) | HIGH | Purchase $10 credits (unlocks 1000/day); implement fallback model list |
| 6 | CORS blocking widget on external sites | HIGH | Configure CORSMiddleware; test cross-origin before shipping widget |
| 7 | SQLite version < 3.41 on SiteGround | MEDIUM | Check `sqlite3 --version` via SSH; add `pysqlite3-binary` if needed |
| 8 | Files stored under `public_html/` | CRITICAL | Store all data files at `~/dochat/storage/`, never in webroot |
| 9 | Fixed-size chunking splits mid-sentence | MEDIUM | Use RecursiveCharacterTextSplitter with `["\n\n", "\n", ". "]` separators |
| 10 | JS-rendered URLs indexed as empty | MEDIUM | Reject if extracted text < 200 chars; show clear admin error |

---

## Roadmap Implications

**Suggested phases (6 total):**

1. **Infrastructure & Deployment Validation** — Validate SiteGround compatibility (pip installs, SQLite version, RAM budget, Passenger WSGI config) before writing application logic. Highest-risk unknown.
2. **Ingestion Pipeline** — File upload, parse (PDF/DOCX/TXT/MD), chunk, embed, store in sqlite-vec. Sets chunking strategy and metadata schema — expensive to change after indexing.
3. **Query Pipeline & RAG Logic** — Embed query, vector search, similarity threshold, context assembly, LLM call, session history, source citations. Tune threshold empirically against real documents.
4. **Admin UI** — Jinja2 admin wrapper (upload, URL crawl, document list, delete, auth). Internal tool — scope to 5 operations only.
5. **Widget** — Vanilla JS client with Shadow DOM, CORS validation, UX polish, themeable via config.
6. **URL Ingestion** — trafilatura crawl with JS-rendering detection. Isolated failure mode, deferred.

**Phase ordering rationale:** SiteGround compatibility is the hardest unknown — validate first. Ingestion before query because chunking/metadata decisions are expensive to change. Admin before widget because widget needs real documents to test meaningfully. URL ingestion last — lower priority, isolated.

**Research flags needing validation:**
- Phase 1: Confirm SiteGround's SQLite version and actual CloudLinux RAM limit via SSH
- Phase 3: Tune similarity threshold (start at 0.35) empirically against real documents

---

## Gaps to Verify in Phase 1

1. Actual SiteGround CloudLinux RAM limit for the specific plan — `cat /proc/self/status` or `ulimit -v` via SSH
2. SiteGround's system SQLite version — if < 3.41, add `pysqlite3-binary` workaround
3. Whether `PassengerMaxPoolSize 1` is honored in `.htaccess` (single-worker enforcement)
4. OpenRouter free model availability at project start — re-verify Gemma 3 27B `:free` status

---
*Research completed: 2026-05-07*
*Ready for roadmap: yes*
