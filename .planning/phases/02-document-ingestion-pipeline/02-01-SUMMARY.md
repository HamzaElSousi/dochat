---
phase: 02-document-ingestion-pipeline
plan: 01
subsystem: database-schema-and-auth
tags: [sqlite-vec, cosine-distance, http-basic-auth, schema-foundation]
dependency_graph:
  requires: [phase-01-infrastructure]
  provides: [document-tables, vec_items-cosine, require_auth-decorator]
  affects: [app/db.py, app/auth.py, requirements.txt]
tech_stack:
  added: [pdfplumber==0.11.9, python-docx==1.2.0, trafilatura==2.0.0, langchain-text-splitters==1.1.2, tiktoken==0.12.0, pytest-mock==3.15.1]
  patterns: [init_document_tables-called-from-init_db, manual-conn.commit-no-context-manager, functools.wraps-decorator]
key_files:
  created: [app/auth.py]
  modified: [app/db.py, requirements.txt]
decisions:
  - "vec_items uses distance_metric=cosine (not L2) — Phase 3 similarity threshold ~0.35 is calibrated for cosine distance; omitting this would break Phase 3 silently"
  - "require_auth uses functools.wraps to preserve route function metadata for Flask routing"
  - "Manual conn.commit() inside init_document_tables() instead of 'with conn:' to avoid sqlite3 context manager + BEGIN conflict (RESEARCH.md Pitfall 6)"
  - "Username ignored in Basic Auth — only password checked against ADMIN_PASSWORD env var; Phase 4 will add full auth"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 2 Plan 01: DB Schema and Auth Foundation Summary

SQLite document tables (documents, chunks, vec_items with cosine distance, chunk_embeddings) and HTTP Basic Auth decorator scaffolded as prerequisite for all Phase 2 ingest routes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend app/db.py with init_document_tables() | c9fd241 | app/db.py |
| 2 | Create app/auth.py and update requirements.txt | 9183e3e | app/auth.py, requirements.txt |

## What Was Built

### Task 1 — init_document_tables() in app/db.py

Added `init_document_tables(conn)` function between `_load_sqlite_vec()` and `init_db()` in `app/db.py`. The function creates four tables:

- **documents** — primary record per uploaded file: id, filename, filetype, uploaded_at, status, chunk_count, filepath
- **chunks** — text segments with doc_id foreign key reference and chunk_index
- **vec_items** — virtual table using `vec0(embedding float[1536] distance_metric=cosine)` — cosine metric required for Phase 3 threshold of ~0.35
- **chunk_embeddings** — join table mapping chunk_id (TEXT) to vec_rowid (INTEGER)

`init_db()` now calls `init_document_tables(conn)` after `_load_sqlite_vec(conn)`.

### Task 2 — app/auth.py and requirements.txt

Created `app/auth.py` with `require_auth` decorator that:
- Reads `ADMIN_PASSWORD` from env on each request (not cached)
- Returns `401 Authentication required` with `WWW-Authenticate: Basic realm="DocChat Admin"` header when credentials are missing or password does not match
- Uses `functools.wraps` to preserve decorated function metadata

Updated `requirements.txt` with 6 new pinned dependencies:
```
pdfplumber==0.11.9
python-docx==1.2.0
trafilatura==2.0.0
langchain-text-splitters==1.1.2
tiktoken==0.12.0
pytest-mock==3.15.1
```

No forbidden packages (torch, transformers, sentence-transformers, PyMuPDF, python-magic) added.

## Verification Results

All 17 pre-existing pytest tests passed after both tasks.

Schema verification confirmed all four tables present including `vec_items` shadow tables from sqlite-vec.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

`require_auth` is documented as a Phase 2 stub. Phase 4 will replace it with rate limiting and session tokens. Current implementation intentionally minimal — password-only check protects admin endpoints against casual access.

## Threat Surface

| Boundary | Mitigation Applied |
|----------|-------------------|
| HTTP request → require_auth (T-02-01) | 401 + WWW-Authenticate header returned on password mismatch |
| vec_items distance_metric (T-02-03) | distance_metric=cosine set at CREATE TABLE time — immutable after creation |
| ADMIN_PASSWORD env var (T-02-02) | Read from os.environ on each request; never hardcoded |

## Self-Check: PASSED

All created files verified on disk. Both commits (c9fd241, 9183e3e) confirmed in git log.
