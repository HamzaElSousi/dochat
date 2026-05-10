---
phase: 04-admin-ui
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - app/__init__.py
  - app/db.py
  - app/routes/admin.py
  - app/routes/admin_api.py
  - staging_htaccess_patch.txt
  - static/admin.js
  - templates/admin/base.html
  - templates/admin/docs.html
  - templates/admin/leads.html
  - tests/test_admin.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 4 delivers an Admin UI with document management (upload, URL crawl, delete) and a leads view, protected by HTTP Basic Auth. The overall structure is sound — auth is applied consistently, SQL uses parameterized queries throughout, and XSS is mitigated in dynamically-built JS HTML. However, three blockers were found: a stored XSS vector in Jinja templates, a timing-safe password comparison bypass, and a missing CSRF defence on all state-mutating API endpoints. Four warnings cover additional robustness gaps.

---

## Critical Issues

### CR-01: Stored XSS — Jinja templates render user-controlled data without escaping

**File:** `templates/admin/docs.html:50-57`, `templates/admin/leads.html:18-22`

**Issue:** Jinja2's auto-escape is disabled by default for files with `.html` extension **unless** the Flask app is created with `render_template` pointing at a Jinja `Environment` that has `autoescape=True`. Flask's own `render_template` enables auto-escape for `.html` files since Flask 2.2, but the behaviour is template-engine-version-dependent and the project does not explicitly configure it. Regardless of auto-escape behaviour, the templates render `doc.status` and `doc.type` as bare CSS class name suffixes:

```html
<!-- docs.html line 53 -->
<span class="status-badge status-{{ doc.status }}">{{ doc.status }}</span>
```

`doc.status` comes from the `documents.status` column, which is set by the ingestion pipeline. If an attacker can control the status value (e.g., via a crafted filename or a compromised ingestion path), the class attribute will contain arbitrary text. Even with auto-escape, `class="status-<script>"` is not a valid XSS vector via attributes alone — but the deeper issue is in `docs.html:56`:

```html
<button ... aria-label="Delete {{ doc.filename }}" title="Delete document">
```

`doc.filename` is rendered unescaped inside an attribute. If auto-escape is not active (confirmed absent from `create_app()`), this is a stored XSS sink. An attacker who uploads a file named `x" onmouseover="alert(1)` would inject event handlers.

More critically, `leads.html` renders `lead.question` and `lead.name` without any escaping:

```html
<td>{{ lead.name }}</td>
<td>{{ lead.question }}</td>
```

Lead data originates from external visitor input (Phase 6 capture form). Stored XSS through the leads table is a realistic attack path. Even if Flask auto-escape is active, this must be verified explicitly and not relied on implicitly.

**Fix:** Explicitly configure auto-escape on the Flask app and add an assertion in tests, OR use `{{ value | e }}` everywhere user-controlled data is rendered. Also add a `Content-Security-Policy` header:

```python
# In create_app(), after app is created:
from jinja2 import Environment
app.jinja_env.autoescape = True  # explicit — do not rely on Flask's heuristic

@app.after_request
def set_csp(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; style-src 'self' cdn.jsdelivr.net; script-src 'self'"
    )
    return response
```

---

### CR-02: Timing-safe password comparison not used — Basic Auth susceptible to timing attacks

**File:** `app/auth.py:29`

**Issue:** The password check uses direct string equality:

```python
if not auth or auth.password != admin_password:
```

Python string comparison (`!=`) short-circuits on the first non-matching byte. This makes the `ADMIN_PASSWORD` value recoverable by a remote timing oracle: an attacker sends thousands of requests with passwords of increasing prefix length and measures response latency. On a shared hosting server with variable network jitter this is harder to exploit than on a LAN, but it is a textbook vulnerability for authentication code.

**Fix:** Replace with `hmac.compare_digest`:

```python
import hmac

if not auth or not hmac.compare_digest(auth.password, admin_password):
```

`hmac.compare_digest` runs in constant time regardless of where the strings diverge.

---

### CR-03: No CSRF protection on state-mutating endpoints

**File:** `app/routes/admin_api.py:13`, `app/routes/admin_api.py:62`, `app/routes/admin_api.py:101`

**Issue:** All three POST/DELETE endpoints (`/dochat/admin/ingest/upload`, `/dochat/admin/ingest/url`, `/dochat/admin/docs/<doc_id>`) are protected only by HTTP Basic Auth. Modern browsers send credentials with cross-origin requests when the user has an active Basic Auth session in the browser. A malicious page loaded in the same browser session can issue:

```javascript
// Attacker page — no user interaction required
fetch('https://staging.social-automate.com/dochat/admin/docs/real-doc-id', {
  method: 'DELETE',
  credentials: 'include'
});
```

Because the browser automatically re-sends Basic Auth credentials for the origin, this request succeeds silently. Every admin action (upload, crawl, delete) is vulnerable.

**Fix:** Add a `Referer`/`Origin` check as a minimal mitigation (appropriate for a single-admin tool), or add a CSRF token. The simplest defence for this architecture:

```python
# In require_auth or a separate before_request check for mutating methods:
from flask import request, abort

def check_csrf():
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        origin = request.headers.get('Origin') or request.headers.get('Referer', '')
        allowed = os.environ.get('ADMIN_ORIGIN', '')
        if allowed and allowed not in origin:
            abort(403)
```

Alternatively, use Flask-WTF with CSRF protection enabled for the session.

---

