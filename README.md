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


---

## Deploy to AWS

Cloud Notes deploys on AWS using a single CloudFormation stack (`infra/stack.yaml`) that provisions every resource: ECR, S3, RDS MySQL, Secrets Manager, ALB, Auto Scaling Group, and CloudWatch monitoring. The deployment has three ordered steps.

### Prerequisites

| Tool | Version | Notes |
| :--- | :--- | :--- |
| AWS CLI v2 | ≥ 2.13 | `aws configure` with region `ap-south-1` |
| Docker Engine / Docker Desktop | ≥ 24 | Required for `--platform linux/amd64` cross-builds |
| Git | Any | Used to tag the image with the current commit hash |

### Deployment Order

> [!IMPORTANT]
> The three steps below **must** be run in order. The ECR repository does not exist until the CloudFormation stack is deployed (Step 1), so the image cannot be pushed (Step 2) before that.

#### Step 1 — Deploy the CloudFormation Stack

This creates all AWS infrastructure: VPC security groups, RDS MySQL, ECR repository, S3 bucket, IAM roles, ALB, Auto Scaling Group, and CloudWatch alarms. It takes approximately 10–15 minutes, mostly waiting for RDS.

```bash
aws cloudformation deploy \
    --template-file infra/stack.yaml \
    --stack-name cloudnotes-app \
    --capabilities CAPABILITY_IAM \
    --region ap-south-1 \
    --parameter-overrides \
        VpcId=<your-vpc-id> \
        SubnetIds=<subnet-1>,<subnet-2> \
        AlertEmail=<your-email@example.com> \
        MinCapacity=1 \
        DesiredCapacity=1
```

> The template's default `DesiredCapacity` and `MinCapacity` are both `0` (safe for validation). Set them to `1` at deploy time to start the first EC2 instance.

After deployment, retrieve the `LoadBalancerUrl` output:

```bash
aws cloudformation describe-stacks \
    --stack-name cloudnotes-app \
    --region ap-south-1 \
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerUrl'].OutputValue" \
    --output text
```

#### Step 2 — Build and Push the Docker Image

Run the provided script from the project root. It handles ECR login, build, tagging, and push automatically.

**PowerShell (Windows):**
```powershell
.\scripts\push-image.ps1
```

**Bash (Linux / macOS / WSL):**
```bash
bash scripts/push-image.sh
```

The script:
1. Checks that `git`, `docker`, and `aws` are on `PATH`.
2. Calls `aws sts get-caller-identity` to obtain the AWS account ID dynamically — no hard-coded values.
3. Calls `aws cloudformation describe-stacks` to read the `EcrRepositoryUri` output — no hard-coded repository paths.
4. Authenticates Docker to ECR via `aws ecr get-login-password | docker login --username AWS --password-stdin ...` — the ECR token is piped and never printed.
5. Builds with `--platform linux/amd64` (matching the `t3.micro` x86_64 EC2 instance type).
6. Tags the image with the short Git commit hash **and** `latest`, then pushes both tags.
7. Prints only the resulting image URIs, never credentials.

Verify the image was pushed:
```bash
aws ecr describe-images \
    --repository-name cloudnotes-repo \
    --region ap-south-1
```

#### Step 3 — Trigger a Rolling Instance Refresh

If the stack was already deployed with `DesiredCapacity=1`, the Auto Scaling Group will automatically pull the `:latest` image on the next instance launch. To force an immediate refresh:

```bash
aws autoscaling start-instance-refresh \
    --auto-scaling-group-name cloudnotes-asg \
    --region ap-south-1
```

### Secret Management

> [!NOTE]
> Cloud Notes does **not** use SSM Parameter Store for runtime secrets. SSM parameters (`/cloudnotes/db-password`, `/cloudnotes/jwt-secret`) from the original tutorial guide are **not needed** — our architecture uses AWS Secrets Manager exclusively:
>
> - **Database credentials**: Generated and rotated automatically by RDS (`ManageMasterUserPassword: true`). Passed to the container as `DB_SECRET_ARN` so `backend/app/config.py` can fetch them at startup via the EC2 instance role.
> - **Application `SECRET_KEY`**: A 64-character random string generated at stack creation time by `AWS::SecretsManager::Secret` (`AppSecret`). Passed as `APP_SECRET_ARN`. Never appears in template outputs, logs, or Git.
>
> Both secrets are scoped to the instance role's `secretsmanager:GetSecretValue` policy and are never echoed to the terminal or stored in files.

### Teardown

```bash
# Delete the CloudFormation stack (RDS, ALB, ASG, ECR are removed automatically)
aws cloudformation delete-stack \
    --stack-name cloudnotes-app \
    --region ap-south-1

# The S3 bucket has DeletionPolicy: Retain — empty it manually first if needed:
aws s3 rm s3://cloudnotes-storage-<account-id> --recursive
aws s3 rb s3://cloudnotes-storage-<account-id> --force
```
