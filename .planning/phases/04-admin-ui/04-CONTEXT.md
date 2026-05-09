# Phase 4: Admin UI - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers a password-protected web UI for the DocChat admin. Admin can manage the full document library (upload files, submit URLs, delete documents) and review captured leads — all through a browser interface at `/dochat/admin/*`. The backend API endpoints from Phase 2/3 already exist and return JSON; this phase builds the HTML/CSS/JS layer on top. No new ingestion or query logic — Phase 4 wires the existing API into a usable UI.

**Route prefix:** `/dochat/admin` (not `/admin` — conflicts with the existing PHP site backend at social-automate.com).

</domain>

<decisions>
## Implementation Decisions

### Route Prefix (D-01)
- **D-01:** All admin routes use the prefix `/dochat/admin` (not `/admin`). The site already has a custom PHP backend at `/admin`. The DocChat admin lives at `/dochat/admin` to avoid conflict. All `.htaccess` rewrite rules must reflect this prefix.

### Authentication (D-02)
- **D-02:** Keep HTTP Basic Auth as-is. The `@require_auth` stub in `app/auth.py` already handles this — browser shows a native username/password dialog on first visit. Password from `ADMIN_PASSWORD` in `.env`. No login page, no session cookie, no new templates needed. The only change required is updating the route prefix from `/admin` to `/dochat/admin` in the rewrite rules.

### Page Structure (D-03 to D-05)
- **D-03:** Multi-route navigation: `/dochat/admin/docs` (document management) and `/dochat/admin/leads` (lead review). Both use a shared base template with a nav bar linking between them. `/dochat/admin` redirects to `/dochat/admin/docs`.
- **D-04:** `/dochat/admin/docs` layout: upload form (drag-and-drop area + URL input field) at the top, document list table below. Single page — no sub-tabs.
- **D-05:** `/dochat/admin/leads` layout: full-width table of captured leads (name, email, question, timestamp). Sortable by timestamp descending.

### CSS (D-06)
- **D-06:** Pico.css v2 via CDN (`https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css`). Classless framework — semantic HTML looks styled without class names. One `<link>` tag in the base template. Minimal custom CSS overrides in a `<style>` block for the drop zone and spinner only.

### Upload UX (D-07 to D-11)
- **D-07:** File upload and URL submission use XHR `fetch()` — not form submit + page reload. Existing endpoints return JSON; JS posts to the API and handles the response in-place. No page reload during ingestion.
- **D-08:** While ingestion runs (~5-10s), the drop zone shows a spinner and "Uploading..." message. The upload button/input is disabled during this period to prevent duplicate submissions.
- **D-09:** On success, the new document row is appended directly to the document table using the JSON response (`doc_id`, `filename`, `chunk_count`, `status`). No full page reload or list re-fetch needed.
- **D-10:** On error, an inline error message appears below the upload area (red, dismissible). The drop zone returns to its ready state so admin can retry.
- **D-11:** Document deletion uses a `DELETE /dochat/admin/docs/<doc_id>` endpoint. Clicking the ✕ button shows a `confirm()` dialog ("Delete [filename]? This removes all indexed chunks."). On confirmation, the row is removed from the table in-place. No page reload.

### Leads View (D-12)
- **D-12:** The leads table (`/dochat/admin/leads`) reads from the `leads` table that Phase 6 will create. Phase 4 must create the `leads` DB schema (so the table exists and is queryable), but the table will be empty until Phase 6 builds the capture logic. Admin sees an empty table with column headers — not an error.

### Claude's Discretion
- Exact Jinja2 template structure (base template with block inheritance vs. flat templates)
- `.htaccess` rewrite rules for `/dochat/admin/*` routes — follow existing Phase 2/3 patterns
- `DELETE /dochat/admin/docs/<doc_id>` endpoint implementation (service-layer call that removes file from disk + chunks from sqlite-vec)
- How the `leads` table schema is defined (Phase 6 will add to it; Phase 4 just needs the table to exist for the empty view)
- Vanilla JS for drag-and-drop (use native HTML5 drag events — no library needed)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Admin UI — ADMIN-01 through ADMIN-06 (all 6 requirements scoped to this phase)
- `.planning/ROADMAP.md` §Phase 4 — success criteria (5 items), goal, dependency on Phase 2 and Phase 3

### Phase Context (carry-forward decisions and constraints)
- `.planning/phases/03-query-pipeline-rag-logic/03-CONTEXT.md` — established patterns: `_open_db()`, manual `BEGIN`/`COMMIT`/`ROLLBACK`, blueprint registration, `.htaccess` rewrite rule pattern
- `.planning/phases/02-document-ingestion-pipeline/02-CONTEXT.md` — `ingest_file()` / `ingest_url()` service functions, `@require_auth` stub, storage path conventions
- `.planning/phases/01-infrastructure-deployment-validation/01-CONTEXT.md` — CGI deployment model, SiteGround constraints, `/home/customer/` path

