# Limitations

This document is an honest record of the known limitations of the current
Cloud Notes deployment, the reasons those decisions were made, and what a
production upgrade would look like.

---

## HTTP Instead of HTTPS

**What it means**: Traffic between the browser and the ALB is unencrypted HTTP
on port 80.  An observer on the network can read note content, cookies, and
credentials in transit.

**Why it was done this way**: Obtaining an SSL/TLS certificate requires either
a registered domain name (for ACM DNS validation) or a publicly trusted CA
certificate.  Purchasing a domain and configuring Route 53 is out of scope for
this project.  AWS Certificate Manager (ACM) issues free certificates, but
they require domain ownership verification.

**Consequence**: The JWT session cookie is served without the `Secure` flag
(`COOKIE_SECURE=false` in the CloudFormation template).  This means the browser
may send the cookie over HTTP.

**Production upgrade**: 
1. Register a domain and create a Route 53 hosted zone.
2. Request an ACM certificate with DNS validation.
3. Add an HTTPS listener (port 443) to the ALB and attach the certificate.
4. Add an HTTP→HTTPS redirect rule on the port 80 listener.
5. Set `COOKIE_SECURE=true` in the container environment.

---

## Single AWS Region

**What it means**: All Cloud Notes resources (EC2, RDS, S3, ALB) are in
`ap-southeast-2` (Sydney).  Users in other continents will experience higher
latency.  An AWS regional outage would take down the entire application.

**Why it was done this way**: Multi-region deployments require cross-region
replication for RDS (Global Database) and S3 (Cross-Region Replication), Route
53 health checks, and Global Accelerator or CloudFront — far beyond the scope
of a student project.

**Production upgrade**: Deploy to two regions with an active-passive or
active-active configuration, RDS read replicas, S3 CRR, and Route 53 latency
or failover routing.

---

## Single-AZ RDS

**What it means**: The RDS MySQL instance runs in a single Availability Zone.
If that AZ experiences an outage, the database is unavailable until AWS
recovers the AZ or the user manually promotes a snapshot.

**Why it was done this way**: `MultiAZ: false` is intentional to avoid cost.
A Multi-AZ RDS instance costs approximately double (~\$37/month vs ~\$18.50/month).

**Production upgrade**: Set `MultiAZ: true` in `infra/02-app.yaml`.  AWS will
maintain a synchronous standby replica in a different AZ and will
automatically fail over in ~60–120 seconds if the primary AZ fails.

---

## EC2 Instances in Public Subnets

**What it means**: The EC2 application servers are in public subnets and are
assigned public IP addresses.  An internet scanning tool can reach the IP
directly on any port that is not blocked by the security group.

**Why it was done this way**: EC2 instances in private subnets need a NAT
Gateway to reach ECR, S3, SSM, and Secrets Manager endpoints.  A NAT Gateway
costs ~\$32 USD/month — roughly the same as the entire rest of the project.
The security group (`AppSg`) allows inbound traffic **only on port 8000 from
the ALB security group**, so no other port is reachable from the internet.

**Production upgrade**: Move EC2 instances to private subnets and add VPC
endpoints for ECR, S3, SSM, Secrets Manager, and CloudWatch Logs.  This
eliminates the public IP and the NAT Gateway.

---

## No Automatic Image Refresh on Deploy

**What it means**: When a new Docker image is pushed to ECR, the running EC2
instances continue running the old image.  A manual instance refresh or
redeployment is needed to roll out the new image.

**Why it was done this way**: The Launch Template pulls `cloudnotes:latest`
on each **new** instance launch.  Existing instances do not automatically
detect a new image.

**Current mitigation**: After pushing, run:
```bash
aws autoscaling start-instance-refresh \
    --auto-scaling-group-name cloudnotes-asg \
    --region ap-southeast-2
```
This performs a rolling replacement respecting `MinInstancesInService: 1`.

**Production upgrade**: Add an AWS CodePipeline / GitHub Actions CD pipeline
that triggers an instance refresh automatically after a successful ECR push.

---

## No Load Test Results on AWS

**What it means**: The k6 load test script (`loadtest/script.js`) was verified
locally against `localhost:8000` and produced the following results:

| Metric | Local result |
|--------|-------------|
| Total HTTP requests | 1,192 |
| Failed requests | 0 (0.00%) |
| p95 response time | 178.74 ms |
| All checks passed | 2,086 / 2,086 (100%) |
| Threshold: p95 < 800 ms | ✅ |
| Threshold: error rate < 1% | ✅ |

The two-run AWS load test (Run A: MaxSize=1 baseline, Run B: MaxSize=2
auto-scaling) described in the project guide was **not executed** — it requires
the live ALB and AWS approval, and was listed as pending user approval at the
end of Stage 11.

The load test script, documentation, and infrastructure changes (CloudFormation
parameter overrides) are fully prepared and documented in `loadtest/README.md`.

---

## No HTTPS / No Custom Domain

(See HTTP Instead of HTTPS above.  Listed separately as it also affects the
System Status page URL and any shared links.)

---

## No Version History (Could-Tier Feature)

The `note_history` table is defined in `backend/app/models.py` but the version
history feature (snapshot at most every 5 minutes) is not implemented in the
API or UI.  This is a deliberate Could-tier deferral per the project spec.

---

## SQLite in Development vs MySQL in Production

The development environment uses SQLite (chosen by `DATABASE_URL=sqlite:///dev.db`).
Production uses MySQL 8 on RDS.  Search uses SQL `LIKE` patterns on both
databases, so there is no collation mismatch, but subtle SQL dialect differences
(e.g., boolean handling, `LIMIT`/`OFFSET` corner cases) could appear if complex
queries are added.

The backend test suite runs against SQLite by default.  MySQL tests require
`TEST_DATABASE_URL` to be set to a live MySQL instance.

---

## No Real-Time Sync

The spec marks "near-instant sync" as a Could-tier feature.  The frontend
does not poll for changes from other sessions.  If the same account is logged
in on two devices, changes made on one device are not reflected on the other
until the user refreshes.

---

## Cookie Security Without HTTPS

The `SameSite=Lax` attribute provides partial CSRF protection but is less
effective without the `Secure` flag.  In a production deployment with HTTPS,
both attributes would be set.

---

## Summary Table

| Limitation | Severity | Fix |
|-----------|---------|-----|
| HTTP only (no TLS) | High | ACM cert + HTTPS ALB listener |
| Single-AZ RDS | Medium | `MultiAZ: true` in template |
| EC2 in public subnets | Low (SG-protected) | Private subnets + VPC endpoints |
| Single AWS region | Low for a student project | Multi-region architecture |
| No auto image refresh | Low | CD pipeline + instance refresh |
| No AWS load test results | Informational | Run approved k6 test against live ALB |
| No HTTPS cookie `Secure` flag | Medium (follows from HTTP limitation) | Fixed when TLS is added |
