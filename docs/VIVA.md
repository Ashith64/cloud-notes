# Viva Preparation Guide

This guide covers the key questions you will be asked about Cloud Notes in
the viva (oral examination).  Every answer describes what is **actually built**
in this project.

---

## Part 1 — Architecture

### Q: Describe the overall architecture of your application.

Cloud Notes runs entirely on AWS.  Here is what each piece does:

- **Browser**: The user opens the React web app in their browser.  The app is
  compiled TypeScript/React code that makes REST API calls to the backend.

- **Application Load Balancer (ALB)**: The first AWS resource the browser
  reaches.  It listens on port 80 (HTTP) and routes traffic to healthy EC2
  instances.  It also runs health checks every 15 seconds (`/api/health`).

- **Auto Scaling Group (ASG)**: A group of 1–2 EC2 `t3.micro` instances.
  Each instance runs a Docker container that serves both the Flask API and
  the compiled React frontend from a single process (gunicorn, port 8000).

- **RDS MySQL**: A managed relational database in private subnets.  It stores
  the users table, notebook metadata, the notes index (title, snippet, tags,
  flags), and attachment metadata.  It does **not** store note bodies.

- **S3**: An encrypted, private S3 bucket.  It stores the actual note content
  as Markdown files (`users/{id}/notes/{note_id}.md`) and attachments.
  S3 is the source of truth for note content — RDS is the searchable index.

- **CloudFormation**: Two YAML templates define every AWS resource.  Deploying
  or tearing down the whole stack is a single CLI command.

- **IAM Instance Role**: EC2 instances assume a least-privilege IAM role.
  There are no static access keys anywhere.

---

### Q: Draw the request flow from browser to database.

```
Browser
  → HTTP (port 80) → ALB (AlbSg: open to internet)
      → Port 8000 → EC2 Docker container (AppSg: accepts from AlbSg only)
          → JWT cookie validated (httpOnly, SameSite=Lax)
          → Flask route handler
              → MySQL query (DbSg: accepts port 3306 from AppSg only)
                  ← JSON response
              ← Flask returns JSON
          ← HTTP 200 JSON
      ← ALB forwards response
  ← Browser receives JSON
```

---

### Q: What is an Auto Scaling Group and how does it work here?

An **Auto Scaling Group (ASG)** is an AWS feature that automatically adds or
removes EC2 instances based on demand.

In Cloud Notes:
- The ASG is named `cloudnotes-asg`.
- It runs between 1 and 2 `t3.micro` instances.
- It uses a **Target Tracking Scaling Policy** targeting 50% average CPU:
  - If the average CPU across all instances exceeds 50% the ASG launches
    a new instance (up to MaxSize=2).
  - When CPU drops back down and stays low, the ASG terminates the extra
    instance (down to MinSize=1).
- New instances boot from a **Launch Template** that installs Docker, pulls
  the latest image from ECR, retrieves secrets from SSM, and starts the
  container automatically — no human intervention required.
- A **rolling update policy** ensures at least 1 instance stays in service
  during deployments (`MinInstancesInService: 1`).

---

### Q: Why is RDS in private subnets but EC2 in public subnets?

**RDS in private subnets**: The database should never be reachable from the
internet.  The private subnets have no internet route table entry at all, so
there is no network path from outside the VPC to the database.

**EC2 in public subnets**: The EC2 instances need to reach ECR (to pull Docker
images), SSM Parameter Store (to fetch secrets), S3 (to store/retrieve notes),
and CloudWatch (to send logs).  Putting them in private subnets would require a
NAT Gateway (~\$32/month) to reach these AWS endpoints.  Placing them in public
subnets with a strict security group (`AppSg` accepts port 8000 **only from the
ALB security group**) achieves the same isolation at zero extra cost.

---

### Q: What is CloudFormation and why use it?

CloudFormation is AWS's **Infrastructure as Code** service.  You write a YAML
template describing every resource, and CloudFormation creates, updates, or
deletes them in the correct order, handling dependencies automatically.

Benefits used in this project:
- Reproducibility: the same template can recreate the entire stack in another
  AWS account or region.
- Rollback: if a deployment fails, CloudFormation automatically reverses all
  changes.
- Auditability: the template is version-controlled in Git alongside the code.
- Teardown: `aws cloudformation delete-stack` removes all resources in one command.

---

## Part 2 — Request Flow

### Q: What happens when a user logs in?

1. The user submits their email and password on the login page.
2. The React app sends `POST /api/auth/login` with `X-Requested-With: cloudnotes`.
3. Flask looks up the user by email in MySQL.
4. Flask calls `bcrypt.checkpw()` to compare the submitted password with the
   stored hash.
