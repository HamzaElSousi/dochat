# STATE: DocChat RAG Pipeline

*Project memory — updated at every phase transition and plan completion.*

---

## Project Reference

**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.
**Current Focus:** Phase 3 — Query Pipeline & RAG Logic
**Milestone:** v1 — Embeddable RAG chatbot on SiteGround shared hosting

---

## Current Position

**Phase:** 3 of 6 — Query Pipeline & RAG Logic
**Status:** Phase 3 in progress — Plan 01 complete (1/5 plans done)
**Last session:** 2026-05-09 — Phase 3 Plan 01 executed (sessions table, embed_query wrapper, chat_bp stub; 50/50 tests pass)

**Progress:**
```
Phase 1 [##########] 100% ✅
Phase 2 [##########] 100% ✅ (4/4 plans)
Phase 3 [##        ] 20% (1/5 plans done)
Phase 4 [          ] 0%
Phase 5 [          ] 0%
Phase 6 [          ] 0%

Overall [####      ] 31%
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 1 / 6 |
| Plans complete | 1 / 5 (Phase 3) |
| Requirements mapped | 34 / 34 |
| Requirements done | 10 / 34 (INFRA-01..04 done; INGEST-01,02,03,05,06,07 done; INGEST-04 URL in progress) |
| Last session | 2026-05-09 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Flask over FastAPI | FastAPI is ASGI — incompatible with Passenger WSGI on SiteGround | Research |
| sqlite-vec over ChromaDB | Single-file SQLite backend; ChromaDB's HNSW index needs too much RAM | Research |
| OpenRouter embeddings API | PyTorch/sentence-transformers would OOM-kill on shared hosting | Research |
| INGEST-04 (URL crawl) in Phase 2 | Same ingestion pipeline as file upload — no separate phase needed | Roadmap |
| WAL mode + 10s busy timeout | Prevents SQLite write contention with single worker | Research |
| Data files outside public_html | Security: `~/dochat/storage/` is not web-accessible | Research |
| CGI over Passenger WSGI | SiteGround shared hosting has no Passenger or mod_wsgi — CGI is the only option | Phase 1 |
| Shebang path is `/home/customer/` | SiteGround resolves home as `/home/customer/` not `/home/<username>/` — use in all shebangs | Phase 1 |
| DocChat routes are surgical .htaccess inserts | Staging public_html is a live PHP site — only `/health`, `/api/*` routed to CGI | Phase 1 |
| vec_items uses distance_metric=cosine | Phase 3 similarity threshold ~0.35 is calibrated for cosine; omitting defaults to L2 breaking Phase 3 silently | Phase 2 |
| Manual conn.commit() in init_document_tables() | Avoids sqlite3 context manager + BEGIN conflict (RESEARCH.md Pitfall 6) | Phase 2 |
| require_auth checks only password, not username | Username ignored; Phase 4 will add full auth (rate limiting, session tokens) | Phase 2 |
| chunk_size=511 not 512 in from_tiktoken_encoder | LangChain off-by-one produces 513-token chunks at 512; 511 keeps all chunks at <=512 tokens | Phase 2 |
| ingest_file() fetches existing filepath BEFORE _delete_document() | DELETE removes the row so re-fetch is impossible after; filepath needed to remove orphaned file | Phase 2 |
| sessions table uses manual conn.commit() (not context manager) | Consistent with init_document_tables() idiom — avoids sqlite3 context manager + BEGIN conflict | Phase 3 |
| chat_bp stub created in Plan 01 before Plan 03 route file exists | Allows app factory to import cleanly and existing tests to pass; Plan 03 replaces stub | Phase 3 |
| embed_query() delegates to embed_chunks([text])[0] | Thin wrapper reuses all existing error handling; zero new dependencies | Phase 3 |

### Resolved Questions (from Phase 1)

| Question | Answer |
|----------|--------|
| Python version on SiteGround | 3.14.3 |
| sqlite-vec native mode available | Yes — `enable_load_extension` works, mode = native |
| HOME path for shebangs | `/home/customer/` (symlink — always use this) |
| Passenger available | No |
| mod_wsgi available | No |
| Deployment method | Apache CGI via `wsgiref.handlers.CGIHandler` |

### Open Questions / Risks

- RAM limit on this SiteGround plan — run `cat /proc/self/status` during Phase 2 to check VmPeak
- OpenRouter free model availability — verify `google/gemma-3-27b-it:free` before writing LLM call code
- CGI process-per-request means no in-memory state between requests — session handling needs to be DB-backed

### Todos (Carry Forward)

- [ ] Verify Gemma 3 27B `:free` is listed in OpenRouter model catalog before writing LLM call code
- [ ] Add `/api/chat` and future routes to .htaccess CGI block as Phase 3 is built

### Blockers

None currently.

---

## Session Continuity

### Last Session (2026-05-09)

**What happened:** Phase 3 Plan 01 executed. Sessions table DDL added to app/db.py, embed_query() wrapper added to app/ingest/embedder.py, chat_bp stub wired into app/__init__.py. All 50 existing tests still pass. Zero deviations from plan.

**Where we stopped:** Phase 3 Wave 1 complete. Wave 2 starts with 03-02 (query service) and 03-04 (archive cron) — these can run in parallel.

**Next action:** `/gsd-execute-phase 3` for Plan 02 (query service)

---

## Phase Completion Log

| Phase | Completed | Notes |
|-------|-----------|-------|
| 1 — Infrastructure & Deployment Validation | 2026-05-09 | CGI deployment, native sqlite-vec, live on staging |

---
*STATE initialized: 2026-05-07*
*Last updated: 2026-05-09 after Phase 1 completion*
