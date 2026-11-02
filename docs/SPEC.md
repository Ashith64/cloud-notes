Part C. Product specification
(Parts C and D are written as a spec. In Part F you will save them as docs/SPEC.md so Antigravity reads them before every stage.)
C1. Feature tiers
Tier	Feature	Notes
Must	Sign up, log in, log out, change password, "Try demo account" button	bcrypt hashes, JWT in an httpOnly cookie; demo button seeds 12 sample notes so the evaluator sees a full app instantly
Must	Notes with a Notion-style visual editor	Slash menu, floating toolbar, headings, lists, checklists, links, code blocks, tables, images
Must	Autosave	Shows "Saving..." then "Saved just now"
Must	Notebooks (folders) and tags	Sidebar lists both; filter by either
Must	Pin, favorite, archive	Pinned notes float to top of the list
Must	Search	Top search box with instant results, plus Ctrl/Cmd+K command palette
Must	Trash with restore	30-day retention, lazy purge (see D3), manual "Empty trash"
Must	Attachments	Drag, drop or paste images; also PDFs; private S3
Must	Export	Single note as .md, everything as a .zip with an attachments folder
Must	Dark mode	Follows system by default, toggle in top bar
Must	Responsive layout	Three panes on desktop, one pane at a time on phone
Must	System Status page	Live server id, running servers, CPU, DB and S3 health, last backup
Should	Keyboard shortcuts	Ctrl/Cmd+K search, Ctrl/Cmd+N new note, Ctrl/Cmd+Shift+L toggle theme
Should	Settings page	Storage used, change password, theme, export all
Should	Skeleton loaders, toasts with Undo, empty states, error pages	The details that make it feel real
Could	Version history	Snapshot at most every 5 minutes or on closing a note
Could	Near-instant sync	Poll every 5 seconds; a stale save becomes a "conflict copy"
Could	[[Note links]], backlinks, graph view	Highest risk; skip unless everything else is finished
Deliberately out: AI features, real-time co-editing, native apps, plugins, share links, import, PWA offline.
C2. Design system (follow exactly)
Mood: calm, airy, lots of white space, one accent colour. Think Apple Notes meets Linear.
Token	Light	Dark
background	#FAFAF9	#0F0F11
surface (cards, editor)	#FFFFFF	#17171A
sidebar	#F5F5F4	#131315
border	#E7E5E4	#27272A
text	#1C1917	#F4F4F5
muted text	#78716C	#A1A1AA
accent	#4F46E5	#818CF8
accent soft	#EEF2FF	#1E1B4B
danger / success	#DC2626 / #16A34A	#F87171 / #4ADE80
    • Fonts: Inter (self-hosted via @fontsource-variable/inter, no CDN) for the UI; JetBrains Mono only in code blocks.
    • Editor typography: 17px body, line-height 1.75, content column max 720px, centred; note title 32px bold with no border.
    • Shape and depth: radius 12px on cards, 8px on buttons and inputs, 1px borders, card shadow 0 1px 2px rgba(0,0,0,.04), on hover 0 4px 12px rgba(0,0,0,.06).
    • Motion: 150ms ease-out for hover, theme change and panel transitions; 120ms fade when switching notes. No bouncy animations.
    • Icons: lucide-react only, 18px, stroke 1.75.
    • Layout: sidebar 248px, note list 340px, editor takes the rest. 1024px and up: three panes. 640 to 1023px: sidebar becomes a slide-in drawer. Under 640px: one pane at a time with a back arrow, a hamburger menu, and a floating "+" button.
    • Accessibility: visible focus rings in the accent colour, contrast at least 4.5:1, every icon button has an aria-label, all actions reachable by keyboard.