5. If correct, Flask creates a JWT (`{"sub": user_id, "exp": now + 7 days}`)
   signed with `SECRET_KEY`, and sets it as an `httpOnly` cookie.
6. If 5 consecutive failed attempts occur, the account is locked for 10 minutes
   (counters stored in the `users` table in MySQL).

---

### Q: What happens when a user creates a note?

1. User clicks "New note" in the workspace.
2. React sends `POST /api/notes` with title and initial content.
3. Flask validates the cookie, identifies the user.
4. A UUID4 note ID is generated.
5. Flask writes the note as a Markdown file to S3:
   `users/{user_id}/notes/{note_id}.md` (with YAML front-matter).
6. Flask inserts a row into the MySQL `notes` table (title, snippet, search_text,
   notebook_id, tags, flags).
7. The editor then autosaves via `PATCH /api/notes/{id}` with an 800 ms debounce.

---

### Q: What happens when a user uploads an image attachment?

1. User drags/drops an image into the Milkdown editor.
2. React sends `POST /api/attachments` (multipart, with `file` and `note_id`).
3. Flask validates the cookie and verifies the note belongs to the user.
4. Flask reads the first bytes of the file to verify the **magic bytes** match a
   supported type (PNG, JPEG, GIF, WebP, PDF). No trust is placed on the filename.
5. Flask stores the file at `users/{user_id}/attachments/{id}.{ext}` in S3.
6. Flask returns `{id, ref, url}`.  The editor inserts `![](attachments/{id}.ext)`.
7. When the editor displays the attachment, it requests `GET /api/attachments/{id}`.
8. Flask verifies ownership, then returns HTTP 302 to a **presigned S3 URL**
   (expires in 300 seconds).  The browser downloads directly from S3.

---

## Part 3 — Scaling

### Q: How does the application scale to handle more traffic?

The Auto Scaling Group uses **CPU target tracking** at 50%.  When enough users
are active that the average CPU across all instances exceeds 50%, EC2 Auto
Scaling automatically launches a new instance (up to MaxSize=2).

This works seamlessly because the application is **stateless**:
- Notes and attachments live in S3 — not on the EC2 instance disk.
- The database is MySQL (RDS) — shared by all instances.
- The JWT cookie is verified with a shared `SECRET_KEY` from Secrets Manager —
  any instance can validate any user's cookie.
- There is no sticky session or server-side session state.

The ALB distributes new requests across all healthy instances using round-robin
load balancing.

---

### Q: What is stateless design and why does it matter for scaling?

A stateless server holds no per-user data between requests — everything it
needs to process a request comes from the request itself (the JWT cookie) or
shared external stores (MySQL, S3).

This matters for scaling because the load balancer can send any request to any
server.  If the app stored session data on disk or in memory, the user would
have to be routed to the same server every time (sticky sessions), which
complicates scaling and fails when instances are replaced.

---

### Q: How does a new EC2 instance know what to run?

The **EC2 Launch Template** contains a User Data bash script that runs
automatically when a new instance starts.  It:

1. Installs Docker.
2. Authenticates to ECR using the IAM instance role
   (`aws ecr get-login-password | docker login …`).
3. Fetches the JWT secret and DB password from SSM Parameter Store
   (`aws ssm get-parameter --with-decryption`).
4. Runs the Docker container with all environment variables and the
   CloudWatch Logs driver.

No human intervention is required — the instance is fully configured and
serving traffic within ~6–10 minutes of launch.

---

## Part 4 — Storage

### Q: Why are notes stored as Markdown files in S3 instead of in the database?

**S3 is the source of truth for note content** because:

- S3 object storage is designed for large amounts of text/binary data with
  built-in versioning, durability (11 nines), and encryption.
- The database (RDS) stores the **index** (title, snippet, search_text, tags,
  flags, timestamps) which is what you need for fast listing and filtering.
- The body of a note can be many KB or MB — storing it in MySQL would bloat
  the database and slow down list queries.
- Keeping content in files means the database is *reconstructible*: `flask reindex`
  reads all S3 files and rebuilds the MySQL index from scratch.

The file format is YAML front-matter + Markdown body:

```markdown
---
title: My Note
tags: [python, cloud]
created: 2026-11-01T10:00:00
updated: 2026-11-04T18:00:00
---
# Body content here
```

---

### Q: What is the two-place save and why is it safe?

When the user saves a note (`PATCH /api/notes/{id}`):

