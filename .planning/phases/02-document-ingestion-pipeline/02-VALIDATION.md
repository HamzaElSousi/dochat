---
phase: 2
slug: document-ingestion-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 |
| **Config file** | none (pytest auto-discovers tests/) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|----------|-----------|-------------------|-------------|--------|
| 02-01-01 | 02-01 | 1 | INGEST-01..07 | DB schema + cosine vec0 + auth stub | unit | `pytest tests/test_db.py -x -q` | ✅ | ⬜ pending |
| 02-01-02 | 02-01 | 1 | INGEST-01..07 | requirements.txt additions installable | manual/lint | `pip install -r requirements.txt --dry-run` | ✅ | ⬜ pending |
| 02-02-01 | 02-02 | 2 | INGEST-01,02,03,05,06 | parser+chunker+embedder utilities | unit (mock) | `pytest tests/test_ingestion_service.py -x -k "parse or chunk or embed"` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02-02 | 2 | INGEST-01,02,03,05,06,07 | /admin/ingest/upload endpoint + rollback | integration (mock) | `pytest tests/test_ingest_upload.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 02-03 | 3 | INGEST-04 | trafilatura fetch + URL parser unit | unit (mock) | `pytest tests/test_ingest_url.py -x -k "fetch"` | ❌ W0 | ⬜ pending |
| 02-03-02 | 02-03 | 3 | INGEST-04,07 | /admin/ingest/url endpoint | integration (mock) | `pytest tests/test_ingest_url.py -x -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 02-04 | 3 | INGEST-05,06,07,D-07 | rollback, chunking, batching, duplicate-replace | unit (mock) | `pytest tests/test_ingestion_service.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ingest_upload.py` — stubs for INGEST-01, INGEST-02, INGEST-03, INGEST-07, D-03, D-07
- [ ] `tests/test_ingest_url.py` — stubs for INGEST-04, JS-only URL → 422
- [ ] `tests/test_ingestion_service.py` — stubs for INGEST-05 (chunk size), INGEST-06 (batch embed mock), rollback, duplicate-replace
- [ ] `pytest-mock==3.15.1` added to requirements.txt

---

## Mock Strategy for OpenRouter

```python
# In tests, patch the requests.post call in app.services.ingestion:

def test_embed_batch_calls_once(mocker, app):
    """Verify embed_chunks sends all chunks in one POST, not N posts."""
    mock_post = mocker.patch('app.services.ingestion.requests.post')
    mock_post.return_value.json.return_value = {
        "data": [{"embedding": [0.1] * 1536, "index": i} for i in range(3)]
    }
    mock_post.return_value.raise_for_status = lambda: None

    from app.services.ingestion import embed_chunks
    result = embed_chunks(["chunk1", "chunk2", "chunk3"])

    assert mock_post.call_count == 1
    call_args = mock_post.call_args
    assert len(call_args.kwargs['json']['input']) == 3
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| .htaccess RewriteRules applied on server | D-10 | Server-side file not in git | SSH to server, `grep -n "ingest" ~/www/staging.social-automate.com/public_html/.htaccess` — must show upload and url rewrite rules |
| Live CGI response to POST /admin/ingest/upload | INGEST-01 | Requires live SiteGround environment | `curl -u admin:$ADMIN_PASSWORD -F "file=@sample.pdf" https://staging.social-automate.com/admin/ingest/upload` — must return `{"doc_id": ..., "chunk_count": N, "status": "indexed"}` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