C3. Screens and behaviour
    1. Login / Sign up. Desktop is a split layout: left a soft indigo gradient panel with the app name, the tagline "Your notes, anywhere" and three one-line benefits; right a centred form card. Show/hide password, friendly errors ("That email or password doesn't look right"), a Try demo account button under the form. Phone shows the form only.
    2. Workspace.
        ◦ Top bar: search field (opens the command palette when focused), New note button, theme toggle, avatar menu (Settings, System Status, Export all, Log out).
        ◦ Sidebar: All Notes, Favorites, Archive, Trash; then Notebooks (with a + to add, rename and delete in a hover menu); then Tags with counts.
        ◦ Note list: sections Pinned and Recent. Each card shows title, two-line preview, tag chips, relative time ("2h ago"). Hovering reveals pin and trash icons; right click opens a context menu (Pin, Favorite, Move to notebook, Archive, Export, Delete). Selected card gets the accent-soft background.
        ◦ Editor: big borderless title, tag chips with an inline "+ tag" input, the Crepe editor, a quiet footer with save status and a "..." menu (Export, Move to notebook, Archive, Delete).
        ◦ Empty states: friendly icon in a soft circle, one line of text, one button. Examples: "No notes yet. Create your first note", "Trash is empty", "No results for 'xyz'".
    3. Command palette (Ctrl/Cmd+K). One box that searches notes (live, highlighted match) and lists actions: New note, Toggle theme, Go to notebook, Open System Status.
    4. Settings. Storage used (progress bar), change password, theme choice (System, Light, Dark), Export all (.zip).
    5. System Status (public, no login). Cards: this server's instance id and availability zone, number of running servers, average CPU, database status, storage status, last automated backup time, app version. Auto-refreshes every 5 seconds; this is what you watch during the load test.
    6. Feedback rules. Skeleton loaders instead of spinners. After delete show "Moved to Trash. Undo" for 6 seconds. Network failure shows "Can't reach the server. Retrying..." and retries automatically. Unsaved changes are never lost: if a save fails, keep retrying with back-off and show "Not saved yet".
Part D. Architecture, data and API
D1. The picture
Browser (React app)
      |  HTTP
      v
Application Load Balancer  (health check: /api/health)
      |
      v
Auto Scaling Group: 1 to 2 EC2 instances (t3.micro)
   each runs ONE Docker container: Flask API + built React app, via gunicorn
      |                      |                          |
      v                      v                          v
RDS MySQL (private)     S3 bucket (private,        CloudWatch Logs, Metrics,
users, note index,      versioned): note .md       Alarms -> SNS email
tags, trash flags       files + attachments