1. Flask writes the `.md` file to S3 **first**.
2. If the S3 write succeeds, Flask updates the MySQL row in a single transaction.
3. If the MySQL step fails, Flask returns a 500 error.  The client retries.
4. On retry, Flask overwrites the S3 file with the same content (idempotent)
   and tries the MySQL update again.

This is safe because:
- S3 PutObject is atomic — either the new version is stored or it is not.
- If MySQL fails, the content is already safe in S3.
- The database is always consistent with or behind S3 — it is never ahead.
- `flask reindex` can resynchronize the MySQL index from S3 at any time.

---

### Q: How are attachments stored and retrieved securely?

**Storage**: Attachments are stored in S3 at `users/{user_id}/attachments/{id}.ext`.
The bucket has all public access blocked.  No pre-signed upload URLs are used —
the backend receives the file and stores it.

**Retrieval**: `GET /api/attachments/{id}`:
1. Flask validates the JWT cookie.
2. Flask looks up the attachment in MySQL and verifies `user_id` matches.
3. Flask generates a **presigned S3 URL** valid for 300 seconds.
4. Flask returns HTTP 302 to that URL.
5. The browser downloads the file directly from S3.

Presigned URLs expire automatically — there is no need to revoke them.

---

## Part 5 — Security

### Q: How are passwords protected?

Passwords are hashed with **bcrypt** before being stored.  bcrypt is a
deliberately slow algorithm that includes a random salt (preventing rainbow
table attacks) and a work factor (making brute-force computationally expensive).

The original password is never stored and cannot be recovered — only verified
against the hash.

---

### Q: What is a JWT and how is it used here?

A **JSON Web Token (JWT)** is a signed, URL-safe string that contains a
payload (here: `{sub: user_id, exp: expiry_timestamp}`) and a cryptographic
signature.

After login, the backend creates a JWT signed with `SECRET_KEY` and places it
in an `httpOnly` cookie.  On every subsequent request:
1. Flask reads the cookie.
2. Flask calls `jwt.decode()` with the same `SECRET_KEY` to verify the signature.
3. If valid and not expired, Flask trusts the `sub` claim and sets `g.current_user`.

Because the cookie is `httpOnly`, JavaScript (including injected scripts) cannot
read it.  The `SameSite=Lax` attribute prevents the cookie from being sent in
cross-site requests.

---

### Q: What is the CSRF header and why is it needed?

Every state-changing API call (`POST`, `PATCH`, `DELETE`) must include:
```
X-Requested-With: cloudnotes
```

A malicious website can embed a form that auto-submits to your app URL.
The browser will attach cookies automatically (including the JWT cookie).
But the browser's Same-Origin Policy prevents the malicious site from setting
custom HTTP headers on cross-origin requests — so the `X-Requested-With` header
will not be present, and Flask will reject the request with HTTP 403.

---

### Q: How does the application avoid storing AWS credentials?

The EC2 instances assume an **IAM instance role** (`cloudnotes-instance-role`).
This role is attached to the instance at launch via an instance profile.
The AWS SDK (boto3) automatically retrieves temporary credentials from the EC2
Instance Metadata Service (IMDS) using this role — no access keys are needed.

The role is least-privilege: it can only access the specific S3 bucket, the
specific ECR repository, specific SSM parameters, and specific CloudWatch log group.
It cannot create or delete any AWS resources.

---

### Q: How is the database protected from internet access?

Three layers:

1. **Private subnets**: The RDS instance is in subnets with no internet
   route table entry — there is literally no route from the internet to the DB.
2. **Security group (`DbSg`)**: Only accepts TCP port 3306 from `AppSg`
   (the EC2 security group).  The ALB, the internet, and operators' machines
   cannot connect.
3. **`PubliclyAccessible: false`**: RDS refuses connections from outside the VPC
   even if a security group somehow allowed it.

---

## Quick Reference — Key Numbers

| Item | Value |
|------|-------|
| EC2 instance type | t3.micro (2 vCPU, 1 GB RAM) |
| ASG min / max | 1 / 2 |
| CPU scale-out target | 50% |
| Instance warmup | 120 s |
| ALB health check path | `/api/health` |
| Health check interval | 15 s |
| JWT expiry | 7 days |
| Account lockout | 5 failures → 10 minutes |
| Trash purge | 30 days |
| S3 presigned URL TTL | 300 s (5 min) |
| Attachment max size | 10 MB |
| Backend workers | 2 gunicorn workers × 4 threads |
| Local load test p95 | 178.74 ms |
| Local load test error rate | 0.00% |
| Backend test count | 207 tests, all passing |
