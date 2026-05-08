# Walking Skeleton — DocChat RAG Pipeline

**Phase:** 1
**Generated:** 2026-05-08

---

## Capability Proven End-to-End

A developer can SSH into SiteGround, deploy the scaffold, and GET `https://staging.social-automate.com/health` — receiving a JSON response confirming Flask boots under Passenger WSGI, sqlite-vec initializes (native or fallback), and `~/dochat/storage/` is writable.

---

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Web framework | Flask 3.1.3 | Passenger is WSGI — FastAPI (ASGI) is disqualified on SiteGround shared hosting |
| WSGI entry point | passenger_wsgi.py | Phusion Passenger requires a file named `passenger_wsgi.py` exporting `application` |
| App structure | Flask application factory (`create_app()`) | Enables testing without a running server; clean blueprint registration |
| Vector store | sqlite-vec 0.1.9 | Single SQLite file; ~0 RAM overhead; no HNSW index RAM spike (ChromaDB disqualified) |
| Embedding source | OpenRouter API (Phase 2+) | No PyTorch/sentence-transformers — OOM-kill risk on shared hosting |
| LLM | OpenRouter (`google/gemma-3-27b-it:free`, fallback `qwen/qwen3-next-80b-a3b-instruct:free`) | Free tier; no GPU required on shared hosting |
| Secret management | python-dotenv, `.env` file | Passenger does not auto-load `.env`; `load_dotenv()` called first in `passenger_wsgi.py` |
| Data storage root | `~/dochat/storage/` (outside `public_html/`) | Files under `public_html/` are web-accessible; DB and uploads must not be |
| SQLite WAL mode | `PRAGMA journal_mode=WAL` (persistent) + `PRAGMA busy_timeout=10000` (per-connection) | Prevents write contention with single Passenger worker |
| sqlite-vec fallback | Auto-detect: native → python-fallback | SiteGround may not have `enable_load_extension` compiled in; coded fallback required |
| Deploy workflow | SSH + `git pull` from GitHub | Standard for shared hosting; no CI/CD required for v1 |
| Restart signal | `touch tmp/restart.txt` (primary) + `touch passenger_wsgi.py` (secondary) | Both signal Passenger to reload the process |
| Python version | 3.11 (preferred) or highest available in cPanel Python Selector | 3.11 is stable LTS; 3.13 acceptable if 3.11 unavailable |
| Hosting target | SiteGround shared hosting (`staging.social-automate.com`) | User's existing hosting; VPS is last-resort fallback only |

---

## Stack Touched in Phase 1

- [x] Project scaffold (`passenger_wsgi.py`, `app/__init__.py`, `app/db.py`, `app/routes/health.py`)
- [x] Routing (one real route: `GET /health` — no auth required)
- [x] Database (`sqlite-vec` init, WAL mode, 10s busy_timeout, native/fallback detection)
- [x] Secret loading (`python-dotenv`, `.env` file, `.env.example` committed)
- [x] Storage path (`~/dochat/storage/` — confirmed outside `public_html/`)
- [x] Test suite (`pytest`, `tests/test_health.py`, `tests/test_db.py`, `tests/test_config.py`)
- [x] Deployment (SiteGround cPanel Python Selector, Passenger WSGI, SSH + git pull)

---

## Directory Layout (Established in Phase 1)

```
~/dochat/                           # cPanel Application root
├── passenger_wsgi.py               # Passenger WSGI entry point
├── app/
│   ├── __init__.py                 # Flask factory (create_app)
│   ├── db.py                       # sqlite-vec init, WAL, fallback
│   └── routes/
│       ├── __init__.py
│       └── health.py               # GET /health blueprint
├── requirements.txt                # Pinned: flask, sqlite-vec, python-dotenv
├── .env.example                    # Committed template (no real secrets)
├── .env                            # NOT committed; real secrets on server
├── .gitignore
├── pytest.ini
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Flask test client fixture
│   ├── test_health.py
│   ├── test_db.py
│   └── test_config.py
└── tmp/
    └── .gitkeep                    # Ensures tmp/ exists for restart.txt

~/dochat/storage/                   # Outside web root — NEVER under public_html/
├── dochat.db                       # sqlite-vec database (WAL mode)
└── uploads/                        # Phase 2 — document uploads
```

---

## Config Keys (app.config — set by create_app())

| Key | Type | Source |
|-----|------|--------|
| `SECRET_KEY` | str | `os.environ['SECRET_KEY']` |
| `STORAGE_PATH` | str | `os.path.expanduser('~/dochat/storage')` |
| `DB_CONN` | sqlite3.Connection | set by `init_db()` |
| `SQLITE_VEC_MODE` | str | `'native'` or `'python-fallback'` |
| `DB_PATH` | str | absolute path to `dochat.db` |

---

## .env Keys (minimum for Phase 1)

| Key | Purpose | When Needed |
|-----|---------|-------------|
| `SECRET_KEY` | Flask session signing | Phase 1 (required at startup) |
| `OPENROUTER_API_KEY` | LLM + embedding API calls | Phase 2+ |
| `ADMIN_PASSWORD` | Admin UI auth | Phase 4 |

---

## Out of Scope (Deferred to Later Slices)

- Document upload and parsing (Phase 2)
- Embedding generation (Phase 2)
- Vector search and RAG pipeline (Phase 3)
- Admin UI with auth (Phase 4)
- Chat widget (Phase 5)
- Lead capture (Phase 6)
- Widget embedding on all staging pages + standalone `/dochat/` page (Phase 5)
- Streaming responses (v2 scope)
- Production promotion to `social-automate.com` (after Phase 6)

---

## Open Questions (Captured for Phase 2)

1. Does SiteGround's Python have `enable_load_extension` compiled in? (Verified at Phase 1 deploy time — result recorded in 01-02-SUMMARY.md)
2. Is `sqlite_vec_mode: python-fallback`? If so, Phase 2 must verify vec0 virtual table creation works in fallback mode before building the ingestion pipeline.
3. What is the SQLite version on SiteGround? If < 3.41, `pysqlite3-binary` may need to be added to requirements.txt.

---

## Subsequent Slice Plan

| Phase | Goal | New Capabilities |
|-------|------|-----------------|
| Phase 2 | Document Ingestion Pipeline | Admin uploads PDF/DOCX/TXT/MD/URL → chunks indexed in sqlite-vec |
| Phase 3 | Query Pipeline & RAG Logic | Visitor question → vector search → LLM answer with session history |
| Phase 4 | Admin UI | Password-protected web interface for document management and lead review |
| Phase 5 | Chat Widget | Embeddable vanilla JS widget with Shadow DOM, theming, single `<script>` tag |
| Phase 6 | Lead Capture | Similarity fallback → inline lead form → email notification + SQLite storage |

---

*Walking Skeleton generated: 2026-05-08*
*Phase 1 success criterion: `https://staging.social-automate.com/health` returns JSON with `storage_writable: true`*
