---
phase: 05-chat-widget
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - app/services/query.py
  - app/routes/chat.py
  - app/static/widget.js
  - app/__init__.py
  - tests/test_chat_chips.py
  - tests/test_parse_chips_red.py
  - tests/test_widget_delivery.py
  - staging_widget_htaccess_patch.txt
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: fixed
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-10
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase delivers three main components: (1) the `_parse_chips` / `handle_chat` logic in `query.py`, (2) the `/chat` Flask route in `chat.py`, and (3) the `widget.js` Shadow DOM widget. The overall architecture is sound, but there are three blocker-level defects: an XSS vulnerability in the widget, a DOM-injection path for user text via `addErrorBubble`, and a session-fixation attack vector in the chat route. There are also several warnings covering input validation gaps, a silent API-key omission, a data-loss path in session management, and test coverage holes.

---

## Critical Issues

### CR-01: XSS via `innerHTML` in `addErrorBubble` — user-controlled class injected into SVG/span

**File:** `app/static/widget.js:511-512`
**Issue:** `addErrorBubble` uses raw `innerHTML` to write an SVG icon plus a hardcoded error string. While the string itself is hardcoded, the pattern is dangerous: the function is called from the `.catch` branch of `sendMessage`, which only receives an opaque `Error` object today, but the error _message_ is never shown. The real problem is that `addBotBubble` (line 483) uses `div.textContent = text` (safe), yet bot `text` originates from `data.answer` on line 561, which is the raw server JSON value — entirely attacker-controlled if the server is ever compromised or the `apiUrl` is pointed at a rogue host. However the immediate, exploitable vector is in `addErrorBubble` itself: it builds the DOM element with `innerHTML` without sanitizing, and any future change that interpolates a variable into that string introduces XSS inside the Shadow DOM. More critically, the chip buttons at line 494 call `sendMessage(q)` where `q` is a chip string from the server; `addUserBubble` (line 461) sets `div.textContent = text` (safe), but nothing prevents a future refactor from switching to `innerHTML`. The direct, current-code bug: **`addErrorBubble` sets `div.innerHTML` with a string that concatenates an SVG literal and a `<span>` — if the error message were ever interpolated here, it would be an XSS sink.** The rule in CLAUDE.md ("NEVER hardcode secrets") implies a security-conscious codebase; using `innerHTML` for DOM construction should be banned project-wide.

**Fix:** Replace the `innerHTML` assignment with safe DOM construction:
```js
function addErrorBubble() {
  var div = document.createElement('div');
  div.className = 'dc-bubble dc-bubble-error';
  // Build SVG via createElementNS to avoid innerHTML entirely
  var ns = 'http://www.w3.org/2000/svg';
  var svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '16'); svg.setAttribute('height', '16');
  svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', '#ef4444'); svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round');
  var circle = document.createElementNS(ns, 'circle');
  circle.setAttribute('cx', '12'); circle.setAttribute('cy', '12'); circle.setAttribute('r', '10');
  var l1 = document.createElementNS(ns, 'line');
  l1.setAttribute('x1', '12'); l1.setAttribute('y1', '8'); l1.setAttribute('x2', '12'); l1.setAttribute('y2', '12');
  var l2 = document.createElementNS(ns, 'line');
  l2.setAttribute('x1', '12'); l2.setAttribute('y1', '16'); l2.setAttribute('x2', '12.01'); l2.setAttribute('y2', '16');
  svg.appendChild(circle); svg.appendChild(l1); svg.appendChild(l2);
  var span = document.createElement('span');
  span.textContent = 'Something went wrong. Check your connection and try again.';
  div.appendChild(svg); div.appendChild(span);
  messages.appendChild(div);
  scrollToBottom();
  return div;
}
```

---

### CR-02: CSS injection via `DocChatConfig` color/font values written directly into `style.textContent`

**File:** `app/static/widget.js:44-51`
**Issue:** Every `cfg.*` value from `window.DocChatConfig` is interpolated verbatim into the CSS `<style>` string that is written into the Shadow DOM. An attacker who can influence the host page's `window.DocChatConfig` (e.g., via a stored XSS on the embedder's site, or a misconfigured CDN) can inject arbitrary CSS, including `</style><script>alert(1)</script>` sequences, or can use CSS `expression()` (IE) or `url("javascript:")` constructs. The Shadow DOM boundary does **not** protect against CSS injection that breaks out of the style block.

Example attack: if `cfg.primaryColor` is set to `red; } body { display:none } :host {`, the layout of the outer page is disrupted. With a `</style><img src=x onerror=...>` payload it becomes XSS against the embedder page.

**Fix:** Validate each config value before interpolating into CSS. Reject anything that is not a valid CSS token:
```js
function sanitizeCssValue(val, fallback) {
  if (typeof val !== 'string') return fallback;
  // Allow only safe CSS value characters: alphanumeric, #, %, px, em, space, comma, dot, parens, dash
  if (/[<>"'`{}\\;]/.test(val)) return fallback;
  return val;
}

