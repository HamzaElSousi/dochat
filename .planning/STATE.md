# STATE: DocChat RAG Pipeline

*Project memory — updated at every phase transition and plan completion.*

---

## Project Reference

**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.
**Current Focus:** Phase 6 — Lead Capture
**Milestone:** v1 — Embeddable RAG chatbot on SiteGround shared hosting

---

## Current Position

**Phase:** 6 of 6 — Lead Capture (IN PROGRESS — discussion phase)
**Status:** Phase 6 starting — all prior phases complete; discussing approach
**Last session:** 2026-05-10 — Phase 4 confirmed complete (14/14 tests, human UAT passed on staging); Phase 6 discussion starting

**Progress:**
```
Phase 1 [##########] 100% ✅
Phase 2 [##########] 100% ✅ (4/4 plans)
Phase 3 [##########] 100% ✅ (5/5 plans)
Phase 4 [##########] 100% ✅ (4/4 plans, 14/14 tests, human UAT passed)
Phase 5 [##########] 100% ✅ (3/3 plans complete)
Phase 6 [▓         ] 0%  (discussion in progress)

Overall [##########] 97%
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 5 / 6 (Phase 1, 2, 3, 4, 5) |
| Plans complete | 4 / 4 (Phase 4) |
| Requirements mapped | 34 / 34 |
| Requirements done | 29 / 34 (INFRA-01..04, INGEST-01..07, QUERY-01..05, ADMIN-01..06, WIDGET-01..08 done) |
| Last session | 2026-05-10 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale | Phase |
|----------|-----------|-------|
| widget_js() route in create_app() (not Blueprint) | Single static-file route — no extra module/file needed; Blueprint overhead unwarranted | Phase 5 |
| send_from_directory resolves app/static/ via __file__ | app/__init__.py static_folder points to root static/ (different dir); explicit path required | Phase 5 |
| .htaccess rule uses anchored pattern with escaped dot | Matches Phase 4 format; ^dochat/widget\.js$ prevents wildcard traversal (T-05-10) | Phase 5 |
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
| _call_llm_with_retry catches RequestException (superset) | Covers connection-level failures beyond just Timeout+HTTPError; documented deviation from plan | Phase 3 |
| _call_llm wraps choices[0] access in try/except | OpenRouter returns 200 with no choices on content-filter refusals; KeyError/IndexError bypasses fallback without the guard | Phase 3 |
| ALLOWED_ORIGINS read at module load (CGI safe) | Fresh process per CGI request means module is re-imported each time — env vars are effectively per-request | Phase 3 |
| archive_sessions.py standalone (no Flask context) | Cron jobs cannot instantiate a Flask app; uses sys.path + _open_db() directly | Phase 3 |

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

### Last Session (2026-05-10)

**What happened:** Confirmed Phase 4 (Admin UI) fully complete — STATE.md had stale 20% entry. All 4 plans executed, 14/14 tests passing, human UAT passed on staging (docs page, file upload/delete, leads empty state). Phase 6 (Lead Capture) discussion starting.

**Where we stopped:** Beginning Phase 6 discussion.

**Next action:** `/gsd-plan-phase 6` after discussion completes

---

## Phase Completion Log

| Phase | Completed | Notes |
|-------|-----------|-------|
| 1 — Infrastructure & Deployment Validation | 2026-05-09 | CGI deployment, native sqlite-vec, live on staging |
| 2 — Document Ingestion Pipeline | 2026-05-09 | PDF/DOCX/TXT/URL ingest, chunking, embeddings, 50/50 tests |
| 3 — Query Pipeline & RAG Logic | 2026-05-09 | handle_chat() RAG pipeline, /chat endpoint, CORS, archive cron, 62/62 tests |
| 4 — Admin UI | 2026-05-09 | Password-protected docs + leads UI, upload/delete API, 14/14 tests, human UAT passed on staging |
| 5 — Chat Widget | 2026-05-10 | Shadow DOM widget.js, chip backend, Flask widget delivery route, 95/95 tests, human-verified embed |

---
*STATE initialized: 2026-05-07*
*Last updated: 2026-05-10 — Phase 4 confirmed complete; Phase 6 discussion starting*
