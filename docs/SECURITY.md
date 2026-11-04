# Security

This document describes the security measures in Cloud Notes.

---

## Authentication and Password Hashing

User passwords are hashed with **bcrypt** (using the `bcrypt` Python library)
before they are stored in the database.  Bcrypt is a deliberately slow,
salted hashing algorithm designed to resist brute-force and rainbow-table attacks.

```
Registration:
  raw password → bcrypt.hashpw(password, bcrypt.gensalt()) → stored hash

Login:
  raw password + stored hash → bcrypt.checkpw() → True / False
```

Error messages are intentionally generic: *"That email or password doesn't look
right"* — the same message is returned whether the email does not exist or the
password is wrong, so an attacker cannot enumerate registered accounts.

**Account lockout**: After 5 consecutive failed login attempts the account is
locked for 10 minutes.  The `failed_logins` counter and `locked_until` timestamp
are stored in the `users` table (not in memory), so the lockout works correctly
across multiple server instances behind the load balancer.

---

## JWT Cookies and CSRF Protection

After a successful login the backend issues a **JSON Web Token (JWT)**:

```
Payload: { "sub": "<user_id>", "exp": <now + 7 days> }
Signed with:  HMAC-SHA256 using SECRET_KEY (fetched from Secrets Manager)
```

The token is delivered as an **httpOnly, SameSite=Lax cookie** named `session`:

| Cookie attribute | Value | Why |
|-----------------|-------|-----|
| `HttpOnly` | ✅ | JavaScript cannot read the cookie — prevents XSS token theft |
| `SameSite=Lax` | ✅ | Cookie is not sent on cross-site POST requests |
| `Secure` | ❌ (HTTP ALB) | Disabled because the ALB listener is HTTP only |
| `Path` | `/` | Sent on all API requests |

**CSRF protection**: Every state-changing request (`POST`, `PATCH`, `DELETE`)
must include the custom header:

```
X-Requested-With: cloudnotes
```

This header cannot be set by a cross-origin form submission or by a plain `<img>`
tag — it requires JavaScript with `fetch()` or `XMLHttpRequest` from the **same
origin**.  Combined with `SameSite=Lax`, this prevents Cross-Site Request Forgery.

The `csrf_required` decorator in `backend/app/routes/auth.py` enforces this
check and returns HTTP 403 if the header is absent.

---

## User Data Isolation

Every database query in Cloud Notes is **scoped to the authenticated user**.
The `login_required` decorator resolves the JWT, sets `g.current_user`, and
all subsequent queries filter by `user_id = g.current_user.id`.

Examples:
- `GET /api/notes` → `SELECT … WHERE user_id = :uid`
- `GET /api/notes/:id` → returns 404 if the note exists but belongs to a different user
- `GET /api/attachments/:id` → checks ownership before issuing a presigned URL

There is no admin override route and no cross-user data access path in the codebase.

S3 objects are stored under a per-user prefix:
```
users/{user_id}/notes/{note_id}.md
users/{user_id}/attachments/{id}.{ext}
```

A user who somehow guessed another user's S3 key could not retrieve the file
directly — the bucket has **all public access blocked** and all downloads go
through the backend, which enforces ownership.

---

## Private S3 Bucket

The notes S3 bucket is configured with:

| Setting | Value |
|---------|-------|
| Public access block | All four settings enabled |
| Bucket policy | Denies any request where `aws:SecureTransport = false` |
| Default encryption | AES-256 (SSE-S3) |
| Versioning | Enabled |
| ACLs | Disabled (bucket-owner enforced) |

No bucket policy grants public read access.  All object access goes through
the Flask backend, which uses the **IAM instance role** (boto3 default
credential chain) — no access keys are stored anywhere.

**Attachment downloads** in S3 mode use **presigned GET URLs** that:
- Expire after 300 seconds (5 minutes).
- Are scoped to the exact S3 key.
- Are generated only after the backend verifies the requesting user owns the attachment.

---

## IAM Instance Role and Least Privilege

The EC2 instances use the `cloudnotes-instance-role` IAM role — there are no
static access keys anywhere in the codebase, configuration files, or CloudFormation
templates.

The role has the **minimum permissions** needed to run the application:

| Permission | Resource | Reason |
|-----------|---------|--------|
| `s3:ListBucket`, `s3:GetBucketLocation` | Specific bucket ARN | Storage health check and list |
| `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | Bucket objects (`/*`) | Note and attachment storage |
| `ecr:GetAuthorizationToken` | `*` (AWS requirement) | Docker login to ECR |
| `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` | Specific ECR repo ARN | Docker image pull |
| `logs:CreateLogStream`, `logs:PutLogEvents`, `logs:DescribeLogStreams` | Specific log group ARN | Structured application logging |
| `ssm:GetParameter` | `/cloudnotes/db-password` and `/cloudnotes/jwt-secret` only | Retrieve secrets at boot |
| `autoscaling:DescribeAutoScalingGroups`, `cloudwatch:GetMetricStatistics`, `rds:DescribeDBInstances` | `*` (read-only APIs) | System Status page metrics |

The role does **not** have:
- `s3:*` or `s3:DeleteBucket`
- `iam:*`
- `ec2:*`
- `rds:*` write permissions
- Access to any SSM parameter outside `/cloudnotes/`
- Access to Secrets Manager (secrets are in SSM Parameter Store)

---

## Security Groups and Private RDS

Security groups implement a strict **ingress chain** — no traffic bypasses it:

```
Internet (0.0.0.0/0)
      │
      ▼ port 80
  AlbSg  ←── only inbound from internet
      │
      ▼ port 8000  (source: AlbSg only)
  AppSg  ←── no direct internet access
      │
      ▼ port 3306  (source: AppSg only)
   DbSg  ←── no internet path exists
```

| Security group | Inbound rules | Outbound |
|---------------|--------------|---------|
| `AlbSg` | TCP 80 from `0.0.0.0/0` | All (default) |
| `AppSg` | TCP 8000 from `AlbSg` | All (default) |
| `DbSg` | TCP 3306 from `AppSg` | All (default) |

No SSH port (22) is open on any security group.  Operator access uses
**AWS Systems Manager Session Manager**, which connects over HTTPS to the SSM
endpoint without requiring any inbound firewall rule.

**RDS isolation**: The `DbSubnetGroup` spans two private subnets that have no
internet route table entry and no NAT Gateway.  The only network path to the
database is from an EC2 instance with `AppSg` attached — not from the internet,
not from the ALB, and not from an operator workstation.

**IMDSv2**: The EC2 Launch Template enforces `HttpTokens: required` (IMDSv2
only) with a hop limit of 2, which allows the Docker container to query the
instance metadata service (for instance ID and AZ) while preventing
unauthenticated metadata access from outside the container.
