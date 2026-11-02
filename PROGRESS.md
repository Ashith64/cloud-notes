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
    - Created idempotent seeder creating 3 notebooks (`College`, `Projects`, `Personal`) and 12 realistic sample notes for a cloud computing student: OSI model, AWS EC2 basics, Docker vs virtual machines, How load balancing works, IaaS PaaS SaaS, S3 storage classes, IAM least privilege, CAP theorem, Semester 5 exam plan, Project ideas, Weekly timetable, Reading list.
    - Varied formatting: markdown tables, code blocks, checklists, quotes, and links. Exactly 1 pinned note, 2 favorites, and multiple tags.
    - Integrated with `POST /api/auth/demo` so demo login immediately yields a fully populated workspace.
  - **Tests**:
    - `test_attachments.py` — 15 tests covering all formats, magic byte verification, type spoofing rejections, oversized payload rejections, note ownership isolation, unauthenticated access, and cascade deletion.
    - `test_export.py` — 11 tests covering single note download, safe filenames, cross-user isolation, full zip archive structure, attachment link rewriting, attachment inclusion in zip, and 200 MB limit guard.
    - `test_status.py` — 14 tests covering public access, all field presence, unconfigured null fallbacks, local fallbacks, mocked ASG / CloudWatch and RDS backup data, and in-memory 10-second cache.
    - `test_demo.py` — 14 tests covering demo login, exact 3 notebooks and 12 notes creation, idempotency on repeated invocations (2x and 3x), pin and favorite constraints, notebook categorisation, and tag listings.
    - Total test suite: 137 tests passing in ~31s.

## How to Run

```sh
# From backend/
cp ../.env.example ../.env   # edit if needed
flask init-db
flask reindex                # rebuilds DB index from stored markdown files
python wsgi.py               # dev server at http://localhost:8000
pytest tests/ -v             # run all 137 tests
```

