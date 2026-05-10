---
phase: 06-lead-capture
plan: "01"
subsystem: database-and-email
tags: [db-migration, smtp, sqlite, email-service, phase-6]
dependency_graph:
  requires: []
  provides:
    - app/db.py:init_leads_table (phone column, idempotent migration)
    - app/db.py:init_settings_table (settings key-value table)
    - app/services/email.py:send_lead_notification (SMTP emailer)
  affects:
    - init_db() (now calls init_settings_table)
    - All Phase 6 routes (depend on phone column + settings table)
tech_stack:
  added:
    - smtplib (stdlib — no new dependency)
    - email.message.EmailMessage (stdlib)
  patterns:
    - Idempotent ALTER TABLE via PRAGMA table_info check
    - Non-fatal SMTP failure pattern (log stderr, return False)
    - SMTP_SSL for port 465, STARTTLS for all others
key_files:
  modified:
    - app/db.py
  created:
    - app/services/email.py
decisions:
  - "PRAGMA table_info(leads) used for idempotent ALTER TABLE phone column — avoids try/except on ALTER (SQLite does not have IF NOT EXISTS for columns)"
  - "send_lead_notification returns bool (not raises) — non-fatal per D-08; caller always saves lead to DB first"
  - "Port 465 branches to SMTP_SSL; all other ports use STARTTLS — matches SiteGround hosting patterns"
metrics:
  duration: "8 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
requirements:
  - LEADS-03
  - LEADS-04
---

# Phase 6 Plan 01: DB Migrations and SMTP Email Service Summary

**One-liner:** Phone column migration + settings table via idempotent PRAGMA check, and SMTP lead notification emailer using smtplib with STARTTLS/SSL branching and non-fatal failure handling.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DB migrations — phone column + settings table | 1d72b03 | app/db.py |
| 2 | SMTP email service — app/services/email.py | 7ba706f | app/services/email.py |

## What Was Built

### Task 1 — DB Migrations (app/db.py)

- `init_leads_table()` updated: creates leads table as before, then checks `PRAGMA table_info(leads)` and runs `ALTER TABLE leads ADD COLUMN phone TEXT` only if the `phone` column is absent. Safe on both fresh DBs and existing DBs that already have the column.
- New `init_settings_table()`: creates `settings(key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')` table — used for admin-configurable settings like the book-call URL (D-10).
- `init_db()` updated: calls `init_settings_table(conn)` immediately after `init_leads_table(conn)`.

### Task 2 — SMTP Email Service (app/services/email.py)

- `send_lead_notification(name, email, phone, question, timestamp) -> bool`
- Subject: `New DocChat Lead: <first 60 chars of question>` (D-07)
- Body: plain text with name, email, phone (or "(not provided)"), question, timestamp
- Port 465 uses `smtplib.SMTP_SSL`; all other ports use `smtplib.SMTP` + `starttls()`
- All SMTP config from env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ADMIN_EMAIL`
- If any required env var is absent: logs to stderr, returns `False` immediately
- If SMTP connection/send fails: logs exception to stderr, returns `False` — never raises (D-08)

## Verification Results

- `python3 -m pytest tests/test_db.py -x -q` — 8/8 passed (backward compatible)
- Task 1 automated verify: phone column present, settings insert/fetch correct, idempotency confirmed
- Task 2 automated verify: SMTP failure returns False (not raises), subject truncates at 60 chars

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is pure infrastructure (no UI, no routes). No stub values flow to rendering.

## Threat Flags

None — no new network endpoints or auth paths introduced. SMTP credentials remain in env vars (T-06-01 accepted per threat model). ALTER TABLE idempotency guard mitigates T-06-03 per plan.

## Self-Check: PASSED

- app/db.py modified: EXISTS
- app/services/email.py created: EXISTS
- Commit 1d72b03 (Task 1): FOUND
- Commit 7ba706f (Task 2): FOUND
- 8 DB tests passing: CONFIRMED