// Then replace all cfg.* uses in the style string:
'  --dc-primary:     ' + sanitizeCssValue(cfg.primaryColor, '#3b82f6') + ';',
// ...etc for all 7 color/dimension properties
```

---

### CR-03: Session fixation — client-supplied `session_id` is never validated

**File:** `app/routes/chat.py:59`, `app/services/query.py:175-177`
**Issue:** The chat route accepts `session_id` from the POST body without any validation:
```python
session_id = data.get('session_id') or None
```
`handle_chat` then passes it directly to `_load_session` and `_save_session`. An attacker can:
1. Supply any arbitrary string as `session_id` — including another user's valid UUID — and read that user's conversation history (which is loaded into the LLM context at step 5, line 234).
2. Supply a crafted `session_id` to inject messages into another session's history by triggering `_save_session`.

There is no ownership check, no format validation (UUID format), and no rate-limiting. This is a session fixation / session hijacking vulnerability — the server trusts the client to self-identify.

**Fix:** At minimum, validate the format is a UUID before using it:
```python
import re
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

session_id_raw = data.get('session_id') or None
session_id = session_id_raw if (session_id_raw and _UUID_RE.match(session_id_raw)) else None
```
Note: format validation alone does not prevent hijacking of a known valid UUID. A proper fix requires associating sessions with a server-side token (e.g., a signed cookie or HMAC-signed session_id). At minimum, the format guard prevents injection of specially crafted strings that could break SQL queries or cause unexpected behavior.

---

## Warnings

### WR-01: Empty `OPENROUTER_API_KEY` causes silent 401s instead of a clear startup error

**File:** `app/services/query.py:32`
**Issue:** `api_key = os.environ.get('OPENROUTER_API_KEY', '')` defaults to an empty string. If the env var is missing, every LLM call silently degrades to `FALLBACK_MESSAGE` (because `_call_llm_with_retry` swallows the 401 from OpenRouter). There is no startup-time check. This means a misconfigured deployment looks "working" but never actually answers questions from documents — it always falls back. Operators get no alert.

**Fix:** Add a validation check in `create_app()` or at module load in `query.py`:
```python
# In query.py at module level (after imports):
if not os.environ.get('OPENROUTER_API_KEY'):
    import warnings
    warnings.warn(
        "OPENROUTER_API_KEY is not set — all LLM calls will fail and return fallback message.",
        RuntimeWarning,
        stacklevel=2,
    )
```

---

### WR-02: `_save_session` silently rolls back on conflict — data loss in multi-request race

**File:** `app/services/query.py:118-119`
**Issue:** The function begins with:
```python
if conn.in_transaction:
    conn.execute('ROLLBACK')
```
This rolls back any **in-progress** transaction on the connection before starting a new one. Because `DB_CONN` is a single shared connection (stored in `app.config`), if two concurrent requests (even under Passenger's CGI model, two overlapping processes sharing the same file could hit WAL contention) are in different stages of the query pipeline, one could inadvertently roll back the other's uncommitted `init_document_tables` work or any other transaction started elsewhere. The `ROLLBACK` before `BEGIN` should not be necessary if all callers always commit or roll back correctly — its presence indicates the code is defensive about leaked transactions, but it is a blunt instrument that can silently discard work.

**Fix:** Remove the preemptive ROLLBACK guard and instead ensure all callers always terminate transactions cleanly. If defensive rollback is truly needed, log it as a warning:
```python
if conn.in_transaction:
    import logging
    logging.getLogger(__name__).warning(
        "_save_session: rolling back leaked transaction before BEGIN"
    )
    conn.execute('ROLLBACK')
```

---

### WR-03: `_parse_chips` regex fails on LLM responses that include nested braces in text

**File:** `app/services/query.py:79`
**Issue:** The regex `r'\{[^{}]*"chips"\s*:\s*\[[^\]]*\][^{}]*\}'` uses `[^{}]*` which does not allow any `{` or `}` inside the JSON object. A real LLM response like:
```
The function does {something}.\n{"chips": ["Q1?", "Q2?", "Q3?"]}
```
will fail to match because the regex requires no braces before `"chips"`, and the outer `[^{}]*` will be blocked by `{something}`. The regex finds the _last_ `{...}` that contains `"chips"`, but because `[^{}]*` disallows nested braces, a response with any `{...}` in the answer text before the chip JSON will cause the regex to miss the chip block and return `(raw, [])`.

Wait — actually the regex uses `re.search` which finds the first match in the string, not the last. The docstring says "Find last JSON object" but `re.search` returns the first match. If the LLM puts `{something}` in the answer text before the chips JSON, `re.search` will match `{something}` (which does not contain `"chips"`) — no wait, the regex requires `"chips"` in the pattern, so `{something}` will not match. However, a brace-containing string like `{"result": "good"}` in the answer body before the chip block would match the pattern if it happened to contain the word `chips` anywhere — the issue is the opposite direction. The real bug is that `re.search` finds the **first** match, not the last, contradicting the docstring. If the LLM includes an example JSON with a `chips` key in the answer body, `re.search` will grab that instead of the trailing chip block.

**Fix:** Use `re.findall` and take the last match, or use a right-anchored approach:
```python
matches = list(re.finditer(r'\{[^{}]*"chips"\s*:\s*\[[^\]]*\][^{}]*\}', raw, re.DOTALL))
if not matches:
    return raw, []
