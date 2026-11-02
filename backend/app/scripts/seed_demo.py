"""Demo seed script for Cloud Notes (spec C1, Stage 3).

Creates 3 notebooks and 12 realistic notes for the demo user
(demo@cloudnotes.app).  Safe to call multiple times — fully idempotent.

Usage:
    FLASK_APP=wsgi:app flask shell -c "from app.scripts.seed_demo import seed; seed()"

Or call seed(user, db, storage, app) directly from the /api/auth/demo route.
"""
import logging
import uuid
from datetime import datetime, timezone

import frontmatter

from ..models import Attachment, Note, NoteTag, Notebook, Tag
from ..utils import make_snippet, strip_markdown

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Note content
# ---------------------------------------------------------------------------

_NOTEBOOKS = ["College", "Projects", "Personal"]

# Each entry: (title, notebook_name, tags, is_pinned, is_favorite, content)
_NOTES: list[tuple[str, str, list[str], bool, bool, str]] = [

    # ── College ──────────────────────────────────────────────────────────────

    (
        "OSI model",
        "College",
        ["networking", "osi", "exam-prep"],
        False, False,
        """\
## The OSI Reference Model

The **Open Systems Interconnection** model divides network communication into seven layers.

| Layer | Name         | Key Protocols           | Data Unit  |
|-------|--------------|-------------------------|------------|
| 7     | Application  | HTTP, FTP, SMTP, DNS    | Message    |
| 6     | Presentation | TLS/SSL, JPEG, ASCII    | Data       |
| 5     | Session      | NetBIOS, RPC            | Data       |
| 4     | Transport    | TCP, UDP                | Segment    |
| 3     | Network      | IP, ICMP, OSPF          | Packet     |
| 2     | Data Link    | Ethernet, Wi-Fi (802.11)| Frame      |
| 1     | Physical     | Cables, radio waves     | Bits       |

### Memory Aid

> **A**ll **P**eople **S**eem **T**o **N**eed **D**ata **P**rocessing

### Key exam points

- TCP is **connection-oriented** (3-way handshake); UDP is **connectionless**.
- IP addresses live at Layer 3; MAC addresses live at Layer 2.
- TLS operates between Layers 4 and 7 (often said to be Layer 6/7).
""",
    ),

    (
        "AWS EC2 basics",
        "College",
        ["aws", "ec2", "cloud", "exam-prep"],
        True, False,
        """\
## Amazon EC2 – Elastic Compute Cloud

EC2 provides resizable **virtual machines** (instances) in the AWS cloud.

### Instance types (family examples)

- `t3.micro` — burstable general purpose (free tier eligible)
- `m6i.large` — balanced CPU / RAM for web servers
- `c6g.xlarge` — compute-optimised (Graviton 2)
- `r6i.2xlarge` — memory-optimised for databases

### Pricing models

1. **On-Demand** — pay per second, no commitment (most expensive per hour)
2. **Reserved** — 1 or 3-year commitment, up to 72 % discount
3. **Spot** — bid on spare capacity, up to 90 % discount, can be interrupted
4. **Savings Plans** — flexible discount in exchange for $/hr commitment

### Launch checklist

- [ ] Choose AMI (Amazon Machine Image)
- [ ] Select instance type
- [ ] Configure VPC and subnet
- [ ] Assign Security Group (firewall rules)
- [ ] Add IAM instance role (no keys in code!)
- [ ] Set User Data script for bootstrap
- [ ] Enable termination protection for production

```bash
# Connect via SSM (no inbound SSH needed)
aws ssm start-session --target i-0abc1234def567890
```

> **Pro tip:** Use IMDSv2 (`X-aws-ec2-metadata-token`) for all metadata calls.
""",
    ),

    (
        "Docker vs Virtual Machines",
        "College",
        ["docker", "containers", "virtualisation", "exam-prep"],
        False, False,
        """\
## Containers vs Virtual Machines

Both technologies isolate workloads, but they do it at different levels.

### Architecture

```
┌──────────┬──────────┐      ┌──────────┬──────────┐
│  App A   │  App B   │      │  App A   │  App B   │
├──────────┴──────────┤      ├──────────┴──────────┤
│  Container runtime  │      │  Guest OS │ Guest OS │
│     (Docker)        │      ├──────────┴──────────┤
├─────────────────────┤      │       Hypervisor     │
│      Host OS        │      ├─────────────────────┤
├─────────────────────┤      │       Host OS        │
│      Hardware       │      ├─────────────────────┤
└─────────────────────┘      │       Hardware       │
      Containers              └─────────────────────┘
                                 Virtual Machines
```

### Comparison

| Property        | Containers          | Virtual Machines     |
|-----------------|---------------------|----------------------|
| Startup time    | Milliseconds        | Minutes              |
| Size            | MBs                 | GBs                  |
| Isolation       | Process-level       | Full OS-level        |
| Portability     | High (image = code) | Medium (disk image)  |
| Overhead        | Low                 | High                 |

### When to use which

- **Containers** — microservices, CI/CD pipelines, stateless web apps.
- **VMs** — strong isolation requirements, full OS customisation, legacy apps.

Cloud Notes uses Docker to package the Flask API + built React app into one
image that runs identically on a developer laptop and on EC2.
""",
    ),

    (
        "How Load Balancing Works",
        "College",
        ["networking", "aws", "alb", "exam-prep"],
        False, True,
        """\
## Load Balancing

A **load balancer** distributes incoming requests across multiple servers so
that no single server becomes a bottleneck.

### Algorithms

1. **Round Robin** — requests cycle sequentially through servers (default ALB)
2. **Least Connections** — request goes to the server with fewest active connections
3. **IP Hash** — same client IP always reaches the same server (sticky sessions)
4. **Weighted** — servers get traffic proportional to their weight (capacity)

### AWS Application Load Balancer (ALB)

- Operates at **Layer 7** (HTTP/HTTPS), so it can route based on URL paths and headers.
- Performs **health checks** (`GET /api/health`) and removes unhealthy targets.
- Terminates **TLS** — instances only see plain HTTP internally.
- Provides **access logs** and CloudWatch metrics out of the box.

### Health check flow

```
ALB every 30 s → GET /api/health → 200 OK → target is healthy
                               → timeout/5xx → unhealthy → removed from pool
```

### Why this project uses ALB

Cloud Notes runs behind an ALB in an Auto Scaling Group.  When a second
instance is launched during load, the ALB instantly starts sending it traffic
without any DNS changes or downtime.
""",
    ),

    (
        "IaaS PaaS SaaS",
        "College",
        ["cloud", "models", "exam-prep"],
        False, False,
        """\
## Cloud Service Models

### IaaS – Infrastructure as a Service

You manage: OS, runtime, middleware, data, applications  
Provider manages: hardware, networking, virtualisation

**Examples:** AWS EC2, Google Compute Engine, Azure VMs

### PaaS – Platform as a Service

You manage: data and applications  
Provider manages: everything below the app

**Examples:** AWS Elastic Beanstalk, Heroku, Google App Engine

### SaaS – Software as a Service

You manage: configuration and your data  
Provider manages: everything

**Examples:** Gmail, Dropbox, Notion, Salesforce

### Quick comparison

| Model | You manage          | Provider manages          |
|-------|---------------------|---------------------------|
| IaaS  | OS → App            | Hardware, network, VMs    |
| PaaS  | App + Data          | OS, runtime, middleware   |
| SaaS  | Settings, data      | Everything                |

### This project

Cloud Notes is deployed using **IaaS** (EC2 instances) because:
- We need full control over the Docker runtime.
- RDS is a **managed database** (PaaS-like).
- S3 is an **object store** (also PaaS-like).

Together they form a hybrid architecture typical of modern cloud applications.
""",
    ),

    (
        "S3 Storage Classes",
        "College",
        ["aws", "s3", "storage", "exam-prep"],
        False, False,
        """\
## Amazon S3 Storage Classes

S3 offers multiple storage tiers with different cost/availability trade-offs.

| Class                     | Availability | Min duration | Use case                      |
|---------------------------|--------------|--------------|-------------------------------|
| S3 Standard               | 99.99 %      | None         | Frequently accessed data      |
| S3 Intelligent-Tiering    | 99.9 %       | None         | Unknown or changing access    |
| S3 Standard-IA            | 99.9 %       | 30 days      | Infrequent access, rapid retrieval |
| S3 One Zone-IA            | 99.5 %       | 30 days      | Infrequent, non-critical      |
| S3 Glacier Instant        | 99.9 %       | 90 days      | Archives, millisecond retrieval|
| S3 Glacier Flexible       | 99.99 %      | 90 days      | Archives, minutes to hours    |
| S3 Glacier Deep Archive   | 99.99 %      | 180 days     | Long-term, 12-h retrieval     |

### Cloud Notes uses S3 Standard

- Note `.md` files and attachment uploads go to **S3 Standard**.
- Versioning is **enabled** on the bucket (protects against accidental overwrites).
- **SSE-S3** (AES-256) encryption is applied to every object.
- The bucket is **private** — no public access policies.

### Access pattern

Attachments are served via 300-second **presigned URLs** so the client
downloads directly from S3 without proxying through the app server.
""",
    ),

    (
        "IAM Least Privilege",
        "College",
        ["aws", "iam", "security", "exam-prep"],
        False, False,
        """\
## IAM Least Privilege Principle

> Grant only the permissions required to perform the task — nothing more.

### Why it matters

- Limits the blast radius if an instance is compromised.
- Reduces the risk of accidental data deletion or exfiltration.
- Required for most compliance frameworks (SOC 2, ISO 27001, GDPR).

### Cloud Notes IAM policy (summary)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:HeadObject",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cloudnotes-bucket",
        "arn:aws:s3:::cloudnotes-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:GetParameter"],
      "Resource": "arn:aws:ssm:*:*:parameter/cloudnotes/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}
```

### Best practices

- [ ] Use **IAM roles** for EC2 instances — no access keys in code or config files.
- [ ] Rotate credentials regularly for human users.
- [ ] Enable **MFA** for all console access.
- [ ] Use **IAM Access Analyzer** to find overly permissive policies.
- [ ] Review permissions quarterly and remove unused ones.
""",
    ),

    (
        "CAP Theorem",
        "College",
        ["distributed-systems", "databases", "exam-prep"],
        False, False,
        """\
## CAP Theorem

Proposed by Eric Brewer (2000): in a distributed data store you can only
**guarantee two of three** properties simultaneously.

```
          Consistency
             /\\
            /  \\
           /    \\
          / CA   \\
         /  RDBMS \\
        /──────────\\
       /  CP    AP  \\
      / HBase  Dynamo\\
     /────────────────\\
Partition Tolerance ── Availability
```

### The three properties

| Property            | Meaning                                                         |
|---------------------|-----------------------------------------------------------------|
| **Consistency** (C) | Every read receives the most recent write or an error          |
| **Availability** (A)| Every request receives a (non-error) response                  |
| **Partition Tolerance** (P) | System continues despite network partitions            |

### Real systems

- **CP** (Consistent + Partition Tolerant): HBase, Zookeeper, etcd — sacrifice availability during partitions.
- **AP** (Available + Partition Tolerant): DynamoDB, Cassandra, CouchDB — may return stale data.
- **CA** (Consistent + Available): Traditional RDBMS (PostgreSQL, MySQL) — only works without partitions (single node).

### Practical note

Network partitions *will* happen in any real distributed system, so the
practical choice is almost always between **CP** and **AP**.

Cloud Notes uses MySQL (CA in single-node dev, effectively CP with RDS Multi-AZ).
""",
    ),

    (
        "Semester 5 exam plan",
        "College",
        ["planning", "exams"],
        False, False,
        """\
## Semester 5 Exam Plan

### Exam schedule

| Subject                   | Date       | Time  | Room  |
|---------------------------|------------|-------|-------|
| Cloud Computing           | 2026-11-15 | 10:00 | LH-3  |
| Distributed Systems       | 2026-11-18 | 14:00 | LH-1  |
| Software Engineering      | 2026-11-21 | 10:00 | LH-2  |
| Database Management       | 2026-11-25 | 14:00 | LH-3  |

### Weekly study plan

- [ ] **Week 1 (Nov 3–9):** Cloud Computing — EC2, S3, IAM, VPC, CloudFormation
- [ ] **Week 2 (Nov 10–14):** Distributed Systems — CAP theorem, consensus, Paxos
- [ ] **Week 3 (Nov 15–20):** Software Engineering — UML, Agile, design patterns
- [ ] **Week 4 (Nov 21–24):** DBMS — normalisation, transactions, indexing

### Resources

- Lecture slides on LMS portal
- [AWS Documentation](https://docs.aws.amazon.com/)
- Tanenbaum: *Distributed Systems, 4th ed.*
- Silberschatz: *Database System Concepts, 7th ed.*

### Revision checklist

- [ ] OSI model layers and protocols
- [ ] TCP/IP 3-way handshake
- [ ] Load balancing algorithms
- [ ] CAP theorem with examples
- [ ] Docker vs VMs trade-offs
- [ ] IAM least privilege
- [ ] Normalisation up to 3NF
""",
    ),

    # ── Projects ─────────────────────────────────────────────────────────────

    (
        "Project Ideas",
        "Projects",
        ["ideas", "projects"],
        False, True,
        """\
## Project Ideas for Portfolio

### In progress

- **Cloud Notes** (this app!) — Full-stack note-taking app deployed on AWS
  - Flask + React + S3 + RDS + CloudFormation
  - [GitHub repo](https://github.com/example/cloud-notes)

### Queue

1. **Serverless URL Shortener**
   - AWS Lambda + API Gateway + DynamoDB
   - Custom domain via Route 53
   - Analytics dashboard with QuickSight

2. **Real-time Chat App**
   - WebSockets (Flask-SocketIO or AWS API Gateway WebSocket)
   - Message history in DynamoDB
   - Presence indicator

3. **CI/CD Pipeline Visualiser**
   - Poll GitHub Actions / Jenkins API
   - React dashboard with live updates
   - Deployed on ECS Fargate

4. **Personal Finance Tracker**
   - Plaid API for bank data import
   - FastAPI backend + Supabase
   - Budget alerts via SNS

### Completed

- Portfolio website (static, S3 + CloudFront)
- Weather dashboard (OpenWeatherMap API)
- CLI task manager (Python, SQLite)

### Evaluation criteria

| Criterion        | Weight |
|------------------|--------|
| AWS services used| 30 %   |
| Code quality     | 25 %   |
| Documentation    | 20 %   |
| UI polish        | 15 %   |
| Test coverage    | 10 %   |
""",
    ),

    # ── Personal ─────────────────────────────────────────────────────────────

    (
        "Weekly Timetable",
        "Personal",
        ["schedule", "routine"],
        False, False,
        """\
## Weekly Study Timetable

| Time          | Monday        | Tuesday       | Wednesday     | Thursday      | Friday        |
|---------------|---------------|---------------|---------------|---------------|---------------|
| 07:00–08:00   | Morning run   | Morning run   | Rest          | Morning run   | Rest          |
| 09:00–11:00   | Cloud Comp.   | Dist. Systems | Cloud Comp.   | Soft. Eng.    | DBMS          |
| 11:00–13:00   | Project work  | Project work  | Dist. Systems | Project work  | Project work  |
| 14:00–16:00   | Lectures      | Lectures      | Lectures      | Lectures      | Revision      |
| 16:00–18:00   | Self-study    | Self-study    | Self-study    | Self-study    | Self-study    |
| 20:00–22:00   | Reading       | Coding        | Reading       | Coding        | Free          |

### Rules

- [ ] No social media before 18:00 on weekdays
- [ ] 8 hours of sleep minimum
- [ ] One full rest day per weekend
- [ ] Review notes within 24 hours of each lecture (spaced repetition)

### Productivity tips

- Use Pomodoro: 25 min focus → 5 min break → repeat × 4 → 30 min break
- Keep phone in another room during study blocks
- Write a "done list" each evening alongside tomorrow's task list
""",
    ),

    (
        "Reading List",
        "Personal",
        ["books", "reading"],
        False, False,
        """\
## Reading List

### Currently reading

- 📖 **The Pragmatic Programmer** — Hunt & Thomas *(ch. 7 of 8)*

### Technical — queue

1. **Designing Data-Intensive Applications** — Martin Kleppmann ⭐ *must-read*
2. **Clean Code** — Robert C. Martin
3. **Site Reliability Engineering** — Beyer et al. (O'Reilly, free online)
4. **The Phoenix Project** — Kim, Behr, Spafford *(DevOps novel)*
5. **Kubernetes in Action** — Lukša

### Non-technical — queue

1. **Deep Work** — Cal Newport
2. **Atomic Habits** — James Clear *(re-read)*
3. **The Lean Startup** — Eric Ries

### Completed this year

- ✅ *Computer Networking: A Top-Down Approach* — Kurose & Ross
- ✅ *Python Crash Course* — Eric Matthes
- ✅ *Eloquent JavaScript* — Marijn Haverbeke

### Tracking

| Book                          | Started    | Finished   | Rating |
|-------------------------------|------------|------------|--------|
| Python Crash Course           | 2026-01-10 | 2026-02-05 | ⭐⭐⭐⭐   |
| Networking Top-Down Approach  | 2026-03-01 | 2026-06-20 | ⭐⭐⭐⭐⭐  |
| The Pragmatic Programmer      | 2026-09-15 | —          | —      |
""",
    ),
]


