---
phase: 02-document-ingestion-pipeline
plan: 02
subsystem: document-ingestion-vertical-slice
tags: [file-upload, pdfplumber, python-docx, tiktoken, langchain-text-splitters, sqlite-vec, openrouter-embeddings, atomic-rollback]
dependency_graph:
  requires: [02-01-db-schema-and-auth]
  provides: [ingest-file-endpoint, parser-module, chunker-module, embedder-module, ingestion-service]
  affects: [app/ingest/parser.py, app/ingest/chunker.py, app/ingest/embedder.py, app/services/ingestion.py, app/routes/ingest.py, app/__init__.py]
tech_stack:
  added: []
  patterns: [manual-BEGIN-COMMIT-ROLLBACK, vec0-rowid-delete, os.rename-atomic-file-move, sub-batch-embedding-100, from_tiktoken_encoder-token-counting]
key_files:
  created: [app/ingest/__init__.py, app/ingest/parser.py, app/ingest/chunker.py, app/ingest/embedder.py, app/services/__init__.py, app/services/ingestion.py, app/routes/ingest.py, tests/test_ingest_upload.py]
  modified: [app/__init__.py]
decisions:
  - "chunk_size=511 (not 512) in from_tiktoken_encoder — LangChain off-by-one produces 513-token chunks at 512; 511 keeps all chunks at <=512 tokens"
  - "parse_txt alias added to parser.py for backward compatibility with any caller using parse_txt directly"
  - "ingest_file() fetches existing doc filepath BEFORE calling _delete_document() — DELETE removes the row so re-fetch is impossible after"
  - "File written to tmp before transaction — parse/chunk/embed errors abort before any DB/disk state is touched"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_created: 8
  files_modified: 1
---

# Phase 2 Plan 02: Document Ingestion Vertical Slice Summary

File ingestion endpoint (PDF/DOCX/TXT/MD) with parse+chunk+embed+store pipeline using atomic rollback, batched OpenRouter embeddings, and duplicate-replace semantics — all backed by 13 passing integration and unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Failing end-to-end tests + utility layer (parser, chunker, embedder) | 837b185 | tests/test_ingest_upload.py, app/ingest/*, app/services/__init__.py |
| 2 | Ingestion service + upload route — make all upload tests GREEN | 5f452d5 | app/services/ingestion.py, app/routes/ingest.py, app/__init__.py |

## What Was Built

### Task 1 — Utility Layer (app/ingest/)

**app/ingest/parser.py** — Text extraction from all supported formats:
- `parse_pdf(bytes)` — pdfplumber with graceful ValueError on corrupt/scanned PDFs
- `parse_docx(bytes)` — python-docx iterating both `doc.paragraphs` AND `doc.tables` (table cells not in paragraphs per OOXML structure)
- `parse_text(bytes)` — UTF-8 with latin-1 fallback; `parse_txt` alias for compatibility
- `detect_file_type(filename)` — extension-based dispatch, raises ValueError for unsupported types
- `parse_file(bytes, filetype)` — single dispatch entry point

**app/ingest/chunker.py** — Token-aware text splitting:
- `chunk_text(text)` — `RecursiveCharacterTextSplitter.from_tiktoken_encoder` with cl100k_base encoding, chunk_size=511, overlap=100
- Token counting (not character counting) ensures embedding model compatibility

**app/ingest/embedder.py** — OpenRouter batch embedding:
- `embed_chunks(texts)` — single or multi-batch call to `openai/text-embedding-3-small`
- SUBBATCH_SIZE=100: automatically splits >100 chunks into sequential batches
- Returns sorted-by-index 1536-dim float vectors

**tests/test_ingest_upload.py** — 13 tests written first (RED), then made GREEN:
- 8 endpoint integration tests (auth, size limit, type rejection, txt/pdf/docx success, corrupt PDF, duplicate replace)
- 5 utility unit tests (scanned PDF error, DOCX tables, token count, single batch, sub-batch)

### Task 2 — Ingestion Service + Upload Route

**app/services/ingestion.py** — Atomic orchestration:
- `ingest_file(conn, storage_path, bytes, filename)` — parse → chunk → embed → temp file write → BEGIN → duplicate delete → INSERT documents/chunks/vec_items/chunk_embeddings → UPDATE status=ready → COMMIT → os.rename()
- `_delete_document(conn, doc_id)` — looks up vec rowids via chunk_embeddings join, deletes from vec_items by rowid (vec0 constraint), then removes mapping/chunk/document rows
- `serialize_f32(vector)` — struct.pack for sqlite-vec binary format
- Full ROLLBACK + temp file cleanup on any exception

**app/routes/ingest.py** — Upload endpoint:
- `POST /admin/ingest/upload` protected by `@require_auth`
- `MAX_FILE_BYTES = 10 MB` enforced before any processing (413 response)
- `os.path.basename()` applied to filename — never used directly in file paths (T-02-04)
- ValueError → 422, Exception → 500 (no stack traces exposed, T-02-06)

**app/__init__.py** — Blueprint registered with `register_blueprint(ingest_bp)`

## Verification Results

```
30 passed in 2.00s
```

All 30 tests pass (17 pre-existing health/db/config + 13 new upload tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] chunk_size=511 instead of 512 to prevent 513-token chunks**
- **Found during:** Task 1 utility test verification
- **Issue:** `RecursiveCharacterTextSplitter.from_tiktoken_encoder` with `chunk_size=512` produces chunks of up to 513 tokens due to an off-by-one in LangChain's token splitter boundary algorithm
- **Fix:** Changed `CHUNK_SIZE = 511` — this produces max 512 tokens in practice (verified empirically)
- **Files modified:** app/ingest/chunker.py
- **Commit:** 837b185 (included in Task 1 commit)

## Known Stubs

None — all data flows are wired. The ingest endpoint stores real data into SQLite and vec_items.

`require_auth` remains the Phase 2 stub from Plan 01 (password-only check). This is intentional and documented — Phase 4 replaces it with full auth.

## Threat Surface

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-02-04 (path traversal via filename) | `os.path.basename()` applied to filename before use; file paths use `doc_id` (UUID) only |
| T-02-06 (stack traces in responses) | `except ValueError` exposes `str(e)` only; `except Exception` returns generic message |
| T-02-07 (temp file persists after failure) | `except` block calls `os.unlink(tmp_path)` before re-raising |
| T-02-08 (large file DoS) | 10 MB gate enforced on `len(file_bytes)` before any parsing or DB work |

## Deployment Notes

After `git pull` on SiteGround staging server:

1. **Add `.htaccess` rewrite rule** (in the existing CGI block):
   ```apache
   RewriteRule ^admin/ingest/upload/?$ /app.cgi/admin/ingest/upload [QSA,L]
   ```

2. **Install new dependencies** (all were added in Plan 01 — no new deps in Plan 02):
   ```bash
   pip install -r requirements.txt
   touch passenger_wsgi.py
   ```

## Self-Check: PASSED

All created files verified on disk:
- app/ingest/__init__.py — FOUND
- app/ingest/parser.py — FOUND
- app/ingest/chunker.py — FOUND
- app/ingest/embedder.py — FOUND
- app/services/__init__.py — FOUND
- app/services/ingestion.py — FOUND
- app/routes/ingest.py — FOUND
- tests/test_ingest_upload.py — FOUND

Both commits (837b185, 5f452d5) confirmed in git log.
