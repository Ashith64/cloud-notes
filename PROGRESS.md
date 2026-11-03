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

- **Stage 3: Attachments, Export, Status, and Demo Data**
  - **Attachments API** (`backend/app/routes/attachments.py`):
    - `POST /api/attachments` — accepts multipart upload (`file`, `note_id`), checks ownership of note, strictly validates file type via initial magic bytes (supporting png, jpg, gif, webp, pdf up to 10 MB limit), stores at `users/{user_id}/attachments/{id}.{ext}`, returns `{id, ref, url}` with stable reference `attachments/{id}.{ext}` and URL `/api/attachments/{id}`.
    - `GET /api/attachments/<id>` — checks cookie and enforces strict user ownership (404 on other user's attachment); in S3 mode answers 302 to a 300-second presigned URL, in local mode streams binary data with correct MIME type and `Content-Disposition`.
    - Permanent note deletion (`DELETE /api/notes/<id>/permanent`) cascade-deletes all associated attachment records and objects in storage.
  - **Export API** (`backend/app/routes/export_routes.py`):
    - `GET /api/notes/<id>/export` — downloads single note as safe `<safe-title>-<shortid>.md` with front matter and body.
    - `GET /api/export` — streams ZIP of all user notes into `notes/` directory and attachments into `attachments/` directory; rewrites in-body image/pdf links from `attachments/<file>` to `../attachments/<file>` so offline viewing works seamlessly.
    - Enforces 200 MB maximum archive size cap returning HTTP 413 if exceeded.
  - **System Status API** (`backend/app/routes/status.py`):
    - `GET /api/status` — public endpoint reporting `instance_id` and `availability_zone` via IMDSv2 (1-second timeout, fallback to `"local"`), `running_servers` and `average_cpu` via Auto Scaling and CloudWatch (null if unconfigured), `db_ok` via `SELECT 1`, `storage_ok` via storage health check, `last_backup` from RDS `LatestRestorableTime` (null if unconfigured), `version`, and `uptime_seconds`.
    - Graceful degradation: all checks fail cleanly to null or false without crashing. Cached in-memory for 10 seconds.
  - **Demo Seeding Script & Integration** (`backend/app/scripts/seed_demo.py`):
    - Created idempotent seeder creating 3 notebooks (`College`, `Projects`, `Personal`) and 12 realistic sample notes for a cloud computing student.
    - Varied formatting: markdown tables, code blocks, checklists, quotes, and links. Exactly 1 pinned note, 2 favorites, and multiple tags.
    - Integrated with `POST /api/auth/demo` so demo login immediately yields a fully populated workspace.
  - **Tests**:
    - `test_attachments.py` — 15 tests.
    - `test_export.py` — 11 tests.
    - `test_status.py` — 14 tests.
    - `test_demo.py` — 14 tests.
    - Total test suite: 137 tests passing in ~31s.

- **Stage 4: Frontend Foundation and Authentication**
  - **Dependencies & Setup**: Configured Vite with React, `@tailwindcss/vite` (Tailwind CSS v4), path aliases (`@/*` -> `./src/*`), and `/api` reverse proxy to backend at `http://127.0.0.1:8000`. Self-hosted `@fontsource-variable/inter` for UI typography.
  - **Design System & Tokens** (`frontend/src/index.css`): Implemented exact C2 design tokens as CSS variables for light and dark modes.
  - **Screens Implemented**:
    - Login & Sign up (`frontend/src/pages/LoginPage.tsx`): C3.1 split layout.
    - Workspace Shell (`frontend/src/pages/WorkspacePage.tsx`, `frontend/src/pages/WorkspaceHome.tsx`): 3-pane shell.
    - System Status (`frontend/src/pages/StatusPage.tsx`): C3.5 public status dashboard.
    - Settings (`frontend/src/pages/SettingsPage.tsx`): Account details, visual theme picker, password change, export.

- **Stage 5A: Notes List, Sidebar, and Notion-Style Visual Editor**
  - Visual editor with `@milkdown/crepe` (slash menu, toolbar, block handles, syntax highlighting, tables).
  - Autosave with 800ms debounce, concurrent save guards, and retry backoff.
  - Sidebar navigation with live counts and context menus.

- **Stage 5B: Attachments, Trash, Search, Settings, Shortcuts & Phone Layout**
  - Image drag/drop and PDF attachment upload chips.
  - Trashed notes banner with 30-day notice and 6-second undo toast.
  - Command palette (`Ctrl/Cmd+K`) with live search.
  - Responsive mobile 1-pane layout with floating `+` button and back navigation.

- **Stage 6: UI Polish, Responsive Refinements & Accessibility (Partially Completed)**
  - UI enhancements and accessibility focus rings applied across workspace components.
  - Responsive drawer navigation and theme provider adjustments.
  - Screenshot verification captures recorded into `docs/screenshots/stage6-*`.
  - *Status: Partially completed with full end-to-end verification unresolved per project record instructions.*

- **Stage 7: Containerisation & Production Configuration**
  - **Production Secrets Resolution** (`backend/app/config.py`):
    - Extended configuration to detect `DB_SECRET_ARN`, `DB_HOST`, `DB_NAME`, and `APP_SECRET_ARN`.
    - Integrates with AWS Secrets Manager via `boto3` default credential chain.
    - Caches secret strings in-memory (`_SECRETS_CACHE`) to avoid redundant AWS API calls.
    - Dynamically generates `DATABASE_URL` for MySQL with `utf8mb4` charset.
    - Preserves existing environment variable defaults when ARN variables are unset.
    - Added `COOKIE_SECURE` configuration flag (default `false`) and updated `auth.py` cookie handler.
  - **Structured JSON Logging** (`backend/app/__init__.py`):
    - Configured stdout logging using custom `_JsonFormatter`.
    - Emits one JSON record per line containing `time`, `level`, `message`, `request_id`, `route`, `status`, and `duration_ms`.
    - Request lifecycle hooks extract or generate `X-Request-Id` and measure request duration via `time.perf_counter()`.
  - **Single-Container SPA Serving & Fallback** (`backend/app/__init__.py`):
    - Catch-all route serves compiled frontend assets from `FRONTEND_DIST_DIR` (`frontend/dist`).
    - Falls back to `index.html` on client routes (`/login`, `/app`, `/settings`, `/status`) so browser reloads work without 404s.
    - Preserves JSON 404 responses for `/api/*` endpoints.
  - **Multi-Stage Dockerfile** (`Dockerfile`):
    - Stage 1: `node:20-alpine` runs `npm ci` and `npm run build`.
    - Stage 2: `python:3.12-slim` installs dependencies from `requirements.txt`, copies backend source and compiled frontend dist, configures non-root user `appuser`, exposes port 8000, and adds `HEALTHCHECK` probing `GET /api/health`.
  - **Container Entrypoint Script** (`docker-entrypoint.sh`):
    - Written with Unix LF line endings.
    - Polls `flask init-db` with exponential backoff / retry up to 60 seconds until the database is ready.
    - Launches Gunicorn with app factory: `gunicorn "app:create_app()" --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 60`.
  - **Docker Compose Setup** (`docker-compose.yml`):
    - Defines `mysql:8` service with healthcheck and persistent named volume `mysql_data`, exposing port 3306.
    - Defines `app` service building `Dockerfile` with persistent named volume `app_storage` mounted to `/app/local_data`.
    - Service dependency ensures `app` starts only after `mysql` is healthy.
  - **Backend Test Suite Expansion** (`backend/tests/`):
    - Updated `conftest.py` to support `TEST_DATABASE_URL` environment variable for MySQL test runs.
    - Updated `test_auth.py` to decouple `test_me_without_cookie` from hardcoded SQLite assumptions.
    - Added `test_stage7.py` covering Secrets Manager resolution, JSON logging, SPA fallback, and cookie security flags.
    - All 157 backend tests passing on SQLite.

## How to Run

### Local Development

```sh
# Backend (port 8000)
cd backend
.venv\Scripts\activate
flask init-db
python wsgi.py

# Frontend dev server (port 5173)
cd frontend
npm run dev

# Or build frontend production bundle
cd frontend
npm run build

# Run all 157 backend tests
cd backend
.venv\Scripts\pytest.exe tests/ -v
```

### Running with Docker

```sh
# Start MySQL 8 and Cloud Notes application
docker compose up --build

# Access application at http://localhost:8000
# Health check at http://localhost:8000/api/health
# Status dashboard at http://localhost:8000/status
```

## Next

- Stage 8: Infrastructure as Code & AWS Deployment (AWS CloudFormation template, ALB, Auto Scaling group, private RDS MySQL, S3 storage, CloudWatch alarms).

## Decisions

- Structured JSON logging uses `json.dumps` with UTC timestamps and standard field names (`time`, `level`, `message`, `request_id`, `route`, `status`, `duration_ms`).
- In-memory cache `_SECRETS_CACHE` prevents repeated AWS Secrets Manager calls across multiple worker threads or configuration reads.
- `COOKIE_SECURE` is explicitly configurable via environment variable (default `false`) so Docker Compose local testing over HTTP functions properly, while production CloudFormation sets `COOKIE_SECURE=true`.
- SPA fallback serves `index.html` for non-API routes when `FRONTEND_DIST_DIR` is present, while strictly returning JSON 404s for any `/api/*` path.
- `docker-entrypoint.sh` uses POSIX shell with retry loop (30 attempts x 2s) for database initialization to handle MySQL startup latency.

## Known Issues & Pending Verifications

- **Docker & MySQL Verification**: Docker CLI is not installed / accessible in the local host environment, and the host's existing Windows MySQL service requires administrator credentials. Live container startup (`docker compose up --build`) and direct MySQL test execution remain pending an active Docker runtime.
- `local_data/` is created on first storage write, not on startup (matches lazy initialization).
