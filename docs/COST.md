# Cost

This document lists the AWS services used by Cloud Notes and their approximate
monthly cost in the **ap-southeast-2 (Sydney)** region.

> [!IMPORTANT]
> Cloud Notes was deployed to **ap-southeast-2** for the project.  Prices below
> are from the [AWS Pricing page](https://aws.amazon.com/pricing/) and the
> [AWS Pricing Calculator](https://calculator.aws/) at the time of writing.
> AWS prices change — always verify at [aws.amazon.com/pricing](https://aws.amazon.com/pricing/).
>
> Items marked **TO VERIFY** could not be confirmed from the official pricing
> pages at the time of writing and should be re-checked before submitting cost estimates.

---

## Deployed Services and Approximate Costs

### EC2 — t3.micro (Auto Scaling Group, 1–2 instances)

The ASG is configured with `MinSize=1`, `MaxSize=2`.  Under normal load only
one instance runs.

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| t3.micro On-Demand (1 instance, 24/7) | 2 vCPU, 1 GB RAM, ap-southeast-2 | ~\$10.90 USD |
| t3.micro On-Demand (2nd instance, occasional scale-out) | Depends on duration | Proportional — TO VERIFY exact rate |
| EBS root volume (gp3, 8 GB per instance) | Default AMI root | ~\$0.64 USD/month per instance |

> [!NOTE]
> t3.micro is **not** covered by the AWS Free Tier in ap-southeast-2 for new
> accounts past the first 12 months.  The price above is On-Demand.

### RDS MySQL 8.0 — db.t3.micro

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| db.t3.micro, Single-AZ, ap-southeast-2 | 2 vCPU, 1 GB RAM | ~\$18.50 USD |
| gp3 storage (20 GB) | Provisioned storage | ~\$2.76 USD |
| Automated backups (1-day retention) | Included up to DB size | \$0.00 |

> [!NOTE]
> db.t3.micro is not covered by the AWS Free Tier after the first 12 months.
> The Free Tier offers 750 hours/month of db.t2.micro or db.t3.micro (single-AZ)
> for the **first 12 months** only.

### S3 — Notes and Attachments Bucket

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| Standard storage (first 50 TB) | Per GB-month | ~\$0.025 USD/GB |
| PUT, COPY, POST, LIST requests | Per 1,000 requests | ~\$0.0055 USD/1,000 |
| GET, SELECT requests | Per 1,000 requests | ~\$0.00044 USD/1,000 |
| Data transfer out (to internet) | First 100 GB/month free | \$0.00 (within free tier) |

For a typical student project with ~100 notes and a few attachments, storage
is a few MB — **total S3 cost is effectively \$0.00/month**.

### Application Load Balancer (ALB)

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| ALB fixed hourly charge | ap-southeast-2 | ~\$0.0225 USD/hour ≈ **\$16.43 USD/month** |
| Load Balancer Capacity Units (LCUs) | Based on traffic | Minimal for student traffic — TO VERIFY |

> [!WARNING]
> The ALB is one of the larger fixed costs even with no traffic.  At low usage
> the LCU component is negligible, but the hourly charge applies 24/7.

### ECR — Docker Image Repository

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| Storage (first 500 MB/month) | Free Tier | \$0.00 |
| Data transfer to EC2 in same region | | \$0.00 |

A typical Cloud Notes Docker image is ~300–400 MB.  ECR cost is \$0.00 within
the free tier.

### SSM Parameter Store

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| Standard parameters (up to 10,000) | Free | \$0.00 |
| GetParameter API calls | Standard: \$0.00/10,000 | \$0.00 |

Cloud Notes uses 2 Standard SecureString parameters
(`/cloudnotes/db-password`, `/cloudnotes/jwt-secret`).

### CloudWatch

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| Log ingestion (first 5 GB/month) | Free Tier | \$0.00 |
| Log storage (first 5 GB/month) | Free Tier | \$0.00 |
| Dashboard (first 3 dashboards free) | Free Tier | \$0.00 |
| Alarms (4 alarms at \$0.10/alarm/month) | Standard resolution | ~\$0.40 USD |
| Metrics (EC2, RDS, ALB built-in) | Included | \$0.00 |

### SNS — Email Alerts

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| SNS notifications (first 1M/month) | Free Tier | \$0.00 |
| Email deliveries (first 1,000/month) | Free Tier | \$0.00 |

For 4 alarms in a student project, SNS cost is effectively \$0.00.

### VPC and Networking

| Item | Detail | Approx. monthly cost |
|------|--------|----------------------|
| VPC | | \$0.00 |
| Subnets | | \$0.00 |
| Internet Gateway | | \$0.00 |
| Security Groups | | \$0.00 |
| **NAT Gateway** | **Not used** | **\$0.00** |
| Data transfer (EC2 ↔ S3, same region) | Free | \$0.00 |

> [!TIP]
> Cloud Notes deliberately avoids NAT Gateways (~\$32 USD/month) by placing
> EC2 instances in public subnets and enforcing network isolation with security
> groups.

---

## Total Estimated Monthly Cost

| Service | Approx. cost (USD/month) |
|---------|--------------------------|
| EC2 t3.micro × 1 (On-Demand) | ~\$10.90 |
| EC2 EBS root volume (8 GB gp3) | ~\$0.64 |
| RDS db.t3.micro | ~\$18.50 |
| RDS gp3 storage (20 GB) | ~\$2.76 |
| ALB (fixed hourly) | ~\$16.43 |
| ALB LCUs (minimal traffic) | ~\$0.00–\$1.00 |
| S3 (< 1 GB data) | ~\$0.00 |
| CloudWatch (alarms) | ~\$0.40 |
| ECR, SSM, SNS | \$0.00 |
| **Total (1 instance, idle)** | **~\$49–\$50 USD/month** |
| **Total (peak, 2 instances)** | **~\$60–\$62 USD/month** |

> [!NOTE]
> These are estimates only.  Actual costs depend on data transfer volume,
> request rates, and whether the account is within the AWS Free Tier 12-month
> period.  Use the [AWS Pricing Calculator](https://calculator.aws/) for a
> precise quote.

---

## Cost Reduction Options (Not Implemented)

The following are **not part of this project** but would reduce cost in production:

- **Stop RDS and ASG when not needed**: The CloudFormation stack supports
  `DesiredCapacity=0`, which terminates EC2 instances.  RDS can be stopped
  manually for up to 7 days via the console.
- **Reserved Instances**: 1-year RIs for t3.micro EC2 and db.t3.micro RDS
  would reduce the compute cost by ~30–40% — TO VERIFY exact savings.
- **Savings Plans**: EC2 Compute Savings Plans offer flexible discounts across
  instance families — TO VERIFY current rates.
- **Fargate / Lambda**: Would eliminate the per-hour EC2 and ALB fixed charge
  at the cost of cold starts.
