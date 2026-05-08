# STATE: DocChat RAG Pipeline

*Project memory — updated at every phase transition and plan completion.*

---

## Project Reference

**Core Value:** A visitor asks a question and gets a correct, sourced answer from your actual documents — not a hallucination and not a dead end.
**Current Focus:** Phase 1 — Infrastructure & Deployment Validation
**Milestone:** v1 — Embeddable RAG chatbot on SiteGround shared hosting

---

## Current Position

**Phase:** 1 of 6 — Infrastructure & Deployment Validation
**Plan:** None started
**Status:** Not started

**Progress:**
```
Phase 1 [          ] 0%
Phase 2 [          ] 0%
Phase 3 [          ] 0%
Phase 4 [          ] 0%
Phase 5 [          ] 0%
Phase 6 [          ] 0%

Overall [          ] 0%
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0 / 6 |
| Plans complete | 0 / ? |
| Requirements mapped | 34 / 34 |
| Requirements done | 0 / 34 |
| Last session | 2026-05-07 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale | Phase |
|----------|-----------|-------|
| Flask over FastAPI | FastAPI is ASGI — incompatible with Passenger WSGI on SiteGround | Research |
| sqlite-vec over ChromaDB | Single-file SQLite backend; ChromaDB's HNSW index needs too much RAM | Research |
| OpenRouter embeddings API | PyTorch/sentence-transformers would OOM-kill on shared hosting | Research |
| INGEST-04 (URL crawl) in Phase 2 | Same ingestion pipeline as file upload — no separate phase needed | Roadmap |
| WAL mode + 10s busy timeout | Prevents SQLite write contention with single Passenger worker | Research |
| Data files outside public_html | Security: `~/dochat/storage/` is not web-accessible | Research |

### Open Questions / Risks

- SiteGround's actual CloudLinux RAM limit for this plan — must verify via SSH (`cat /proc/self/status`)
- System SQLite version on SiteGround — if < 3.41, need `pysqlite3-binary` workaround
- Whether `PassengerMaxPoolSize 1` in `.htaccess` is honored (single-worker enforcement)
- OpenRouter free model availability at project start — re-verify `google/gemma-3-27b-it:free` status

### Todos (Carry Forward)

- [ ] SSH into SiteGround and run: `python3 --version`, `sqlite3 --version`, `cat /proc/self/status`, `ulimit -v`
- [ ] Verify Gemma 3 27B `:free` is listed in OpenRouter model catalog before writing LLM call code

### Blockers

None currently.

---

## Session Continuity

### Last Session (2026-05-07)

**What happened:** Project initialized. Research completed. Requirements defined (34 v1). Roadmap created (6 phases). STATE.md initialized.

**Where we stopped:** Roadmap written. Ready to begin Phase 1 planning.

**Next action:** Run `/gsd-plan-phase 1` to decompose Phase 1 into executable plans.

---

## Phase Completion Log

| Phase | Completed | Notes |
|-------|-----------|-------|
| — | — | No phases complete yet |

---
*STATE initialized: 2026-05-07*
*Last updated: 2026-05-07 after roadmap creation*