match = matches[-1]  # take the last occurrence, not the first
```

---

### WR-04: No input length cap on `message` — unbounded LLM prompt injection risk

**File:** `app/routes/chat.py:52-56`
**Issue:** The `message` field is validated only for being non-empty. There is no maximum length check. A caller can send a 100 KB message, which:
1. Is embedded (expensive API call for a huge input).
2. Is appended to the LLM prompt directly (line 253: `llm_messages.append({'role': 'user', 'content': message})`), potentially crowding out the system prompt and context — a form of prompt injection where the user overrides instructions by flooding the context window.
3. Can also cause the `sessions` table row to grow unboundedly if the user repeats this.

**Fix:** Add a length cap in the route:
```python
MAX_MESSAGE_LEN = int(os.environ.get('MAX_MESSAGE_LEN', '2000'))
if len(message) > MAX_MESSAGE_LEN:
    resp = jsonify({'error': 'Message too long'})
    resp.headers.update(cors)
    return resp, 400
```

---

### WR-05: `widget_js()` route in `__init__.py` does not set `Cache-Control` header despite the docstring claiming it does

**File:** `app/__init__.py:30-43`
**Issue:** The docstring at line 37 states: "Cache-Control: public, max-age=300 (5-minute cache — reasonable for widget updates)", but the implementation at line 42 calls `send_from_directory(static_dir, 'widget.js', mimetype='application/javascript')` with no `max_age` or `cache_timeout` argument. Flask's `send_from_directory` defaults to no cache headers (or the Flask default, which in debug mode is no-cache). The Cache-Control header that the docstring documents is never actually set.

**Fix:**
```python
return send_from_directory(
    static_dir, 'widget.js',
    mimetype='application/javascript',
    max_age=300,
)
```

---

### WR-06: Chip click does not disable further chip clicks — duplicate sends possible

**File:** `app/static/widget.js:494-497`
**Issue:** When a chip button is clicked, `chipsEl.remove()` removes the chip container from the DOM and `sendMessage(q)` is called. `sendMessage` calls `setLoading(true)` which disables `input` and `sendBtn`, but it does NOT disable the chip buttons before calling `chipsEl.remove()`. Under rapid double-click (or a race between two fast clicks before the DOM update propagates), two `sendMessage` calls can fire from the same chip. The `state.loading` guard in `sendMessage` (line 526) catches this only if `state.loading` is already `true` at the time of the second call — but both clicks may fire synchronously before `setLoading(true)` executes.

**Fix:** Set a guard on the chip immediately:
```js
btn.addEventListener('click', function () {
  if (state.loading) return;   // guard against double-click race
  chipsEl.remove();
  sendMessage(q);
});
```

---

## Info

### IN-01: Duplicate test file — `test_parse_chips_red.py` is a strict subset of `test_chat_chips.py`

**File:** `tests/test_parse_chips_red.py`
**Issue:** All four tests in `test_parse_chips_red.py` are identical in assertion logic to four tests already in `test_chat_chips.py` (lines 84-117). The `_red` file was a TDD red-phase artifact that was never deleted after implementation. Running the test suite runs each of these assertions twice, adding noise to test output and obscuring which file a failure originates from.

**Fix:** Delete `tests/test_parse_chips_red.py`. All scenarios it covers are already exercised in `test_chat_chips.py`.

---

### IN-02: `_call_llm_with_retry` catches `requests.RequestException` which subsumes `requests.HTTPError` — redundant clause

**File:** `app/services/query.py:61`
**Issue:** The except tuple is `(requests.exceptions.Timeout, requests.HTTPError, requests.RequestException)`. `requests.HTTPError` is a subclass of `requests.RequestException`, so the `requests.HTTPError` entry is redundant — it will always be caught by `requests.RequestException` first (Python checks left-to-right in a tuple, but regardless the last clause covers all). This is dead code in the exception handler.

**Fix:**
```python
except (requests.exceptions.Timeout, requests.RequestException):
    continue
```

---

### IN-03: `widget.js` — `openPanel` / `closePanel` rebuild FAB `innerHTML` with SVG strings on every toggle

**File:** `app/static/widget.js:411, 420`
**Issue:** Each call to `openPanel()` and `closePanel()` replaces `fab.innerHTML` with a raw SVG string. While the content is hardcoded (no injection risk here), this is inconsistent with the rest of the widget which avoids `innerHTML`. It also re-parses the SVG on every toggle. Using `innerHTML` for the FAB icon while using `textContent` / `createElement` elsewhere is an inconsistent pattern that makes future maintainers more likely to copy the `innerHTML` pattern into unsafe contexts.

**Fix:** Pre-render the two SVG states as child elements and toggle visibility/display between them, or clone pre-parsed template nodes.

---

_Reviewed: 2026-05-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
