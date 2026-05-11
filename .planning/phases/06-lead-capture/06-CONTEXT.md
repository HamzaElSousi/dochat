# Phase 6: Lead Capture - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

When the RAG pipeline returns `fallback: true` (any reason), the widget replaces the fallback message with an inline lead capture form. The visitor submits their name, email, and phone. The lead is stored in SQLite and the admin receives an email notification via SMTP. After submission, the widget shows a thank-you message and a "Book a call" CTA button whose URL is fetched from a new admin-configurable Settings page. No potential lead is lost due to an unanswered question.

**In scope:**
- Inline lead capture form in the widget (name, email, phone)
- New `POST /dochat/api/leads` endpoint to save the lead
- SMTP email notification to admin on lead capture
- New `settings` table in SQLite for key-value app settings
- New Settings tab in admin nav UI (book-call URL field)
- New `GET /dochat/api/settings` endpoint (widget reads book-call URL)
- Admin leads view already exists — Phase 6 populates it with real data
- `.htaccess` patches for the new routes

**Out of scope:**
- Lead routing / CRM integration (v2)
- Email templates / HTML email (plain text only for v1)
- Admin reply-to-lead from within admin UI
- Analytics on lead conversion rate
- Spam / bot protection on the lead form

</domain>

<decisions>
## Implementation Decisions

### Form Trigger
- **D-01:** The lead form fires on ANY `fallback: true` response — similarity-gate miss, embedding failure, or LLM failure. All fallbacks are treated the same by the widget.
- **D-02:** Once a visitor submits the form in a session, subsequent `fallback: true` responses show only the FALLBACK_MESSAGE text — the form is not shown again. This is tracked via a boolean flag in widget JS state (`_leadSubmitted`).
- **D-03:** The lead form **replaces** the fallback message bubble entirely (not appended below). The form itself carries a brief heading to orient the visitor (e.g., "I couldn't find an answer — leave your details and we'll follow up.").

### Lead Form Fields
- **D-04:** Form fields: **Name**, **Email**, **Phone** (all three). Phone requires a schema migration — add `phone TEXT` column to the existing `leads` table (ALTER TABLE or recreate). The question that triggered the fallback is captured automatically from the widget's last user message (not re-typed by visitor).

### Post-Submission UX
- **D-05:** After successful form submission: form disappears, replaced with a **thank-you message** + a prominent **"Book a call" CTA button** linking to the configured URL. Both appear together.

### Email Delivery
- **D-06:** Use **Python `smtplib`** with SiteGround's outgoing SMTP server (or any SMTP). Credentials from `.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ADMIN_EMAIL`. Email sent synchronously within the `/api/leads` request (CGI — no background workers).
- **D-07:** Email body contains: visitor **name, email, phone, question, timestamp** in plain text. Subject line: `New DocChat Lead: <first 60 chars of question>`.
- **D-08:** Email failure is non-fatal — if SMTP fails, the lead is still saved to SQLite and the endpoint returns 200. Log the SMTP error to stderr.

### Book-a-Call URL — Admin Settings
- **D-09:** The book-call URL is configured by admin in a new **Settings tab** in the admin nav (alongside Docs and Leads).
- **D-10:** Backend: new `settings` table (`key TEXT PRIMARY KEY, value TEXT`). Initialized in `init_db()` via `init_settings_table()`. No pre-seeded rows — defaults to empty string.
- **D-11:** New admin routes: `GET /dochat/admin/settings` (render settings page), `POST /dochat/admin/settings` (save key-value). Protected by `@require_auth`.
- **D-12:** Widget-accessible endpoint: `GET /dochat/api/settings` — returns `{"book_call_url": "..."}`. No auth (widget is public). Widget fetches this once on init and stores in config.

### Claude's Discretion
- **D-02 (partial):** Subsequent-fallback behavior: Claude chose "show fallback text only after first submission" — cleaner UX, simple boolean flag in widget state, no re-prompting.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Phase 3 — Query Pipeline (fallback signal source)
- `app/services/query.py` — `handle_chat()` returns `{"fallback": true, ...}` in 3 paths (similarity gate, embed fail, LLM fail). All trigger the lead form per D-01.
- `app/routes/chat.py` — `/chat` endpoint. The `/api/leads` endpoint follows the same CGI/CORS pattern.

