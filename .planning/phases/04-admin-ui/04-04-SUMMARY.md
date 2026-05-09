---
phase: 04-admin-ui
plan: "04"
subsystem: testing, deployment
tags: [pytest, admin, auth, htaccess, cgi, verification]

# Dependency graph
requires:
  - phase: 04-admin-ui
    plan: "01"
    provides: admin_bp/admin_api_bp stubs with @require_auth on all routes
  - phase: 04-admin-ui
    plan: "02"
    provides: admin route implementations, HTML templates with drop-zone/doc-table-body
  - phase: 04-admin-ui
    plan: "03"
    provides: POST upload, POST url-ingest, DELETE doc API endpoints
provides:
  - tests/test_admin.py — 14-test suite covering ADMIN-01 through ADMIN-06
  - staging_htaccess_patch.txt — 6 RewriteRule entries for all /dochat/admin/* paths
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "io.BytesIO wrapper required for multipart file uploads in Flask test client (not raw bytes)"
    - "Pre-insert document row before mock ingest call — route SELECTs filetype/uploaded_at from DB after ingest returns"
    - "conn.in_transaction guard before BEGIN in test setup — prevents OperationalError on nested transaction"

key-files:
  created:
    - tests/test_admin.py
    - staging_htaccess_patch.txt
  modified: []

key-decisions:
  - "io.BytesIO wrapping for multipart uploads — Flask test client requires BytesIO, not raw bytes (Rule 1 auto-fix)"
  - "staging_htaccess_patch.txt contains 6 anchored RewriteRule patterns for /dochat/admin/* (T-04-13 mitigation)"
  - "ADMIN-01 through ADMIN-06 all covered; checkpoint reached at human-verify gate for live staging verification"

requirements-completed:
  - ADMIN-01
  - ADMIN-02
  - ADMIN-03
  - ADMIN-04
  - ADMIN-05
  - ADMIN-06

# Metrics
duration: 15min
completed: 2026-05-09
---

# Phase 4 Plan 04: Admin Test Suite + .htaccess Patch Summary

**14-test admin test suite covering all 6 ADMIN requirements and staging .htaccess patch file with 6 RewriteRule entries for all /dochat/admin/* routes**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-09T18:25:00Z
- **Completed:** 2026-05-09T18:40:35Z
- **Tasks:** 1 auto task + 1 artifact (staged for human checkpoint)
- **Files created:** 2

## Accomplishments

- Created `tests/test_admin.py` with 14 tests covering ADMIN-01 through ADMIN-06:
  - ADMIN-01: 5 tests — auth protection on docs, leads, upload, delete routes + root redirect
  - ADMIN-02: 3 tests — upload no-file 400, upload too-large 413, upload success 200
  - ADMIN-03: 2 tests — url-ingest missing 400, url-ingest success 200
  - ADMIN-04: 1 test — docs page renders with drop-zone, doc-table-body, "Indexed Documents"
  - ADMIN-05: 2 tests — delete not-found 404, delete success 200 + DB verification
  - ADMIN-06: 1 test — leads page renders with "Captured Leads" and empty-state message
- Created `staging_htaccess_patch.txt` with 6 RewriteRule entries for `/dochat/admin/*`
- Full test suite: 76 tests passing (62 prior + 14 new admin tests)

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Admin test suite (14 tests, all 6 requirements) | e878259 | tests/test_admin.py |
| 2 | Staging .htaccess patch with 6 RewriteRule entries | 5d69b16 | staging_htaccess_patch.txt |

## Verification Results

All acceptance criteria verified pre-checkpoint:

- `grep -c "def test_admin" tests/test_admin.py` → 14 (requirement: ≥ 12)
- `pytest tests/test_admin.py --tb=short` → 0 (all 14 pass)
- `pytest tests/ --tb=short` → 0 (76/76 pass, no regressions)
- `grep -c "ADMIN-01\|ADMIN-02\|ADMIN-03\|ADMIN-04\|ADMIN-05\|ADMIN-06" tests/test_admin.py` → 14
- `grep -c "dochat/admin" staging_htaccess_patch.txt` → 9 (6 RewriteRule patterns + comments)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] io.BytesIO wrapper required for multipart file uploads**
- **Found during:** Task 1 test execution (test_admin_upload_too_large, test_admin_upload_success)
- **Issue:** Flask test client requires `io.BytesIO` objects for multipart file fields, not raw `bytes`. The plan template used `(big_bytes, 'large.pdf')` with raw bytes — this caused 400 (no file recognized) instead of 413.
- **Fix:** Wrapped all file bytes in `io.BytesIO()` before passing to `data={'file': (io.BytesIO(bytes), 'filename')}`. Added `import io` to test file. Matches the pattern in `tests/test_ingest_upload.py`.
- **Files modified:** `tests/test_admin.py`
- **Commit:** e878259 (fix included in same commit — caught in first test run)

## Checkpoint Status

Plan 04 has reached the `checkpoint:human-verify` gate. All automated work is complete:

- `tests/test_admin.py` — 14 tests, all passing
- `staging_htaccess_patch.txt` — ready to apply to staging server

**Awaiting:** Human to apply `.htaccess` patch on staging server, deploy, and verify live admin UI loads at `https://staging.social-automate.com/dochat/admin/docs`.

## Known Stubs

None — all tests exercise real routes. `staging_htaccess_patch.txt` is a complete, ready-to-apply file.

## Threat Surface Scan

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-04-13 | RewriteRules use anchored `^dochat/admin` patterns with `[L]` flag | Mitigated in staging_htaccess_patch.txt |
| T-04-14 | Staging .htaccess does not expose secrets | Accepted — staging only |

No new threat surface introduced beyond what was planned.

## Self-Check: PASSED

Files verified:
- [FOUND] tests/test_admin.py
- [FOUND] staging_htaccess_patch.txt
- [FOUND] .planning/phases/04-admin-ui/04-04-SUMMARY.md

Commits verified:
- [FOUND] e878259 test(04-04): add admin test suite covering all 6 ADMIN requirements
- [FOUND] 5d69b16 docs(04-04): add staging .htaccess patch for all /dochat/admin/* routes

76/76 tests passing.
