---
phase: 1
slug: infrastructure-deployment-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green + live `curl https://staging.social-automate.com/health` returns 200
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-scaffold | 01 | 1 | INFRA-01 | — | passenger_wsgi.py exists; no app.run() call | unit/smoke | `pytest tests/test_health.py -x -q` | ❌ W0 | ⬜ pending |
| 01-db-init | 01 | 1 | INFRA-02 | — | WAL mode + busy_timeout=10000 on every connection | unit | `pytest tests/test_db.py::test_db_init -x -q` | ❌ W0 | ⬜ pending |
| 01-vec-roundtrip | 01 | 1 | INFRA-02 | — | Vector insert + cosine query returns result | unit | `pytest tests/test_db.py::test_vec_round_trip -x -q` | ❌ W0 | ⬜ pending |
| 01-storage-path | 01 | 1 | INFRA-03 | Information Disclosure | Storage at ~/dochat/storage/; not under public_html | unit | `pytest tests/test_db.py::test_storage_path -x -q` | ❌ W0 | ⬜ pending |
| 01-secrets | 01 | 1 | INFRA-04 | Information Disclosure | Secrets from .env; no hardcoded values in source | unit | `pytest tests/test_config.py::test_secrets_from_env -x -q` | ❌ W0 | ⬜ pending |
| 01-health-live | 01 | 2 | INFRA-01 | — | Live URL returns 200 JSON with all fields | manual | `curl https://staging.social-automate.com/health` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — makes tests/ a package
- [ ] `tests/test_health.py` — GET /health smoke test (INFRA-01)
- [ ] `tests/test_db.py` — sqlite-vec init, WAL mode, vector round-trip, storage path (INFRA-02, INFRA-03)
- [ ] `tests/test_config.py` — secrets loaded from .env, absent from source (INFRA-04)
- [ ] `pytest.ini` — testpaths = tests, addopts = -x -q
- [ ] `pip install pytest` in local venv

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flask app responds over HTTPS via Passenger on SiteGround | INFRA-01 | Requires live SiteGround deployment; cannot be automated locally | `curl -v https://staging.social-automate.com/health` — expect 200 with JSON payload |
| sqlite_vec_mode reported correctly | INFRA-02 | Depends on SiteGround's SQLite compile flags; unknown until SSH | Check /health JSON `sqlite_vec_mode` field: "native" or "python-fallback" |
| .env file is NOT committed to git | INFRA-04 | Git history check | `git log --all --full-history -- .env` — must return no commits |
| Data files absent from public_html/ | INFRA-03 | Filesystem check on SiteGround | SSH in; verify `ls ~/public_html/dochat.db` returns no file |