## Warnings

### WR-01: `doc_id` path parameter is passed unsanitized to a URL-derived `fetch()` path

**File:** `static/admin.js:135`

**Issue:** The delete button's `data-doc-id` attribute value comes from the server-rendered HTML (server-side the IDs are UUIDs, so this is low-risk in practice). However, the `deleteDoc` function constructs the fetch URL via direct string concatenation:

```javascript
fetch('/dochat/admin/docs/' + docId, { method: 'DELETE' })
```

If `docId` ever contains characters like `../` (e.g., if a non-UUID value ends up in the table), this becomes a path traversal in the fetch URL. Additionally, `docId` is read from `data-doc-id` which is populated from `appendDocRow` via `escapeHtml` — but `escapeHtml` does not encode `/` or `.`, so a `doc_id` containing `../something` would silently produce a request to the wrong endpoint.

**Fix:** Validate that `docId` matches the expected UUID format before building the URL:

```javascript
function deleteDoc(docId, filename) {
  if (!/^[0-9a-f-]{36}$/.test(docId)) {
    showError('Invalid document ID.');
    return;
  }
  // ...
}
```

---

### WR-02: `admin_delete_doc` silently swallows all exceptions — error details lost

**File:** `app/routes/admin_api.py:124-132`

**Issue:** The bare `except Exception` catch in the delete route suppresses the exception entirely with no logging:

```python
except Exception:
    conn.execute("ROLLBACK")
    return jsonify({"error": "Internal server error during deletion"}), 500
```

If `_delete_document` raises for any reason (DB constraint violation, vec_items rowid mismatch, etc.), the operator has no diagnostic information. The same pattern exists in `admin_upload` (line 43) and `admin_url_ingest` (line 83). Phase 2 already established a logging pattern in `chat.py`.

**Fix:** Log the exception before returning 500:

```python
import traceback

except Exception:
    conn.execute("ROLLBACK")
    current_app.logger.error("Deletion failed for doc_id=%s: %s", doc_id, traceback.format_exc())
    return jsonify({"error": "Internal server error during deletion"}), 500
```

---

### WR-03: `_format_datetime` uses `%-d` (Linux-only strftime directive)

**File:** `app/routes/admin.py:14`

**Issue:**

```python
return dt.strftime('%b %-d, %Y %H:%M')
```

`%-d` (day without zero-padding) is a glibc extension supported on Linux but not on macOS (`%e` is the macOS equivalent) and not on Windows. If any developer runs the test suite on macOS or Windows, `_format_datetime` will throw `ValueError: Invalid format string`. The test suite currently exercises `admin_docs_page_renders` and `admin_leads_page_renders` which call this function indirectly — they will fail on non-Linux systems, masking real test failures.

**Fix:**

```python
# Platform-independent: strip leading zero manually
day = str(dt.day)
return dt.strftime(f'%b {day}, %Y %H:%M')
```

---

### WR-04: `escapeHtml` does not encode single quotes — `aria-label` attribute injection possible

**File:** `static/admin.js:150-156`

**Issue:**

```javascript
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

The function escapes double-quotes but not single quotes (`'`). In `appendDocRow`, filenames are used inside double-quoted HTML attributes (`aria-label="Delete ..."`) — those are safe. However, if the rendering context ever changes to single-quoted attributes, or if `escapeHtml` is reused in a context with single-quote delimiters, the omission becomes a XSS vector. The `confirm()` dialog also uses unescaped filename directly:

```javascript
// admin.js line 134
if (!confirm('Delete ' + filename + '? This removes all indexed chunks.')) return;
```

`filename` here is read from `data-filename` which was escaped through `escapeHtml`, but `escapeHtml` does not encode `'`. A filename containing `' + alert(1) + '` would break out of the string in the `confirm()` call in older browsers.

**Fix:** Add `'` encoding to `escapeHtml`:

```javascript
.replace(/'/g, '&#x27;')
```

---

## Info

### IN-01: `admin.js` loaded on all pages including leads (no-op elements)

**File:** `templates/admin/base.html:101`

**Issue:** `admin.js` is included in the base template and thus loaded on the leads page. The script references `drop-zone`, `file-input`, `doc-table-body`, etc., which do not exist on the leads page. The `DOMContentLoaded` handler guards every lookup with `if (element)` checks, so no runtime errors occur. However, the JS bundle is unnecessarily executed on every admin page.

**Fix:** Either split the JS into page-specific scripts, or conditionally include it:

```html
{% if active_page == 'docs' %}
<script src="{{ url_for('static', filename='admin.js') }}"></script>
{% endif %}
```

---

### IN-02: `staging_htaccess_patch.txt` — `[QSA]` flag passes arbitrary query strings to admin routes

**File:** `staging_htaccess_patch.txt:11-16`

**Issue:** All rewrite rules use `[QSA,L]` (Query String Append). This means any query string appended to an admin URL is forwarded to the Flask app. Flask ignores unknown query params, so this is not a security vulnerability by itself — but it means `GET /dochat/admin/docs?foo=../../etc/passwd` is routed to the Flask handler with those params accessible via `request.args`. If any future code inspects `request.args` without validation, the `QSA` flag becomes a vulnerability enabler.

**Fix:** For admin routes that take no query parameters, omit `QSA` and use just `[L]`:

```apache
RewriteRule ^dochat/admin/?$  /app.cgi/dochat/admin [L]
```

---

_Reviewed: 2026-05-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
