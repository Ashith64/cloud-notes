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

- **Stage 8A: Infrastructure as Code & AWS Foundation Template (`infra/stack.yaml`)**
  - **CloudFormation Template** (`infra/stack.yaml`):
    - Target AWS region: `ap-south-1` (Mumbai).
    - Fully parameterized with 9 parameters: `ProjectName` (default `cloudnotes`), `VpcId`, `SubnetIds` (list of public subnets across AZs), `AlertEmail`, `ImageTag` (default `latest`), `InstanceType` (default `t3.micro`), `DBInstanceClass` (default `db.t3.micro`), `DesiredCapacity` (default `0`), `MaxCapacity` (default `2`).
    - **ECR Repository** (`EcrRepository`): Image scan on push enabled, lifecycle policy retaining 5 latest images, `EmptyOnDelete: true`, `DeletionPolicy: Delete`.
    - **S3 Bucket & Policy** (`NotesBucket`, `NotesBucketPolicy`): All public access blocked, bucket versioning enabled, AES256 server-side encryption default, lifecycle rules expiring non-current versions at 30 days and aborting incomplete multipart uploads at 7 days, policy denying non-TLS requests (`aws:SecureTransport: false`), `DeletionPolicy: Retain`.
    - **Secrets Manager** (`AppSecret`): Generates 64-character random alphanumeric string for application `SECRET_KEY`, `DeletionPolicy: Delete`. Database password managed by RDS via `ManageMasterUserPassword: true`.
    - **Security Groups Inbound Chain**:
      - `AlbSg`: TCP port 80 from internet (`0.0.0.0/0`).
      - `AppSg`: TCP port 8000 only from `AlbSg`.
      - `DbSg`: TCP port 3306 only from `AppSg`.
      - No other inbound rules.
    - **RDS MySQL 8** (`DBSubnetGroup`, `DBInstance`): Engine MySQL 8.0, 20 GB gp3 storage, single-AZ (`MultiAZ: false`), private (`PubliclyAccessible: false`), encrypted storage (`StorageEncrypted: true`), 7-day automated backups, deletion protection off, `DeleteAutomatedBackups: true`, skip final snapshot with `DeletionPolicy: Delete`.
    - **CloudWatch Log Group** (`AppLogGroup`): Retention period 14 days, `DeletionPolicy: Delete`.
    - **IAM Role & Instance Profile** (`AppInstanceRole`, `AppInstanceProfile`): Least-privilege inline policy scoped to specific ARNs:
      - S3: `s3:ListBucket`, `s3:GetBucketLocation` on bucket ARN; `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on bucket objects ARN (`/*`).
      - Secrets Manager: `secretsmanager:GetSecretValue` on `AppSecret` and RDS master secret ARN only.
      - ECR: `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` on ECR repo ARN only; `ecr:GetAuthorizationToken` on `*`.
      - CloudWatch Logs: `logs:CreateLogStream`, `logs:PutLogEvents`, `logs:DescribeLogStreams` on project log group ARN.
      - Status Page: `autoscaling:DescribeAutoScalingGroups`, `cloudwatch:GetMetricStatistics`, `rds:DescribeDBInstances` on `*` (read-only monitoring APIs).
    - **Outputs**: Defined exports for all resource identifiers, ARNs, database endpoints, security group IDs, and IAM profile names required by subsequent stages.
  - **Infrastructure Documentation** (`infra/README.md`):
    - Plain-language explanation of each resource, architectural role, and security configuration.
    - Explicit explanation of security group inbound chaining and least privilege IAM permissions.
    - Step-by-step template validation commands.
    - Honest documentation of S3 teardown and manual bucket cleanup procedures (`aws s3 rm` and `aws s3 rb`).
  - **Automated Validation & Tests** (`backend/tests/test_stage8a.py`):
    - 11 comprehensive automated tests validating template format, parameters, resources, security group chaining, IAM policies, S3 lifecycle, and outputs.
    - Total test suite: 168 tests passing across all suites.
    - **No resources deployed; template creation and validation only.**

- **Stage 8B: Application Stack Infrastructure (`infra/stack.yaml`)**
  - **Single Combined Template Architecture**: Extended `infra/stack.yaml` to include compute, load balancing, auto-scaling, monitoring, and alerting rather than introducing a disconnected second template or cross-stack imports.
  - **Parameters**: Added `BackupRetentionDays` (default 7), `MinCapacity` (default 0), and `CpuTarget` (default 50), while preserving existing parameter defaults (`DesiredCapacity: 0`, `MaxCapacity: 2`).
  - **RDS Updates**: Replaced hardcoded backup retention with `BackupRetentionPeriod: !Ref BackupRetentionDays`.
  - **Log Group Updates**: Updated `AppLogGroup` retention from 14 days to 7 days (`RetentionInDays: 7`).
  - **IAM Instance Role Updates**: Attached AWS managed policy `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore` for keyless terminal access via AWS Systems Manager Session Manager (eliminating SSH port 22 requirements), and added least-privilege `ssm:GetParameter` policy scoped to `arn:aws:ssm:...:parameter/cloudnotes/*`.
  - **SNS Alerts Topic & Subscription**: Added `AlertsTopic` and `AlertsEmailSubscription` sending operational notifications to `AlertEmail`.
  - **EC2 Launch Template (`AppLaunchTemplate`)**:
    - Image: AL2023 x86_64 AMI dynamic lookup via SSM parameter `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`.
    - Security: IMDSv2 strictly required (`HttpTokens: required`), metadata hop limit set to 2 (`HttpPutResponseHopLimit: 2`), standard CPU credits, detailed 1-minute monitoring enabled, no keypair.
    - User Data: Automated bash script installing Docker, logging into ECR via instance role (`aws ecr get-login-password`), and starting application container on port 8000 with `awslogs` driver. Reuses Secrets Manager ARNs (`DB_SECRET_ARN`, `APP_SECRET_ARN`) directly to maintain compatibility with Stage 7 backend without leaking or hardcoding secret values.
  - **Application Load Balancer & Target Group (`AppAlb`, `AppTargetGroup`, `AppAlbListener`)**:
    - Internet-facing ALB in public subnets with `AlbSg` security group.
    - Port 8000 target group with `/api/health` health checks (interval 15s, healthy threshold 2, unhealthy threshold 3).
    - Port 80 HTTP listener forwarding traffic to target group.
  - **Auto Scaling Group & Target Tracking (`AppAsg`, `AppScalingPolicy`)**:
    - Named `cloudnotes-asg` across public subnets.
    - ELB health check type with 300s grace period and 1-minute metrics collection.
    - Rolling update policy (`AutoScalingRollingUpdate`).
    - CPU target-tracking policy maintaining average CPU utilization at `CpuTarget` (50%) with 120s instance warmup.
  - **CloudWatch Alarms (4 Alarms)**:
    - `AlarmAsgHighCpu`: ASG CPU > 70% for 2 minutes.
    - `AlarmAlbTarget5xx`: ALB target 5XX count >= 10 in 5 minutes.
    - `AlarmAlbUnhealthyHosts`: Unhealthy host count >= 1 for 2 minutes.
    - `AlarmRdsHighCpu`: RDS MySQL CPU > 80% for 5 minutes.
    - All alarms notify `AlertsTopic`.
  - **CloudWatch Dashboard (`AppDashboard`)**:
    - Dashboard named `cloudnotes` with 8 operational metric widgets (ASG CPU, in-service instances, ALB requests, target response time, 5xx errors, healthy hosts, RDS CPU, RDS connections).
  - **Outputs**:
    - Added `LoadBalancerUrl`, `DashboardUrl`, `DbEndpoint`, `AlertsTopicArn`, and `LoadBalancerDnsName`.
  - **Testing & Verification**:
    - Added `backend/tests/test_stage8b.py` with 12 comprehensive automated test cases.
    - Verified all 180 project tests pass cleanly.
    - Template syntax and structure verified via Python AST and PyYAML parser.
    - **No resources deployed; template creation and validation only.**

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

# Run all 180 backend tests
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

- **Stage 9: Secrets Architecture & ECR Image Push Scripts**
  - **Architecture Decision — No SSM create-secrets script**: The original Stage 9 guide describes generating `/cloudnotes/db-password` and `/cloudnotes/jwt-secret` in SSM Parameter Store. This step is **not applicable to our architecture**. Our Stage 7 backend (`backend/app/config.py`) resolves secrets via `DB_SECRET_ARN` and `APP_SECRET_ARN` using AWS Secrets Manager. Both secrets are created and managed by CloudFormation/RDS (`AppSecret` + `ManageMasterUserPassword: true`) — no additional SSM parameters are required or created. Creating them would introduce unused, orphaned credentials conflicting with the established interface.
  - **`scripts/push-image.ps1`** (PowerShell for Windows):
    - Prerequisite checks for `git`, `docker`, and `aws` with clear failure messages.
    - Dynamically resolves AWS account ID via `aws sts get-caller-identity`.
    - Dynamically resolves ECR repository URI from the `EcrRepositoryUri` CloudFormation stack output via `aws cloudformation describe-stacks`.
    - Authenticates Docker to ECR via `aws ecr get-login-password | docker login --username AWS --password-stdin ...` — token is piped, never printed.
    - Builds image with `--platform linux/amd64` targeting `t3.micro` x86_64 EC2 instances.
    - Tags with short `git rev-parse --short HEAD` commit hash **and** `latest`.
    - Pushes both tags and prints only image URIs, never credentials.
    - Fails safely on any error; does not overwrite local project files.
  - **`scripts/push-image.sh`** (Bash for Linux / macOS / WSL):
    - Identical logic to the PowerShell script; supports `--stack-name` and `--region` arguments.
    - Uses `set -euo pipefail` for safe error propagation.
  - **Tests** (`backend/tests/test_stage9.py`): 23 automated tests covering existence, no hard-coded account IDs, no secret echoing, ECR authentication pattern, `--platform linux/amd64`, two-tag push, prerequisite check presence, CloudFormation prerequisite documentation, ECR URI resolved from stack output, and `git rev-parse` tag sourcing.
  - **README.md** (`README.md`): Added a comprehensive **Deploy to AWS** section covering the three-step deployment order (CloudFormation → image push → instance refresh), secret management rationale, and teardown instructions.
  - **All 203 backend tests pass** (180 prior + 23 new Stage 9 tests) in 35.20s. No regressions.
  - **Scripts not yet executed** — pending explicit user approval and a deployed CloudFormation stack.

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

# Run all 203 backend tests
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

- **Deployment Execution (Stage 10 Deploy Phase)**:
  1. Deploy CloudFormation stack: `aws cloudformation deploy --template-file infra/stack.yaml --stack-name cloudnotes-app --capabilities CAPABILITY_IAM --region ap-south-1 --parameter-overrides VpcId=<vpc-id> SubnetIds=<subnet-1>,<subnet-2> AlertEmail=<email> DesiredCapacity=1 MinCapacity=1`
  2. Build and push Docker image to ECR: `.\scripts\push-image.ps1` (Windows) or `bash scripts/push-image.sh`
  3. Verify: `aws ecr describe-images --repository-name cloudnotes-repo --region ap-south-1`
  4. Open `LoadBalancerUrl`, test demo login, upload image, verify `/status` page.

## Decisions

- **No SSM create-secrets script**: The original Stage 9 guide's SSM parameter creation step is unnecessary for our Secrets Manager-based architecture. `DB_SECRET_ARN` is the RDS-managed master secret, and `APP_SECRET_ARN` is the CloudFormation `AppSecret`. Creating separate SSM parameters (`/cloudnotes/db-password`, `/cloudnotes/jwt-secret`) would create orphaned credentials the backend never reads.
- **Scripts resolve ECR URI from CloudFormation outputs**: Both `push-image.ps1` and `push-image.sh` call `aws cloudformation describe-stacks` to obtain `EcrRepositoryUri`, ensuring no account ID or repository path is ever hard-coded.**: Extends the existing Stage 8A template to keep resource definitions, internal references (`!Ref`, `!GetAtt`), and security group rules cohesive without relying on fragile cross-stack imports.
- **Secrets Manager Integration Preserved**: Preserved Stage 7 AWS Secrets Manager pattern (`DB_SECRET_ARN`, `APP_SECRET_ARN`, `ManageMasterUserPassword: true`). Secrets are queried securely by the container via IAM instance role at startup, rather than passing raw credentials into UserData or template parameters.
- **Capacity & Cost Safety**: `DesiredCapacity` and `MinCapacity` default to `0` in the CloudFormation template, ensuring that template syntax and resources can be created or validated without launching billable EC2 compute instances.
- **Session Manager Access**: `AmazonSSMManagedInstanceCore` managed policy attached to `AppInstanceRole` enables AWS Systems Manager Session Manager, allowing SSH-free terminal access without opening port 22 or provisioning keypairs.
- **IMDSv2 Hop Limit**: Configured `HttpPutResponseHopLimit: 2` in `AppLaunchTemplate` to allow Docker containers to query EC2 instance metadata (instance ID and Availability Zone) for `/api/status`.
- Structured JSON logging uses `json.dumps` with UTC timestamps and standard field names (`time`, `level`, `message`, `request_id`, `route`, `status`, `duration_ms`).
- In-memory cache `_SECRETS_CACHE` prevents repeated AWS Secrets Manager calls across multiple worker threads or configuration reads.
- `COOKIE_SECURE` is explicitly configurable via environment variable (default `false`) so Docker Compose local testing over HTTP functions properly, while production CloudFormation sets `COOKIE_SECURE=false` (for HTTP ALB listener without custom SSL certificate).
- SPA fallback serves `index.html` for non-API routes when `FRONTEND_DIST_DIR` is present, while strictly returning JSON 404s for any `/api/*` path.
- `docker-entrypoint.sh` uses POSIX shell with retry loop (30 attempts x 2s) for database initialization to handle MySQL startup latency.
- S3 `DeletionPolicy: Retain` prevents CloudFormation stack deletion failure if the bucket has objects or versions; documented honest manual bucket emptying and deletion in `infra/README.md`.
- RDS `ManageMasterUserPassword: true` allows RDS to generate, encrypt, and manage master database credentials in Secrets Manager without exposing passwords in templates or outputs.
- ECR `EmptyOnDelete: true` allows CloudFormation to cleanly remove the repository upon stack deletion without manual image deletion.
- Security group inbound chain strictly enforces ALB (HTTP 80 from internet) -> App (port 8000 from AlbSg) -> DB (port 3306 from AppSg) with no other inbound rules.

## Known Issues & Pending Verifications

- **Scripts not yet executed**: `scripts/push-image.ps1` and `scripts/push-image.sh` are prepared and tested but have **not** been run. Execution requires a deployed CloudFormation stack (ECR repository does not exist locally), Docker Desktop, and AWS CLI with valid credentials.
- **Docker & MySQL Verification**: Docker CLI is not installed / accessible in the local host environment. Live container startup (`docker compose up --build`) remains pending an active Docker runtime.
- **AWS CLI & cfn-lint**: `aws` CLI and `cfn-lint` are not installed locally on this host environment. CloudFormation template validity verified via automated Python AST test suites only. AWS remote validation (`aws cloudformation validate-template`) is pending CLI installation.
- `local_data/` is created on first storage write, not on startup (matches lazy initialization).