Supporting: VPC + security groups, IAM instance role (no keys in code),
SSM Parameter Store (DB password, JWT secret), ECR (Docker images)
D2. Components and why they exist
Component	Role	Rubric concept
EC2 in an Auto Scaling Group	Runs the container; replaced if it dies	IaaS, scaling
Docker + ECR	One image holds backend and frontend	Containers
ALB	Spreads traffic, checks health	Load balancing
RDS MySQL (private, automated backups)	Users, note index, search	Managed database
S3 (private, versioned, encrypted)	Source of truth for notes and attachments	Object storage
IAM instance role	Instance may only touch its bucket, parameters, logs	IAM, least privilege
Security groups	Internet to ALB only; ALB to EC2 only; EC2 to RDS only	Network security
CloudWatch + SNS	Dashboard, alarms, email alerts	Monitoring
CloudFormation template	Whole stack created and deleted with one command	Infrastructure as code
D3. Key design decisions (do not change)
    1. One container serves everything. Flask serves /api/* and the built React files, so there is one image, one port (8000), one health check.
    2. Storage abstraction. A Storage interface with LocalStorage (folder on disk, for development) and S3Storage (production), chosen by STORAGE_BACKEND. This lets everything be built and tested on your laptop with zero AWS usage.
    3. Database abstraction. SQLite locally, MySQL 8 in Docker Compose and on RDS, chosen by DATABASE_URL. Search uses LIKE (simple and works on both).
    4. Notes are Markdown files; the database is an index. Path: users/{user_id}/notes/{note_id}.md. File format: a small front-matter block (title, tags, created, updated) followed by the body. The editor only ever sees the body.
    5. Safe two-place save. Write the .md to storage first, then update the database row in one transaction. If the database step fails, return an error and the client retries; the next save overwrites the file with the same content, so nothing is half-saved. Provide a command flask reindex that rebuilds the database index from the files, which proves the files are the source of truth.
    6. Attachments never use expiring links inside notes. The .md stores a stable reference ![](attachments/<id>.png). The editor displays it through /api/attachments/<id>, which checks the login cookie, then redirects to a short-lived presigned S3 URL (or streams the file in local mode). Exports include a real attachments/ folder.
    7. Lazy trash purge. No scheduler. Whenever the Trash list or Empty trash is requested, permanently delete that user's notes whose deleted_at is older than 30 days. Document this as a design choice.
    8. Auth. Passwords hashed with bcrypt. Login sets a JWT (7 days) in an httpOnly, SameSite=Lax cookie. State-changing requests must carry the header X-Requested-With: cloudnotes. Five failed logins lock the account for 10 minutes (counters kept in the database so they work across servers).
    9. Stateless servers. No session or file kept on the instance, so the load balancer can send any request to any server and scaling just works.
    10. Secrets. Never in code or Git. Local: .env (git-ignored). AWS: SSM Parameter Store SecureString, read at container start via the instance role.
D4. Data model
    • users: id, email (unique), name, password_hash, failed_logins, locked_until, created_at
    • notebooks: id, user_id, name, created_at; unique (user_id, name)
    • notes: id (uuid), user_id, notebook_id (nullable), title, snippet (first 200 characters of plain text), search_text (plain text of the body), storage_key, is_pinned, is_favorite, is_archived, deleted_at (nullable), version (integer, +1 per save), created_at, updated_at
    • tags: id, user_id, name; unique (user_id, name). note_tags: note_id, tag_id
    • attachments: id (uuid), user_id, note_id, filename, content_type, size_bytes, storage_key, created_at
    • note_history (Could tier): id, note_id, storage_key, created_at
Indexes on notes (user_id, updated_at), (user_id, deleted_at), and on title.
D5. API contract
All JSON. Errors look like {"error": {"code": "not_found", "message": "Note not found"}} with correct HTTP status. Every route except health, status and auth requires the cookie, and every query is scoped to the logged-in user.
Area	Endpoints
Auth	POST /api/auth/register, /login, /logout, /change-password, /demo; GET /api/auth/me
Notes	GET /api/notes?view=all|favorites|archive|trash&notebook_id=&tag=&q=&sort=updated|created|title&limit=&offset= (summaries, no body); POST /api/notes; GET /api/notes/{id} (with body); PATCH /api/notes/{id} (title, content, notebook_id, tags[], is_pinned, is_favorite, is_archived, base_version); DELETE /api/notes/{id} (to trash); POST /api/notes/{id}/restore; DELETE /api/notes/{id}/permanent; POST /api/trash/empty
Notebooks	GET, POST /api/notebooks; PATCH, DELETE /api/notebooks/{id} (deleting keeps the notes, just unfiled)
Tags	GET /api/tags (name and note count)
Attachments	POST /api/attachments (multipart: file, note_id; max 10 MB; png, jpg, gif, webp, pdf only) returns {id, ref, url}; GET /api/attachments/{id}
Export	GET /api/notes/{id}/export (one .md); GET /api/export (zip: notes/*.md, attachments/*)
System	GET /api/health (public, no database call, returns 200); GET /api/status (public: instance id, availability zone, running servers, CPU, db ok, storage ok, last backup, version)
Note JSON: id, title, snippet, notebook_id, tags[], is_pinned, is_favorite, is_archived, deleted_at, version, created_at, updated_at plus content on the detail route.