- **Stage 4: Frontend Foundation and Authentication**
  - **Dependencies & Setup** (`frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.app.json`):
    - Configured Vite with React, `@tailwindcss/vite` (Tailwind CSS v4), path aliases (`@/*` -> `./src/*`), and `/api` reverse proxy to backend at `http://127.0.0.1:8000`.
    - Self-hosted `@fontsource-variable/inter` for UI typography with zero external CDN dependencies.
    - Added UI libraries: `@tanstack/react-query`, `zustand`, `react-router-dom`, `lucide-react`, `sonner`, `clsx`, `tailwind-merge`, `class-variance-authority`, `cmdk`.
  - **Design System & Tokens** (`frontend/src/index.css`):
    - Implemented exact C2 design tokens as CSS variables for light and dark modes: background (`#FAFAF9` / `#0F0F11`), surface (`#FFFFFF` / `#17171A`), sidebar (`#F5F5F4` / `#131315`), border (`#E7E5E4` / `#27272A`), text (`#1C1917` / `#F4F4F5`), muted text (`#78716C` / `#A1A1AA`), accent (`#4F46E5` / `#818CF8`), accent soft (`#EEF2FF` / `#1E1B4B`), danger/success (`#DC2626`/`#16A34A` and `#F87171`/`#4ADE80`).
    - Card radius 12px, inputs/buttons radius 8px, card shadow and hover elevations, 150ms ease-out transitions.
  - **Theme Provider** (`frontend/src/providers/ThemeProvider.tsx`, `frontend/index.html`):
    - Supports System, Light, and Dark modes, persisted in `localStorage` under `cloudnotes_theme`.
    - Synchronized with OS `prefers-color-scheme` media query changes.
    - Inline anti-flash script in `index.html` prevents theme flashing on initial page load.
  - **shadcn/ui Components** (`frontend/src/components/ui/`):
    - Implemented all 16 requested components: `button`, `input`, `label`, `dialog`, `dropdown-menu`, `context-menu`, `command`, `sonner`, `skeleton`, `tooltip`, `avatar`, `sheet`, `separator`, `scroll-area`, `badge`, `switch`.
  - **API Client & Query Setup** (`frontend/src/lib/api.ts`, `frontend/src/lib/queryClient.ts`):
    - Typed `ApiError` class capturing status, spec code, and message.
    - Automatically sends credentials (cookies) and required `X-Requested-With: cloudnotes` header on every request.
    - TanStack Query client configured with 30s stale time and intelligent retry rules (no retries for 401, 403, 404).
  - **Routing & Auth Guards** (`frontend/src/components/AuthGuard.tsx`, `frontend/src/main.tsx`):
    - Routes: `/login`, `/app`, `/settings`, `/status`, and wildcard 404.
    - `AuthProvider` validates session against `GET /api/auth/me` with loading skeleton state.
    - `RequireAuth` redirects unauthenticated users to `/login`.
    - `RequireGuest` redirects authenticated users from `/login` to `/app`.
  - **Screens Implemented**:
    - **Login & Sign up** (`frontend/src/pages/LoginPage.tsx`): C3.1 split layout with soft indigo brand gradient panel, tagline, 3 key benefits; toggleable password visibility; inline friendly errors; loading button state; "Try demo account" one-click button; mobile layout showing form only.
    - **Workspace Shell** (`frontend/src/pages/WorkspacePage.tsx`, `frontend/src/pages/WorkspaceHome.tsx`): C3.2 responsive 3-pane shell with 248px sidebar, 340px note list, and editor space. Below 1024px, sidebar collapses into a slide-in sheet drawer. Below 640px, collapses into mobile 1-pane view. Top bar includes search bar with ⌘K badge, New note button, theme switcher, and avatar dropdown menu with logout.
    - **System Status** (`frontend/src/pages/StatusPage.tsx`): C3.5 public status dashboard auto-refreshing every 5 seconds with health dots (green/amber/red) and card grid for Instance ID, Availability Zone, Compute, DB status, Storage status, RDS Backup, and Application version.
    - **Settings** (`frontend/src/pages/SettingsPage.tsx`): Account details, visual theme picker (System, Light, Dark), password change placeholder, and export all zip button.
    - **Error Boundary & 404** (`frontend/src/components/ErrorBoundary.tsx`, `frontend/src/pages/NotFoundPage.tsx`): Styled error recovery screen and 404 not found page.
  - **Verification & Testing**:
    - Automated headless browser test suite (`frontend/verify-stage4.js` using Edge) verified all user journeys:
      - New user registration -> redirected to `/app` -> user profile confirmation.
      - User logout -> redirected to `/login`.
      - User login with credentials.
      - "Try demo account" instant login with seeded notes.
      - Theme switching between System, Light, and Dark modes.
      - Status page polling with live database and storage status.
      - Responsive layout adaptation at desktop (1280px), tablet (768px with drawer), and mobile (375px).
    - Captured 14 high-resolution verification screenshots into `docs/screenshots/`:
      - `login-desktop-light.png`, `login-desktop-dark.png`, `login-tablet.png`, `login-mobile.png`
      - `workspace-desktop-light.png`, `workspace-desktop-dark.png`, `workspace-tablet.png`, `workspace-drawer-open.png`, `workspace-mobile.png`
      - `status-desktop-light.png`, `status-desktop-dark.png`, `status-mobile.png`
      - `settings-desktop.png`, `not-found.png`
    - All 137 backend tests continue to pass (100%).
    - Frontend TypeScript check and Vite production build pass cleanly with zero errors.

