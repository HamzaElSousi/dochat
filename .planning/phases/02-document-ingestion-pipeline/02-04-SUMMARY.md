---
phase: 02-document-ingestion-pipeline
plan: 04
subsystem: ingestion-service-tests
tags: [pytest, service-tests, rollback, chunking, batching, duplicate-replace, tiktoken, sqlite-vec]
dependency_graph:
  requires: [02-02-ingestion-vertical-slice]
  provides: [service-layer-test-coverage, ingestion-correctness-verification]
  affects: [tests/test_ingestion_service.py]
tech_stack:
  added: []
  patterns: [direct-service-call-test, mocker-patch-requests-post, db-state-inspection, subbatch-verification]
key_files:
  created: [tests/test_ingestion_service.py]
  modified: []
decisions:
  - "Tests bypass HTTP layer and call ingest_file() directly — DB state inspected via app.config['DB_CONN']"
  - "test_ingest_url.py failures acknowledged as expected — Plan 03 (URL route) runs in parallel and was not yet complete when suite ran"
  - "ingestion.py pre-existing change (ingest_url added by Plan 03 parallel agent) left unstaged — only test file committed"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-09"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 2 Plan 04: Service-Layer Ingestion Tests Summary

12 service-layer unit and integration tests verifying atomic rollback, token-aware chunking (<=512 cl100k_base tokens), batched OpenRouter embedding (sub-batch at 100), and duplicate-replace semantics — all passing against the Plan 02 implementation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Service-layer tests — rollback, chunking, batching, duplicate-replace | a84901a | tests/test_ingestion_service.py |

## What Was Built

### tests/test_ingestion_service.py

12 tests that call the ingestion service and embedder directly (no HTTP layer):

**Rollback tests (INGEST-07):**
- `test_rollback_on_embed_failure` — documents + chunks tables are empty after HTTPError
- `test_rollback_on_embed_failure_no_vec_rows` — chunk_embeddings table is empty after HTTPError
- `test_rollback_no_temp_file_on_disk` — no .txt files remain in tmp dir after failure

**Batch embedding tests (INGEST-06):**
- `test_embed_batch_single_call` — short text produces exactly 1 requests.post call
- `test_embed_subbatch_101_chunks` — 101 chunks split into 2 batches of 100 + 1

**Chunking tests (INGEST-05):**
- `test_chunk_size_token_limit` — every chunk from chunk_text() has <= 512 cl100k_base tokens
- `test_chunk_overlap` — consecutive chunks share token overlap > 0

**DB state tests:**
- `test_ingest_txt_db_rows` — documents/chunks/chunk_embeddings all populated after successful ingest
- `test_ingest_file_filepath_set` — documents.filepath contains doc_id and 'original.txt'; file exists on disk

**Duplicate-replace tests (D-07):**
- `test_duplicate_replace_single_doc_row` — same filename uploaded twice = exactly 1 documents row
- `test_duplicate_replace_old_vectors_gone` — old chunks and chunk_embeddings deleted after replace; new chunks present

**Error handling:**
- `test_ingest_no_stack_trace_on_parse_error` — unsupported file type raises ValueError at service layer

## Verification Results

```
tests/test_ingestion_service.py — 12 passed in 1.91s
Full suite (excluding Plan 03 pending tests) — 42 passed
```

The 5 failures in `tests/test_ingest_url.py` are expected — Plan 03 (URL ingestion route) runs in parallel in Wave 3 and had not yet completed when this plan executed. Those tests are Plan 03's responsibility.

## Deviations from Plan

### Noted (not deviations)

**1. ingestion.py had ingest_url() added by Plan 03 parallel agent**
- Found during pre-commit `git diff` review
- The parallel Plan 03 agent added `ingest_url()` to `app/services/ingestion.py`
- This change was left unstaged (not this plan's responsibility) — only `tests/test_ingestion_service.py` was committed
- No impact on Plan 04 tests

**2. test_ingest_url.py pre-existing failures**
- Plan 03 created `tests/test_ingest_url.py` as part of its TDD RED phase but the implementation (the route) was not yet committed when Plan 04 ran
- These 5 failures are expected in Wave 3 execution context and are not regressions introduced by Plan 04
- After Plan 03 commits its implementation, all 5 will pass

## Known Stubs

None — all tests verify real service behavior against the Plan 02 implementation.

## Threat Flags

None — this plan only adds test files; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- tests/test_ingestion_service.py — FOUND (277 lines)
- Commit a84901a — FOUND in git log
- grep -c "test_rollback" = 3 (>= 2 required) — PASS
- grep -c "chunk_embeddings" = 11 (>= 3 required) — PASS
- grep -c "test_embed_subbatch_101_chunks" = 1 — PASS
- grep -c "test_chunk_size_token_limit" = 1 — PASS
- grep -c "cl100k_base" = 3 (>= 1 required) — PASS
- pytest tests/test_ingestion_service.py -v exits 0 — PASS (12 passed)
