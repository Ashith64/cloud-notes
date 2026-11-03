# Cloud Notes

A polished student notes web app that runs on AWS. Notes are Markdown files (S3 in the cloud, a local folder in development).

## Features

- **Visual Editor**: Notion-style Markdown editor powered by Milkdown Crepe with slash commands, syntax highlighting, task lists, tables, and image/PDF attachments.
- **Organization**: Notebooks, tags, favorites, archive, and trash with 30-day lazy purge.
- **Search & Command Palette**: Instant full-text search with match highlighting via `Ctrl+K` / `⌘K`.
- **System Status**: Public status dashboard reporting live instance telemetry, compute, database and storage health.
- **Production Container**: Single multi-stage Docker container serving both the Flask API and the compiled React SPA.

## Tech Stack

- **Backend**: Python 3.12, Flask 3, SQLAlchemy 2, PyMySQL, PyJWT, bcrypt, boto3, python-frontmatter, gunicorn, pytest.
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, lucide-react, TanStack Query, Zustand, React Router, Sonner, @milkdown/crepe, @fontsource-variable/inter.
- **Database**: SQLite in local development, MySQL 8 in Docker Compose and on AWS RDS.
- **Storage**: Local filesystem in development, AWS S3 in production.

---

## Run Locally

### Prerequisites

- Python 3.12+
- Node.js 20+ and npm

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example ../.env

# Initialise database and seed demo data
flask init-db

# Run development server (port 8000)
python wsgi.py
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm ci

# Start development dev server (proxies /api to localhost:8000)
npm run dev

# Or compile production bundle
npm run build
```

The frontend dev server runs at `http://localhost:5173`. When built with `npm run build`, Flask automatically serves the production SPA from `http://localhost:8000`.

### 3. Run Backend Tests

```bash
cd backend
.venv\Scripts\pytest.exe tests/ -v
```

To run tests against a MySQL database:

```bash
# Set TEST_DATABASE_URL environment variable
$env:TEST_DATABASE_URL="mysql+pymysql://cloudnotes:cloudnotes_secret@127.0.0.1:3306/cloudnotes?charset=utf8mb4"
.venv\Scripts\pytest.exe tests/ -v
```

---

## Run with Docker

Cloud Notes packages the Flask API and the built React frontend into a single production Docker container.

### Prerequisites

- Docker Engine / Docker Desktop (with Compose V2)

### 1. Build and Start Services

From the project root:

```bash
docker compose up --build
```

This starts:
1. `mysql`: MySQL 8 with persistent volume `mysql_data` and healthcheck.
2. `app`: Multi-stage build (Node 20 builds frontend, Python 3.12-slim runs gunicorn with 2 workers and 4 threads). Wait script retries `flask init-db` until MySQL is healthy before starting Gunicorn.

### 2. Access the Application

- **Web App**: Open [http://localhost:8000](http://localhost:8000) in your browser.
  - Click **"Try demo account"** to log in immediately with pre-seeded student notes.
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Status Dashboard**: [http://localhost:8000/status](http://localhost:8000/status)

### 3. Stop Containers

```bash
docker compose down
```

Data in `mysql_data` and `app_storage` volumes persists across restarts. To perform a clean reset:

```bash
docker compose down -v
```
