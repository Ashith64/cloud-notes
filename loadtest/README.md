# Cloud Notes - Load Testing & Performance Verification (Stage 11)

This directory contains the automated performance and scalability test suite for **Cloud Notes**, implemented using [k6](https://k6.io/).

---

## 1. Workload Specification

The load test simulates realistic, concurrent student and user workflows across all tiers of the Cloud Notes architecture:

| Step | Operation | Method & Endpoint | Payload / Parameters | Success Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Authentication** | `POST /api/auth/demo` | `{}` | HTTP 200, JWT cookie received |
| **2** | **List Notes** | `GET /api/notes` | `?view=all&sort=updated` | HTTP 200, JSON array of note summaries |
| **3** | **Open Note** | `GET /api/notes/{id}` | Note ID from list | HTTP 200, note body & front-matter parsed |
| **4** | **Create Note** | `POST /api/notes` | Title, Markdown body, Tags | HTTP 201, note UUID & initial version returned |
| **5** | **Update Note** | `PATCH /api/notes/{id}` | Updated title & content | HTTP 200, version incremented |
| **6** | **Search** | `GET /api/notes` | `?q=model` / `?q=test` | HTTP 200, search results returned |
| **7** | **System Status** | `GET /api/status` | None | HTTP 200, `db_ok: true`, `storage_ok: true` |
| **8** | **Public Health** | `GET /api/health` | None | HTTP 200, lightweight ALB probe |

- **Security & Headers**: Every state-changing request transmits `Content-Type: application/json` and `X-Requested-With: cloudnotes` (CSRF protection). Authentication is maintained through the session cookie (`cloudnotes_token`).
- **Pacing**: Virtual users (VUs) pause for 1 second (`sleep(1)`) between iterations to emulate realistic human read/think times.

---

## 2. Load Profile & Thresholds

### 2.1 Stages

The test executes a 9-minute workload ramping from 0 to 40 concurrent virtual users:

```
VUs
40 |           +---------------------------------------+
   |          /                                         \
   |         /                                           \
10 |   +----+                                             \
   |  /                                                    \
 0 +--+-----+-------------------------------------------+---+
   0  1m    3m                                          8m  9m  Time
```

- **Stage 1 (00:00 - 01:00)**: Ramp up from 0 to 10 VUs (1 minute).
- **Stage 2 (01:00 - 03:00)**: Ramp up from 10 to 40 VUs (2 minutes).
- **Stage 3 (03:00 - 08:00)**: Sustained plateau at 40 concurrent VUs (5 minutes).
- **Stage 4 (08:00 - 09:00)**: Ramp down from 40 to 0 VUs (1 minute).

### 2.2 Service Level Objectives (SLOs) & Thresholds

- **Reliability**: `http_req_failed < 0.01` (failure rate strictly under **1%**).
- **Latency**: `http_req_duration p(95) < 800ms` (95% of all requests complete in under **800 ms**).

---

## 3. Running the Tests

### 3.1 Local Validation Test

Before executing against cloud infrastructure, verify the workload against a local application instance:

```powershell
# 1. Start backend server on localhost:8000
python wsgi.py

# 2. Run quick smoke validation (25 seconds)
backend\.venv\Scripts\k6.exe run -e QUICK=true -e BASE_URL=http://127.0.0.1:8000 loadtest/script.js

# 3. Run full local 9-minute test with JSON export
backend\.venv\Scripts\k6.exe run -e BASE_URL=http://127.0.0.1:8000 --summary-export=loadtest/results/local-summary.json loadtest/script.js
```

---

## 4. AWS Scaling Verification (Run A & Run B)

> **Important**: Run A and Run B are executed against the AWS ALB endpoint **only after explicit evaluator/operator approval**.

### 4.1 Run A: Single-Instance Baseline (MaxSize = 1)

Verifies single-node throughput and demonstrates that CPU target tracking alarm triggers when capacity is capped:

1. **Set MaxSize to 1 via CloudFormation**:
   ```sh
   aws cloudformation deploy \
     --template-file infra/02-app.yaml \
     --stack-name cloudnotes-app \
     --capabilities CAPABILITY_NAMED_IAM \
     --region ap-southeast-2 \
     --parameter-overrides MaxSize=1
   ```

   *(Alternative direct Auto Scaling CLI command:)*
   ```sh
   aws autoscaling update-auto-scaling-group \
     --auto-scaling-group-name cloudnotes-asg \
     --max-size 1 \
     --region ap-southeast-2
   ```

2. **Execute k6 Load Test**:
   ```sh
   backend\.venv\Scripts\k6.exe run \
     -e BASE_URL=http://cloudnotes-alb-460732187.ap-southeast-2.elb.amazonaws.com \
     --summary-export=loadtest/results/run-a-summary.json \
     loadtest/script.js
   ```

3. **Observations to Capture**:
   - Single EC2 instance CPU utilization (exceeds 50% target).
   - In-service instance count remains at 1.
   - Response time degradation and request rate.

---

### 4.2 Run B: Auto Scaling Verification (MaxSize = 2)

Proves automated scale-out under identical load conditions:

1. **Set MaxSize to 2 via CloudFormation**:
   ```sh
   aws cloudformation deploy \
     --template-file infra/02-app.yaml \
     --stack-name cloudnotes-app \
     --capabilities CAPABILITY_NAMED_IAM \
     --region ap-southeast-2 \
     --parameter-overrides MaxSize=2
   ```

   *(Alternative direct Auto Scaling CLI command:)*
   ```sh
   aws autoscaling update-auto-scaling-group \
     --auto-scaling-group-name cloudnotes-asg \
     --max-size 2 \
     --region ap-southeast-2
   ```

2. **Execute k6 Load Test**:
   ```sh
   backend\.venv\Scripts\k6.exe run \
     -e BASE_URL=http://cloudnotes-alb-460732187.ap-southeast-2.elb.amazonaws.com \
     --summary-export=loadtest/results/run-b-summary.json \
     loadtest/script.js
   ```

3. **Observations to Capture**:
   - Target tracking policy detects CPU > 50% and initiates scaling action.
   - Second EC2 instance (`t3.micro`) launches and passes ALB health checks (`/api/health`).
   - Auto Scaling Group instance count scales from 1 to 2 (`GroupInServiceInstances = 2`).
   - ALB distributes traffic across both instances, stabilizing p95 latency under 800 ms.
