# Phase 1: Infrastructure & Deployment Validation - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers a confirmed-working deployment environment on SiteGround shared hosting. No application feature logic is written here — the output is a real project scaffold (Flask factory, sqlite-vec init, passenger_wsgi.py) with a live `/health` endpoint returning a passing JSON payload at `staging.social-automate.com/health`. Every subsequent phase builds on this scaffold.

</domain>

<decisions>
## Implementation Decisions

### Project Scaffold
- **D-01:** Phase 1 produces the **real project scaffold** that Phases 2–6 will build on — not a throwaway validation probe. No rework required when Phase 2 begins.
- **D-02:** Scaffold structure:
  ```
  dochat/
  ├── passenger_wsgi.py       # SiteGround Passenger entry point
  ├── app/
  │   ├── __init__.py         # Flask application factory
  │   └── db.py               # sqlite-vec init (WAL mode, 10s busy timeout)
  ├── requirements.txt
  ├── .env.example
  └── storage/                # symlink or reference to ~/dochat/storage/
  ```
- **D-03:** A **public** `GET /health` endpoint is included in the scaffold. It returns JSON confirming each constraint:
  ```json
  {
    "status": "ok",
    "sqlite_vec_version": "...",
    "sqlite_vec_mode": "native",
    "storage_path": "/home/.../dochat/storage",
    "storage_writable": true
  }
  ```
  No auth on `/health` — exposes no sensitive data, easiest to verify during Phase 1.

### Deploy Workflow
- **D-04:** Code is deployed via **SSH + `git pull` from GitHub**. Workflow: push to GitHub → SSH into SiteGround → `git pull` in the app directory.
- **D-05:** App restart signal is **`touch passenger_wsgi.py`** — standard Phusion Passenger restart mechanism. Run after every `git pull`.

### sqlite-vec Failure Handling
- **D-06:** sqlite-vec is the locked vector store choice (no ChromaDB, no FAISS). If the native `.so` extension fails to load (old SQLite version, extension loading blocked), fall back to **pure-Python sqlite-vec mode** automatically.
- **D-07:** If the pure-Python fallback is active, `/health` reports it as a **degraded state**:
  ```json
  {
    "sqlite_vec_mode": "python-fallback",
    "warning": "native extension unavailable — investigate SQLite version"
  }
  ```
  Phase 1 still completes (vector insert + retrieval must still work), but the degradation is documented. The VPS is a last resort only — user preference is to stay on SiteGround.

### Validation Target
- **D-08:** Phase 1 is complete when `https://staging.social-automate.com/health` returns a passing JSON payload (all checks green, no degraded warnings). Live URL is the definitive proof — not a local script.
- **D-09:** The dochat app is the **root of `staging.social-automate.com`** — not a sub-path. Routes: `/health`, `/api/*`, `/admin/*` all live at the staging subdomain root.
- **D-10:** `social-automate.com` is the prod environment. Phase 1 stays on staging. Promotion to prod happens after validation passes.

### Claude's Discretion
- sqlite-vec initialization details (WAL pragma, busy_timeout pragma sequence) — follow the pattern in CLAUDE.md hard rules exactly.
- Python virtualenv setup via cPanel Python Selector — standard SiteGround procedure, planner can choose the Python version (3.11+ preferred).
- `.env.example` keys to include — at minimum: `OPENROUTER_API_KEY`, `ADMIN_PASSWORD`, `SECRET_KEY`. Planner can add any others needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` — Phase 1 success criteria (4 items), phase goal, requirements mapped (INFRA-01 through INFRA-04)
- `.planning/REQUIREMENTS.md` — INFRA-01, INFRA-02, INFRA-03, INFRA-04 (the 4 requirements this phase satisfies)
- `.planning/PROJECT.md` — hosting context, key decisions, constraints section

### Hard Rules
- `CLAUDE.md` — Hard rules that MUST be followed: never torch/transformers/sentence-transformers; WAL mode + 10s busy timeout on sqlite-vec; data files at ~/dochat/storage/ not public_html/; secrets from .env only; Flask only (not FastAPI)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — fresh project with no existing code.

### Established Patterns
- None yet — Phase 1 establishes the patterns that all subsequent phases follow.

### Integration Points
- `passenger_wsgi.py` is the entry point SiteGround's Passenger will invoke — all Flask routing flows through here.
- `~/dochat/storage/` is the data root for all phases — Phase 1 confirms it's writable and correctly referenced.

</code_context>

<specifics>
## Specific Ideas

- User has `staging.social-automate.com` wired up and ready to use as the Phase 1 test target.
- The widget embed (floating button on all pages, standalone `/dochat/` page) was mentioned — captured as deferred to Phase 5.

</specifics>

<deferred>
## Deferred Ideas

- **Widget embedding on all staging pages + standalone /dochat/ page** — Phase 5 (Chat Widget). User wants the floating widget to be embeddable across all pages and a standalone page at `/dochat/`. This is within Phase 5's scope (Shadow DOM embed, `<script>` tag, `DocChatConfig`).

</deferred>

---

*Phase: 1-Infrastructure & Deployment Validation*
*Context gathered: 2026-05-08*