### Existing Phase 4 — Admin UI (leads view + auth pattern)
- `app/routes/admin.py` — `admin_bp` blueprint; `@require_auth` decorator pattern for protected routes. New settings routes follow this pattern.
- `app/routes/admin_api.py` — `admin_api_bp` blueprint; JSON API pattern for admin API endpoints.
- `templates/admin/base.html` — base template with Pico.css nav bar. Settings tab added here.
- `app/db.py` — `init_leads_table()` and `init_db()` pattern. New `init_settings_table()` follows this. `leads` table needs `phone` column added.

### Existing Phase 5 — Widget (integration point)
- `static/widget.js` — Shadow DOM widget. Lead form rendered inside the chat panel. Widget already reads `fallback` from API response. `DocChatConfig` object used for embed-time config. New behavior: on `fallback: true`, render form instead of text; track `_leadSubmitted` state; fetch `GET /dochat/api/settings` on init.

### Project constraints
- `.planning/PROJECT.md` — CGI deployment, no background workers, WAL mode + 10s busy timeout, no torch/transformers, data under `~/dochat/storage/`
- `.planning/ROADMAP.md` — Phase 6 success criteria (LEADS-01..04)
- `.planning/STATE.md` — accumulated key decisions from all prior phases

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/db.py:_open_db()` — reuse for all DB access in the new leads and settings routes
- `app/auth.py:require_auth` — apply to all new admin routes (settings GET/POST)
- `app/db.py:init_leads_table()` — existing `leads` table; needs `ALTER TABLE leads ADD COLUMN phone TEXT` migration (or conditional column add via PRAGMA)
- `static/admin.js` — existing JS patterns for fetch + DOM update; new settings form follows same pattern
- `templates/admin/base.html` — add "Settings" `<li>` to the nav alongside Docs and Leads

### Established Patterns
- All DB connections via `_open_db()` with WAL mode + 10s busy timeout — never bypass this
- Manual `conn.commit()` — never use `with conn:` context manager (sqlite3 BEGIN conflict, Pitfall 6)
- All new Flask routes registered via Blueprint; both `admin_bp` (UI) and `admin_api_bp` (JSON API) already registered in `create_app()`
- CORS headers pattern from `chat.py:_cors_headers()` — apply to `GET /dochat/api/settings` (public widget endpoint)
- `.htaccess` RewriteRule patches follow the pattern from `staging_htaccess_patch.txt` — append new rules for `/dochat/admin/settings`, `/dochat/api/leads`, `/dochat/api/settings`

### Integration Points
- **Widget → `/dochat/api/settings`**: Widget fetches book-call URL on init; new public GET endpoint returns JSON
- **Widget → `/dochat/api/leads`**: On form submit, POST JSON `{name, email, phone, question}`; endpoint saves to `leads` table and sends SMTP email
- **Admin nav → `/dochat/admin/settings`**: New Settings tab; GET renders form, POST saves to `settings` table
- **`leads` table schema**: Needs `phone TEXT` column — migration required before Phase 6 routes are tested

</code_context>

<specifics>
## Specific Ideas

- Settings tab sits alongside "Docs" and "Leads" in the existing Pico.css nav bar — minimal UI, just a labeled input for the book-call URL and a Save button
- Lead form heading inside widget: something like "I couldn't find an answer to that. Leave your details and we'll get back to you."
- After submission the CTA button label: "Book a Call" (or similar) — exact wording can be refined in implementation

</specifics>

<deferred>
## Deferred Ideas

- CRM integration (HubSpot, Salesforce, etc.) — post-v1
- HTML/styled email templates — v1 uses plain text only
- Admin reply-to-lead from within admin UI — post-v1
- Spam / CAPTCHA protection on the lead form — post-v1
- Lead conversion analytics — post-v1

</deferred>

---

*Phase: 6-Lead Capture*
*Context gathered: 2026-05-10*
