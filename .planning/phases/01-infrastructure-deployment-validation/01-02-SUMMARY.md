---
phase: 01-infrastructure-deployment-validation
plan: 02
status: complete
completed: 2026-05-09
---

# Plan 01-02 Summary — SiteGround Deployment

## Result: PASS

Live endpoint confirmed:
```json
{
  "sqlite_vec_mode": "native",
  "sqlite_vec_version": "v0.1.9",
  "status": "ok",
  "storage_path": "/home/customer/dochat/storage",
  "storage_writable": true
}
```

## What was deployed

- App code cloned to `~/dochat/` on `giowm1251.siteground.biz`
- Virtualenv at `~/dochat/venv/` (Python 3.14.3)
- Dependencies installed from `requirements.txt`
- `.env` created with real secrets (not in git)
- `~/dochat/storage/` created and writable
- `app.cgi` symlinked into staging `public_html/`, executable
- `.htaccess` updated with surgical DocChat CGI block

## Deployment method

Passenger WSGI was not available on SiteGround shared hosting.
Deployed via Apache CGI using `wsgiref.handlers.CGIHandler`.
Entry point: `app.cgi` (symlinked from `~/dochat/app.cgi` into `public_html/`).
Routes: only DocChat-specific paths (`/health`, future `/api/*`) routed to CGI.
Existing PHP staging site unaffected.

## Environment facts (resolved open questions)

| Question | Answer |
|----------|--------|
| Python version on SiteGround | 3.14.3 |
| SQLite version | confirmed compatible with sqlite-vec 0.1.9 |
| sqlite_vec mode | **native** (enable_load_extension available) |
| HOME path | `/home/customer/` (symlink — use this in shebangs) |
| Passenger available | No — CGI used instead |
| mod_wsgi available | No |

## Phase 1 verification checklist

- [x] `curl https://staging.social-automate.com/health` returns HTTP 200
- [x] Response is valid JSON
- [x] `storage_writable` is `true`
- [x] `sqlite_vec_mode` is `native`
- [x] No 500 errors
- [x] Existing staging PHP site unaffected
- [x] 17 pytest tests passing locally
