# Phase 1: Infrastructure & Deployment Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 1-Infrastructure & Deployment Validation
**Areas discussed:** Scaffold vs. probe, Deploy workflow, sqlite-vec failure plan, Validation evidence

---

## Scaffold vs. Probe

| Option | Description | Selected |
|--------|-------------|----------|
| Real scaffold | Phase 1 creates passenger_wsgi.py, app/__init__.py, folder layout, .env.example, requirements.txt. Future phases expand this — no rework. | ✓ |
| Throwaway probe | A single validation.py script that tests each constraint and prints PASS/FAIL, then gets deleted. Phase 2 starts from scratch. | |

**User's choice:** Real scaffold

---

### Health-check endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| Health-check endpoint | GET /health returns JSON with sqlite_vec_version, storage_path, storage_writable | ✓ |
| App structure only | Just folder layout, no routes. Validation via logs or separate test script. | |

**User's choice:** Health-check endpoint

---

### Health endpoint access

| Option | Description | Selected |
|--------|-------------|----------|
| Public | No auth on /health — easiest to test, exposes no sensitive data. | ✓ |
| Token-protected | Require X-Health-Token header from .env. | |

**User's choice:** Public

---

## Deploy Workflow

### Deployment method

| Option | Description | Selected |
|--------|-------------|----------|
| SSH + git pull | Push to GitHub, SSH into SiteGround, run git pull. Clean and repeatable. | ✓ |
| SFTP file upload | Manual upload via SFTP client. Easy but error-prone. | |
| cPanel Git Version Control | SiteGround's built-in cPanel Git feature. Less control. | |

**User's choice:** SSH + git pull

---

### Remote repo

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub | Push to GitHub; SSH into SiteGround and git clone/pull. | ✓ |
| GitLab | Same pattern on GitLab. | |
| No remote — direct SSH push | SiteGround as git remote. No offsite backup. | |

**User's choice:** GitHub

---

### App restart method

| Option | Description | Selected |
|--------|-------------|----------|
| Touch passenger_wsgi.py | Standard Passenger restart signal. Fast, scriptable. | ✓ |
| tmp/restart.txt | Alternative Passenger signal — depends on SiteGround config. | |
| Let Phase 1 figure it out | Test both during Phase 1 and document which one works. | |

**User's choice:** Touch passenger_wsgi.py

---

## sqlite-vec Failure Plan

### Primary contingency

| Option | Description | Selected |
|--------|-------------|----------|
| Switch to VPS immediately | If sqlite-vec fails, conclude SiteGround is incompatible, move to VPS. | |
| Try pure-Python fallback first | sqlite-vec has a pure Python mode — test before declaring incompatible. | |
| Document and continue anyway | Use temporary placeholder; unblock Phase 2 delivery. | |

**User's choice:** (Other — freeform) "Not sure, I would much rather keep the hosting on SiteGround."
**Notes:** User strongly prefers SiteGround. VPS is last resort only.

---

### Fallback reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back silently, call it a pass | If native fails, use Python-only sqlite-vec. Phase 1 passes as long as vector ops work. | |
| Flag as degraded, investigate | If native fails, /health reports sqlite_vec_mode: python-fallback with warning. Phase 1 completes but degradation is documented. | ✓ |

**User's choice:** Flag as degraded, investigate

---

## Validation Evidence

### Definition of done

| Option | Description | Selected |
|--------|-------------|----------|
| Live URL response | curl staging.social-automate.com/health returns passing JSON. Unambiguous, sharable. | ✓ |
| SSH test script output | python validate.py on SiteGround prints PASS/FAIL. No public URL needed. | |
| Both — script first, then URL | Run validation script during setup, then confirm live URL as final sign-off. | |

**User's choice:** Live URL response

---

### App location

| Option | Description | Selected |
|--------|-------------|----------|
| Subdomain (chat.social-automate.com) | Chatbot at its own subdomain. | |
| Path on main domain (/chat) | Lives under the main site. Requires SCRIPT_NAME config. | |
| Temporary staging URL | Use SiteGround's temporary URL for Phase 1 only. | |

**User's choice:** (Other — freeform) "root of staging subdomain is the site. Figure out something else or if possible keep hovering widget at all the pages, as for the standalone page at /dochat/"
**Notes:** staging.social-automate.com is the staging environment. The dochat app is the root of this subdomain. Widget embedding across pages + /dochat/ page deferred to Phase 5.

---

### Staging vs. root

| Option | Description | Selected |
|--------|-------------|----------|
| Root of staging subdomain | staging.social-automate.com IS the dochat app. All routes live there. | ✓ |
| Sub-path (/dochat/) | Chatbot under /dochat/ — allows other things at staging root. | |

**User's choice:** Root of staging subdomain

---

## Claude's Discretion

- sqlite-vec initialization sequence (WAL pragma + busy_timeout order) — follow CLAUDE.md hard rules exactly
- Python version selection for cPanel Python Selector virtualenv — 3.11+ preferred
- .env.example key list — at minimum OPENROUTER_API_KEY, ADMIN_PASSWORD, SECRET_KEY

## Deferred Ideas

- **Widget hovering on all pages + standalone /dochat/ page** — Phase 5 (Chat Widget). User mentioned wanting the floating widget embeddable across all staging pages and a standalone page at `/dochat/`. This belongs in Phase 5 scope.
