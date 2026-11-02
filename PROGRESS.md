# Progress

## Done

- **Stage 0: Project Scaffold**
  - Created directory layout:
    - `backend/app/` (`__init__.py`, `config.py`, `extensions.py`, `models.py`, `storage/`, `routes/`)
    - `backend/tests/` (`__init__.py`, `test_health.py`)
    - `backend/wsgi.py`
    - `backend/requirements.txt`
    - `frontend/` (scaffolded with Vite React TypeScript template)
    - `infra/`
    - `loadtest/`
    - `docs/screenshots/`
  - Created Python virtual environment in `backend/.venv` (Python 3.12).
  - Installed all backend dependencies from `AGENTS.md` (Flask 3, SQLAlchemy 2, PyMySQL, PyJWT, bcrypt, boto3, python-frontmatter, gunicorn, pytest) and pinned exact versions into `backend/requirements.txt`.
  - Created `.gitignore` ignoring dependencies, virtualenvs, local databases, build outputs, environment files, and local data directory.
  - Created `.env.example` containing all required configuration variables with default values.
  - Built Flask application factory in `backend/app/__init__.py` loading environment configuration and exposing `GET /api/health` returning `{"status": "ok", "version": "0.1.0"}` without database access.
  - Wrote pytest test in `backend/tests/test_health.py` and verified it passes.
  - Verified Flask server starts and `/api/health` returns HTTP 200 with JSON payload.
  - Created root `README.md` and initialized `PROGRESS.md`.

- **Stage 1: Backend Foundation & Authentication**
  - **Models** (`backend/app/models.py`): Full SQLAlchemy 2 declarative models for all D4 tables:
    - `users` — id, email (unique), name, password_hash, failed_logins, locked_until, created_at
    - `notebooks` — id, user_id, name, created_at; unique constraint (user_id, name)
    - `notes` — UUID string PK, user_id, notebook_id (nullable), title, snippet, search_text, storage_key, is_pinned, is_favorite, is_archived, deleted_at, version, created_at, updated_at; indexes on (user_id, updated_at), (user_id, deleted_at), title
    - `tags` + `note_tags` — many-to-many; unique constraint (user_id, name) on tags
    - `attachments` — UUID string PK
    - `note_history` — Could-tier table, created but feature-gated
  - **Database init** (`backend/app/db.py`): `init_db()` calls `create_all`; wraps in MySQL `GET_LOCK` advisory lock when on MySQL so multiple servers starting simultaneously don't collide. `flask init-db` CLI command available.
  - **Extensions** (`backend/app/extensions.py`): `init_extensions()` creates SQLAlchemy engine and scoped session, stores both on `app._db_engine` / `app._db_session` (instance-local) to avoid test cross-contamination.
  - **Storage abstraction** (`backend/app/storage/`):
    - `base.py` — abstract interface: `put_text`, `get_text`, `put_bytes`, `get_bytes`, `delete`, `exists`, `presigned_url_or_none`, `health_check`
    - `local.py` — writes under `LOCAL_STORAGE_PATH`; path-traversal check; `presigned_url_or_none` returns `None`
    - `s3.py` — boto3 default credential chain (instance role); `ServerSideEncryption=AES256` on every put; presigned GET URLs expire in 300 s; no access keys in code
    - `factory.py` + `__init__.py` — `get_storage()` selects backend from `STORAGE_BACKEND` env var
  - **Auth routes** (`backend/app/routes/auth.py`): all D5 / D3.8 auth endpoints:
    - `POST /api/auth/register` — email regex validation, min 8-char password, unique email check, bcrypt hash
    - `POST /api/auth/login` — bcrypt verify, generic error message, lockout after 5 failures for 10 minutes (counters in DB)
    - `POST /api/auth/logout` — clears cookie
    - `GET /api/auth/me` — requires login cookie
    - `POST /api/auth/change-password` — requires old password, min 8-char new password
    - `POST /api/auth/demo` — creates or reuses `demo@cloudnotes.app`
    - `login_required` decorator — validates JWT cookie, sets `g.current_user`
    - `csrf_required` decorator — rejects POST/PATCH/DELETE without `X-Requested-With: cloudnotes`
    - JWT stored in httpOnly, SameSite=Lax cookie (Secure only in non-debug/non-test)
    - `sub` claim stored as string (PyJWT 2.x requirement)
  - **Error handlers** (`backend/app/__init__.py`): consistent JSON `{"error":{"code":"…","message":"…"}}` format for 400/401/403/404/405/409/422/429/500
  - **Tests**: 39 tests all passing (9.86 s):
    - `test_auth.py` — 19 tests covering register, duplicate email, invalid email, short password, login, wrong password, lockout (5 failures), me with/without cookie, change password, CSRF header check, demo (idempotent)
    - `test_storage.py` — 19 tests: local backend (text, bytes, exists, delete, missing key raises, presigned=None, health, traversal rejection); S3 backend fully mocked (put/get text, put/get bytes, exists true/false, delete, presigned URL, health ok/fail)
    - `test_health.py` — 1 existing test