### Existing code to read before writing new code
- `app/auth.py` — `@require_auth` decorator (HTTP Basic Auth stub); Phase 4 uses as-is, no changes needed
- `app/db.py` — `_open_db()` pattern; all DB access in new admin routes must use this
- `app/__init__.py` — Flask factory; new `admin_bp` blueprint registered here
- `app/routes/ingest.py` — existing `/admin/ingest/upload` and `/admin/ingest/url` routes; Phase 4 re-registers these under `/dochat/admin/ingest/upload` and `/dochat/admin/ingest/url`
- `app/services/ingestion.py` — `ingest_file()`, `ingest_url()` — reused directly by admin routes; also contains delete logic to implement
- `app/routes/chat.py` — blueprint pattern reference for new `admin_bp`

### Deployment
- `~/www/staging.social-automate.com/public_html/.htaccess` — must add rewrite rules for `/dochat/admin`, `/dochat/admin/docs`, `/dochat/admin/leads`, `/dochat/admin/ingest/upload`, `/dochat/admin/ingest/url`, `/dochat/admin/docs/<doc_id>` (DELETE)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/auth.py → @require_auth`: Already handles HTTP Basic Auth against `ADMIN_PASSWORD`. Apply to all `/dochat/admin/*` routes — no changes needed to the decorator itself.
- `app/db.py → _open_db()`: All DB access goes through this. New admin routes read `documents`, `chunks`, `vec_items`, and `leads` tables using this connection.
- `app/services/ingestion.py → ingest_file() / ingest_url()`: Existing service functions handle parse → chunk → embed → store pipeline. Admin upload/URL routes call these directly — no new ingestion logic needed.
- `app/routes/ingest.py → _validate_url()`: SSRF validation helper; reuse for URL submission in admin UI.

### Established Patterns
- Manual `BEGIN`/`COMMIT`/`ROLLBACK` only — no `with conn:` context manager
- All storage paths via `app.config['STORAGE_PATH']` — never construct manually
- Secrets via `os.environ.get('KEY')` — never hardcode
- Every new Flask route needs a corresponding `.htaccess` RewriteRule on the server
- Blueprint pattern: each route group in its own file under `app/routes/`, registered in `create_app()`

### Integration Points
- Phase 4 reads: `documents` table (list view), `chunks` table (chunk count per doc), `leads` table (leads view — empty until Phase 6)
- Phase 4 writes: `leads` table schema (DDL only — no data until Phase 6); deletes from `documents`, `chunks`, `chunk_embeddings`, `vec_items` on delete action
- Phase 4 calls: `ingest_file()` and `ingest_url()` from `app/services/ingestion.py`
- Phase 5 is unaffected by this phase — widget uses `POST /chat` which is unchanged
- Phase 6 will populate the `leads` table that Phase 4 creates the schema for

### New route files needed
```
app/routes/admin.py      — admin_bp: /dochat/admin, /dochat/admin/docs, /dochat/admin/leads
app/routes/admin_api.py  — admin API: POST /dochat/admin/ingest/upload,
                           POST /dochat/admin/ingest/url,
                           DELETE /dochat/admin/docs/<doc_id>
templates/admin/base.html   — base template with Pico.css CDN link + nav bar
templates/admin/docs.html   — document management page
templates/admin/leads.html  — leads review page
static/admin.js             — ~80 lines: XHR upload, drag-and-drop, delete confirm, row append
```

</code_context>

<specifics>
## Specific Ideas

- Route prefix `/dochat/admin` is locked — no deviation. Site has existing PHP backend at `/admin`.
- Pico.css v2 CDN: `https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css`
- Drop zone uses HTML5 native drag events (`dragover`, `drop`) — no third-party JS library
- The `confirm()` dialog for delete is intentional (not a custom modal) — keeps JS minimal and avoids the browser dialog blocking issue noted in system constraints for the chat widget (different context — admin panel is fine with native dialogs)
- Leads table is created in Phase 4 with correct schema so the view works; Phase 6 adds the capture route that populates it

</specifics>

<deferred>
## Deferred Ideas

- **Session-based login form** — Custom HTML login page with Flask session cookie. Deferred; HTTP Basic Auth is sufficient for a solo admin tool.
- **Re-indexing documents** — Admin clicks "Re-index" to re-chunk/re-embed an existing doc with updated settings. v2 feature (ROADMAP backlog).
- **Document preview** — Show indexed chunks for a document. v2 feature.
- **Streaming upload progress** — SSE-based real-time progress bar during chunking/embedding. Deferred (CGI SSE untested on SiteGround).
- **Rate limiting on admin routes** — Post-v1 enhancement.

</deferred>

---

*Phase: 4-Admin UI*
*Context gathered: 2026-05-09*