# ---------------------------------------------------------------------------
# Public seeding function
# ---------------------------------------------------------------------------

def seed(user, db, storage, app) -> None:
    """Create 3 notebooks and 12 demo notes for *user*.  Idempotent.

    Args:
        user:    SQLAlchemy User instance (already committed).
        db:      SQLAlchemy session (scoped).
        storage: StorageBase instance.
        app:     Flask app (for config/context).
    """
    from datetime import timedelta

    user_id = user.id
    log.info("Seeding demo data for user %s", user_id)

    # ── 1. Notebooks (idempotent by name) ────────────────────────────────────
    notebooks: dict[str, int] = {}
    for nb_name in _NOTEBOOKS:
        nb = db.query(Notebook).filter_by(user_id=user_id, name=nb_name).first()
        if not nb:
            nb = Notebook(user_id=user_id, name=nb_name)
            db.add(nb)
            db.flush()
        notebooks[nb_name] = nb.id

    db.flush()

    # ── 2. Notes (idempotent by title within the user) ────────────────────────
    now = datetime.now(timezone.utc)

    for idx, (title, nb_name, tags, is_pinned, is_favorite, body) in enumerate(_NOTES):
        # Check if this note already exists for this user
        existing = db.query(Note).filter_by(user_id=user_id, title=title).first()
        if existing:
            log.debug("Demo note '%s' already exists, skipping", title)
            continue

        note_id = str(uuid.uuid4())
        notebook_id = notebooks[nb_name]

        # Stagger creation times so the list looks natural
        created_at = now - timedelta(days=len(_NOTES) - idx, hours=idx * 2)
        updated_at = created_at + timedelta(hours=idx % 4)

        # Prepare front-matter file
        clean_tags: list[str] = []
        for t in tags:
            n = t.strip().lower()[:30]
            if n and n not in clean_tags:
                clean_tags.append(n)

        meta = {
            "title": title,
            "tags": clean_tags,
            "created": created_at.isoformat(),
            "updated": updated_at.isoformat(),
            "notebook": nb_name,
            "notebook name": nb_name,
        }
        post = frontmatter.Post(body, **meta)
        file_content = frontmatter.dumps(post)

        storage_key = f"users/{user_id}/notes/{note_id}.md"

        try:
            storage.put_text(storage_key, file_content)
        except Exception:
            log.exception("Storage error seeding note '%s'", title)
            continue

        plain = strip_markdown(body)
        snippet = make_snippet(body)

        note = Note(
            id=note_id,
            user_id=user_id,
            notebook_id=notebook_id,
            title=title,
            snippet=snippet,
            search_text=plain,
            storage_key=storage_key,
            is_pinned=is_pinned,
            is_favorite=is_favorite,
            version=1,
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(note)
        db.flush()

        # Tags
        for tag_name in clean_tags:
            tag = db.query(Tag).filter_by(user_id=user_id, name=tag_name).first()
            if not tag:
                tag = Tag(user_id=user_id, name=tag_name)
                db.add(tag)
                db.flush()
            # Avoid duplicate note_tags
            from ..models import NoteTag
            exists = db.query(NoteTag).filter_by(note_id=note_id, tag_id=tag.id).first()
            if not exists:
                db.add(NoteTag(note_id=note_id, tag_id=tag.id))

    db.commit()
    log.info("Demo seed complete for user %s", user_id)