- **Stage 5A: Notes List, Sidebar, and Notion-Style Visual Editor**
  - **Sidebar Navigation & Operations** (`frontend/src/pages/WorkspacePage.tsx`, `frontend/src/components/notebooks/NotebookDialogs.tsx`):
    - All Notes, Favorites, Archive, Trash with cheap live note counts from queries.
    - Notebooks list with note counts, "+ New notebook" dialog, and hover menu (`...`) with Rename and Delete operations (notes remain unfiled).
    - Tags list with exact note counts.
    - Filter selection reflected immediately in the URL query params (`?view=`, `?notebook_id=`, `?tag=`, `?q=`).
    - Top bar live search input (Ctrl/Cmd+K) and New note shortcut (Ctrl/Cmd+N).
  - **Note List** (`frontend/src/components/notes/NoteList.tsx`, `frontend/src/components/notes/NoteCard.tsx`):
    - Pinned and Recent sections (pinned notes float to top in All Notes view).
    - Cards show title, two-line snippet preview, tag chips, and relative time ("2h ago", "Just now", etc.).
    - Hover pin and trash action buttons.
    - Right-click context menu (Pin, Favorite, Move to notebook submenu, Archive, Export as Markdown, Delete).
    - Selected card styling (`accent-soft` background, accent border).
    - Keyboard Up and Down navigation with automatic scroll into view.
    - Trash view with "Empty Trash" confirmation dialog.
    - Skeleton loaders for notes list while loading.
    - Empty states for no notes, empty trash, no search results.
  - **New Note Creation**:
    - Creates an "Untitled" note on the server immediately via `POST /api/notes`, selects it, and focuses the title.
  - **Notion-Style Visual Editor with @milkdown/crepe** (`frontend/src/components/editor/MilkdownEditor.tsx`, `frontend/src/components/editor/NoteEditor.tsx`):
    - Crepe 7.23 integration supporting slash menu, floating toolbar, block handles, lists, task checklists, links, CodeMirror syntax-highlighted code blocks, tables, and image blocks.
    - Official theme CSS imported and overridden to match C2 tokens in both light and dark modes.
    - C2 typography: 17px body, 1.75 line-height, 720px centered max-width column, 32px bold borderless title.
    - Tag chips row with inline `+ tag` add field and tag removal.
    - Quiet footer displaying live save status ("Saving...", "Saved just now", "Not saved yet" with retry button) and `...` actions menu (Export, Move to notebook, Archive, Delete).
    - 120ms fade-in transition when switching notes.
  - **Autosave Controller** (`frontend/src/hooks/useNoteAutosave.ts`):
    - 800ms debounce after the last keystroke.
    - Strictly prevents concurrent saves of the same note (`inFlightRef`).
    - Coalesces edits made while a save is in flight and immediately triggers next save on response.
    - Retries transient and network errors with exponential back-off (1s, 2s, 4s, up to 10s).
    - Flushes save immediately when switching notes or unmounting.
    - Warns before closing the tab if edits are unsaved via `beforeunload`.
    - Optimistic updates in query cache so the note card title and snippet update instantly while typing.
    - 409 conflict handling updates server version and retries safely.
    - Stale response guard prevents overwriting newer selected notes.
  - **Browser Verification & Disk Inspection** (`frontend/verify-stage5a.js`):
    - Automated headless Edge verification test ran end-to-end:
      - Demo login -> Sidebar counts & navigation -> Light/Dark note list -> Right-click context menu -> Keyboard Up/Down navigation.
      - Created new note on server -> Edited title, added Markdown table, checklist, and syntax-highlighted Python code block -> Added tags.
      - Verified Autosave transitioned through Saving... -> Saved just now.
      - Switched notes and back (120ms fade-in verified).
      - Reloaded page: verified all title, table, checklist, and code blocks persisted exactly.
      - Mobile view (375px) tested with back navigation.
      - Inspected stored `.md` file on disk: confirmed clean YAML front-matter and standard Markdown body with zero data loss.
    - Captured 5 high-resolution screenshots into `docs/screenshots/`:
      - `stage5a-notes-list-light.png`
      - `stage5a-notes-list-dark.png`
      - `stage5a-context-menu.png`
      - `stage5a-editor-formatted.png`
      - `stage5a-mobile-view.png`
    - All 137 backend pytest tests continue to pass 100%.
    - Frontend TypeScript check and Vite production build pass cleanly with zero errors.

## How to Run

```sh
# Backend (port 8000)
cd backend
.venv\Scripts\python.exe wsgi.py

# Frontend dev server (port 5173/5174)
cd frontend
npm run dev

# Run automated browser verification test
node verify-stage5a.js

# Run backend test suite
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

## Next

- Stage 5B: Polish & Search / Command Palette (⌘K full integration, fuzzy search, attachment upload drag-drop in editor, keyboard shortcuts).

## Decisions

- Preserved backend port 8000 in `backend/wsgi.py` and configured Vite proxy to target `http://127.0.0.1:8000` to maintain consistency with Stage 0-3 verifications and single-container production specification.
- Used `@tailwindcss/vite` plugin with Tailwind CSS v4 and CSS theme variables for seamless design token integration with shadcn/ui components.
- Implemented inline anti-flash script in `index.html` to prevent layout/theme flashes when users reload in dark mode.
- Used `erasableSyntaxOnly` compatible class syntax in `ApiError` to satisfy TypeScript 7 strict compiler rules.
- Automated browser testing using Edge with `puppeteer-core` directly against the live dev server without downloading extra binaries.

- Validated file content signatures via byte markers (`_MAGIC` table and WebP RIFF/WEBP check) rather than trusting client MIME types or file extensions.
- Capped attachment uploads at 10 MB checked dynamically on streaming read to prevent memory exhaustion.
- Enforced strict user scoping on attachment retrieval and single/full export to guarantee data isolation.
- Used in-memory zip streaming generator with pre-flight size aggregation to ensure total export does not exceed 200 MB cap.
- Status route implements IMDSv2 token flow with 1.0s timeout to avoid blocking when running outside AWS EC2.
- In-memory 10-second cache with thread lock on `/api/status` prevents excessive polling load on CloudWatch and RDS APIs.
- Demo seeder checks existing records by title per user to ensure idempotency across multiple demo logins.

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