- **Stage 2: Notes, Notebooks, and Tags API**
  - **Notes API** (`backend/app/routes/notes.py`):
    - `POST /api/notes` — creates note id (UUID4), writes front matter Markdown to storage `users/{user_id}/notes/{note_id}.md`, then writes DB row in single transaction.
    - `GET /api/notes` — lists summaries (no body) with filters: `view` (`all`, `favorites`, `archive`, `trash`), `notebook_id`, `tag`, `q` (case-insensitive search on title and search_text with `%`/`_` escaping), sorting (`updated`, `created`, `title`), `limit`, and `offset`. Pinned notes float to the top in the `all` view.
    - `GET /api/notes/<id>` — returns full note including `content` extracted from storage file.
    - `PATCH /api/notes/<id>` — updates title, content, notebook_id, tags, is_pinned, is_favorite, is_archived. Supports optimistic concurrency with `base_version` (returns 409 conflict if mismatched). Increments version and performs two-place save (file first, then DB).
    - `DELETE /api/notes/<id>` — soft delete (sets `deleted_at`).
    - `POST /api/notes/<id>/restore` — restores soft-deleted note (clears `deleted_at`).
    - `DELETE /api/notes/<id>/permanent` — permanently deletes DB row, tag links, attachments, and the storage file.
    - `POST /api/trash/empty` — empties trash for current user, deleting files and DB records.
    - Lazy trash purge (D3.7): automatically purges notes trashed over `TRASH_PURGE_DAYS` (default 30) when trash is viewed or emptied.
  - **Notebooks API** (`backend/app/routes/notebooks.py`):
    - `GET /api/notebooks` — lists notebooks scoped to current user.
    - `POST /api/notebooks` — creates notebook with unique name per user.
    - `PATCH /api/notebooks/<id>` — renames notebook with validation and collision checks.
    - `DELETE /api/notebooks/<id>` — deletes notebook while keeping notes unfiled (`notebook_id` set to `null`).
  - **Tags API** (`backend/app/routes/tags.py`):
    - `GET /api/tags` — returns list of tags for current user with accurate note counts.
    - Tag rules: trimmed, lowercased, at most 30 characters, at most 10 per note, auto-deduplicated.
  - **Markdown Utilities** (`backend/app/utils.py`):
    - `strip_markdown`: strips code blocks, inline code, links, images, headings, quotes, lists, bold/italic, tables, HTML tags.
    - `make_snippet`: generates snippet from first 200 chars of plain text body.
  - **CLI Command** (`backend/app/__init__.py`):
    - `flask reindex` — reads all stored Markdown files and rebuilds the notes table's title, snippet, search_text, and tag links.
  - **Tests** (`backend/tests/test_notes.py`):
    - 39 comprehensive tests covering: CRUD for notes and notebooks, user isolation (404 on reading, updating, deleting another user's note/notebook), search with special character escaping, filter views (`all`, `favorites`, `archive`, `trash`), tag constraints, pin ordering, trash and restore, lazy purge with back-dated notes, 409 version conflict, failure injection (DB commit failure leaves no partial state, retry succeeds consistently), and `flask reindex` CLI command.
    - Total test suite: 78 tests passing across all suites in 17.36s.

## How to Run

```sh
# From backend/
cp ../.env.example ../.env   # edit if needed
flask init-db
flask reindex                # rebuilds DB index from stored markdown files
python wsgi.py               # dev server at http://localhost:8000
pytest tests/ -v             # run all 78 tests
```

## Next

- Stage 3: Rich Text Editor & Frontend Workspace — Vite/React integration, `@milkdown/crepe` editor, three-pane layout, auto-save, sidebar notebook/tag navigation.

## Decisions

- Set default port to 8000 in `backend/wsgi.py` aligned with the single container specification in `docs/SPEC.md`.
- Stored exact pinned dependencies in `backend/requirements.txt` using UTF-8 encoding.
- Configured Flask app factory to accept optional configuration overrides for testing while defaulting to `Config` object.
- JWT `sub` claim is stored as a string (not int) to satisfy PyJWT 2.x strict type checking; converted back to int when loading user from DB.
- `Secure` cookie flag is disabled when `TESTING=True` so Werkzeug test client (HTTP only) correctly sends the cookie back in subsequent requests.
- `init_extensions()` stores engine and session both on the `app` instance (`app._db_engine`, `app._db_session`) and on module-level globals. Routes use `current_app._db_session()` so multiple test app instances don't clobber each other's sessions.
- Added `TRASH_PURGE_DAYS` to `Config` (default 30 days) to configure lazy purge period.
- Front-matter metadata in `.md` files includes both `notebook` and `notebook name` keys for maximum interoperability.
- Tag sanitation occurs both on API payload receipt and during front-matter serialization to prevent duplicate tag errors during index rebuilding.
- Two-place save guarantees: UUID is generated before disk write; storage write occurs first; database transaction wraps row updates and tag synchronization; database exceptions rollback and return HTTP 500.

## Known Issues

- `local_data/` is created on first storage write, not on startup (acceptable — matches lazy init).
