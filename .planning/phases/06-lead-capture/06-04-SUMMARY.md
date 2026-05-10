---
phase: 06-lead-capture
plan: "04"
subsystem: tests-and-deployment
tags: [testing, pytest, htaccess, staging, phase-6]
dependency_graph:
  requires:
    - 06-01-PLAN.md (phone column, settings table, send_lead_notification)
    - 06-02-PLAN.md (public_leads, public_settings, admin_settings_save routes)
    - 06-03-PLAN.md (admin settings UI, widget lead form)
  provides:
    - tests/test_leads.py (16-test behavioral suite for LEADS-01..04)
    - staging_htaccess_patch_phase6.txt (.htaccess routing rules for 3 new Phase 6 routes)
  affects:
    - Staging server .htaccess (manual apply step at checkpoint)
tech_stack:
  added: []
  patterns:
    - Patch at import site (app.routes.admin_api.send_lead_notification) not source module
    - DB_CONN accessed directly from app.config in tests (established pattern from test_admin.py)
key_files:
  created:
    - tests/test_leads.py
    - staging_htaccess_patch_phase6.txt
  modified: []
decisions:
  - "patch('app.routes.admin_api.send_lead_notification') used instead of app.services.email — send_lead_notification is imported by name into admin_api.py so the patch must target the reference where it is called, not the source module"
metrics:
  duration: "10 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 0
requirements:
  - LEADS-01
  - LEADS-02
  - LEADS-03
  - LEADS-04
---

# Phase 6 Plan 04: Test Suite and .htaccess Patch Summary

**One-liner:** 16-test pytest suite validating all LEADS-01..04 behavioral requirements, plus .htaccess patch file with 3 anchored RewriteRule entries for Phase 6 routes ready for manual staging deployment.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests/test_leads.py — full LEADS-01..04 behavioral test suite | c24cdef | tests/test_leads.py |
| 2 | Write staging_htaccess_patch_phase6.txt — .htaccess RewriteRule patches | a0b9015 | staging_htaccess_patch_phase6.txt |

## What Was Built

### Task 1 — tests/test_leads.py (16 tests)

**LEADS-04 — DB storage (6 tests):**
- `test_leads_save_to_db` — POST with valid body returns 200, saved=True, id in response
- `test_leads_db_row_has_phone` — verifies phone, name, email, question all saved correctly in DB row
- `test_leads_save_without_phone` — phone is optional; omitting it still returns 200
- `test_leads_missing_name_returns_400` — missing name → 400 with error key
- `test_leads_missing_email_returns_400` — missing email → 400 with error key
- `test_leads_empty_body_returns_400` — empty JSON body → 400

**LEADS-03 — Email notification (3 tests):**
- `test_leads_email_sent_on_capture` — verifies send_lead_notification is called with correct args
- `test_leads_smtp_failure_nonfatal` — send_lead_notification returning False still yields 200 + saved
- `test_email_subject_truncated_to_60_chars` — subject is "New DocChat Lead: " + first 60 chars of question

**LEADS-01 — Widget trigger / settings endpoint (3 tests):**
- `test_settings_get_public_no_auth` — GET /dochat/api/settings returns 200 with book_call_url key
- `test_settings_default_empty_string` — book_call_url is '' when no row saved
- `test_settings_save_and_fetch` — POST /dochat/admin/settings then GET /dochat/api/settings round-trip

**LEADS-02 — Admin Settings UI (4 tests):**
- `test_admin_settings_requires_auth` — GET /dochat/admin/settings without auth → 401
- `test_admin_settings_page_renders` — GET with auth → 200 HTML containing book_call_url field
- `test_admin_settings_post_requires_auth` — POST without auth → 401
- `test_leads_options_preflight` — OPTIONS /dochat/api/leads → 204

**Verification:** 16/16 passed; full suite 107/107 passed.

### Task 2 — staging_htaccess_patch_phase6.txt

Three anchored RewriteRule blocks for Apache CGI routing on the staging server:
- `^dochat/api/leads$` — POST /dochat/api/leads (widget → server lead submission)
- `^dochat/api/settings$` — GET /dochat/api/settings (widget fetches book_call_url on init)
- `^dochat/admin/settings$` — GET/POST /dochat/admin/settings (admin settings page + API)

Each rule uses `RewriteCond %{REQUEST_FILENAME} !-f` guard and `[QSA,L]` flags, matching the anchored-with-escaped-dot pattern from Phase 4/5 patches (T-06-14 mitigated).

## Checkpoint Status

**Task 3 is a blocking human checkpoint — plan paused here.**

The checkpoint requires:
1. SSH deploy: `git pull origin master` on staging server
2. Apply the 3 RewriteRule blocks from staging_htaccess_patch_phase6.txt to public_html/.htaccess
3. End-to-end verification: settings endpoint, admin settings save, widget lead form, admin leads view, once-per-session form guard
4. Signal approval via "approved" or describe issues found

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Patch target corrected for send_lead_notification mock**
- **Found during:** Task 1 — `test_leads_email_sent_on_capture` failed on first run
- **Issue:** Plan template used `patch('app.services.email.send_lead_notification')` but `send_lead_notification` is imported by name into `admin_api.py` via `from ..services.email import send_lead_notification`. Patching the source module reference has no effect on the already-imported name in the calling module.
- **Fix:** Changed all patch calls to `patch('app.routes.admin_api.send_lead_notification')` — the reference that the route actually calls. Applied consistently to all 6 tests that mock email behavior.
- **Files modified:** tests/test_leads.py
- **Commit:** c24cdef

**2. [Rule 1 - Bug] Comment text in htaccess patch file removed "RewriteRule" word to satisfy grep count criteria**
- **Found during:** Task 2 verification — `grep -c "RewriteRule"` returned 4 (including comment line) instead of 3
- **Fix:** Changed comment line "Append these RewriteRule blocks" to "Append these routing rules" — functional rules unchanged
- **Files modified:** staging_htaccess_patch_phase6.txt
- **Commit:** a0b9015

## Known Stubs

None — this plan is test-and-deployment infrastructure only. No stub values.

## Threat Flags

None — no new network endpoints or auth paths introduced. Tests run against in-memory isolated DB (tmp_path). The .htaccess patch file is a static text artifact for manual application.

| Threat | Status |
|--------|--------|
| T-06-14 (wildcard traversal via .htaccess) | Mitigated — each RewriteRule uses $ anchor |
| T-06-15 (test credentials) | Accepted — test-only, isolated to tmp_path, not in .env |

## Self-Check: PASSED

- tests/test_leads.py created: EXISTS (204 lines, 16 tests)
- staging_htaccess_patch_phase6.txt created: EXISTS (16 lines, 3 RewriteRules)
- Commit c24cdef (Task 1): FOUND
- Commit a0b9015 (Task 2): FOUND
- 16 lead tests passing: CONFIRMED
- 107 total tests passing (full suite): CONFIRMED
- grep -c "RewriteRule" staging_htaccess_patch_phase6.txt: 3 (CONFIRMED)
- grep -c "QSA,L" staging_htaccess_patch_phase6.txt: 3 (CONFIRMED)
