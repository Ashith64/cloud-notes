# Cloud Notes Infrastructure (AWS CloudFormation)

This directory contains the AWS CloudFormation template and documentation for deploying the **Cloud Notes** web application on Amazon Web Services in region `ap-south-1` (Mumbai).

> **Important**: In Stage 8A, this template is created and validated only. **Nothing has been deployed yet.**

---

## Architecture Overview

The infrastructure follows a multi-tier, least-privilege architecture:

```
Internet (Browser)
       │ HTTP (Port 80)
       ▼
Application Load Balancer (AlbSg)
       │ TCP (Port 8000)
       ▼
Auto Scaling Group / EC2 Instances (AppSg)
       │
       ├─► MySQL 8 Database (RDS private, single-AZ, DbSg, Port 3306)
       ├─► S3 Bucket (Private, versioned, encrypted notes & attachments)
       ├─► Secrets Manager (App SECRET_KEY & RDS Master DB Password)
       ├─► Amazon ECR (Docker image registry)
       └─► CloudWatch Logs (Centralized application log group)
```

---

## Stack Parameters (`infra/stack.yaml`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ProjectName` | String | `cloudnotes` | Prefix used for resource naming and resource tags. |
| `VpcId` | `AWS::EC2::VPC::Id` | *(None)* | The target VPC (typically the default VPC). |
| `SubnetIds` | `List<AWS::EC2::Subnet::Id>` | *(None)* | At least two public subnet IDs in different Availability Zones. |
| `AlertEmail` | String | *(None)* | Operator email address for CloudWatch alarm notifications. |
| `ImageTag` | String | `latest` | Tag of the container image to pull from ECR. |
| `InstanceType` | String | `t3.micro` | EC2 instance size for application servers. |
| `DBInstanceClass` | String | `db.t3.micro` | RDS MySQL instance class. |
| `DesiredCapacity` | Number | `0` | Initial target count of instances (0 during initial setup). |
| `MaxCapacity` | Number | `2` | Maximum instance limit for Auto Scaling Group. |

---

## Resources Explained in Plain Language

### 1. Amazon ECR Repository (`EcrRepository`)
- **What it is**: A private Docker container image registry hosted on AWS.
- **Why it exists**: Stores the unified Docker image containing the Flask backend and compiled React single-page frontend.
- **Key Settings**:
  - `ImageScanningConfiguration.ScanOnPush: true`: Scans pushed container images automatically for software vulnerabilities.
  - `LifecyclePolicy`: Automatically retains only the last 5 images, pruning older images to prevent accumulating storage costs.
  - `EmptyOnDelete: true`: Allows the ECR repository to be cleanly removed if the stack is deleted, even if it still contains Docker images.
  - `DeletionPolicy: Delete`: Removes the repository automatically when the CloudFormation stack is deleted.

### 2. Amazon S3 Storage Bucket & Bucket Policy (`NotesBucket`, `NotesBucketPolicy`)
- **What it is**: Highly durable, secure object storage.
- **Why it exists**: Serves as the primary source of truth for user notes (stored as Markdown `.md` files) and uploaded user attachments (images, PDFs).
- **Key Settings**:
  - `PublicAccessBlockConfiguration`: All 4 public access block settings (`BlockPublicAcls`, `BlockPublicPolicy`, `IgnorePublicAcls`, `RestrictPublicBuckets`) are enabled. The bucket and all objects are completely private.
  - `VersioningConfiguration.Status: Enabled`: Keeps previous revisions of notes and attachments, protecting against accidental deletion or corruption.
  - `BucketEncryption`: Enforces AES-256 server-side encryption (`SSE-S3`) on all stored objects at rest.
  - `LifecycleConfiguration`:
    - Automatically expires non-current versions after 30 days to keep storage costs predictable.
    - Aborts incomplete multipart uploads after 7 days so orphaned chunks do not accumulate.
  - `NotesBucketPolicy`: Enforces transport security by explicitly denying any access requests made over unencrypted HTTP (`aws:SecureTransport: false`).
  - **Deletion Policy (`DeletionPolicy: Retain`)**: S3 buckets containing objects or versioned objects cannot be deleted by CloudFormation directly. Setting `Retain` guarantees that deleting the CloudFormation stack will succeed without failing on a non-empty bucket. *See the Teardown & Manual Cleanup section below for instructions on emptying and removing the bucket.*

### 3. AWS Secrets Manager (`AppSecret` & RDS Master User Secret)
- **What it is**: Secure, encrypted secret storage service.
- **Why it exists**: Keeps application and database secrets out of source code, environment files, and version control.
- **Secrets Defined**:
  1. `AppSecret`: Stores a 64-character randomly generated alphanumeric string used by Flask as `SECRET_KEY` for cryptographically signing JWT authentication session cookies.
  2. `DBInstance.MasterUserSecret`: Managed automatically by RDS via `ManageMasterUserPassword: true`. RDS generates, encrypts, and rotates the database master password in Secrets Manager without exposing credentials in the CloudFormation template or outputs.

### 4. Security Groups (`AlbSg`, `AppSg`, `DbSg`)
A strict, three-tier inbound security chain:
1. **`AlbSg` (Load Balancer)**:
   - Inbound: Accepts TCP port 80 (HTTP) from `0.0.0.0/0` (the internet).
   - Outbound: Allows traffic to downstream targets.
2. **`AppSg` (EC2 Instances)**:
   - Inbound: Accepts TCP port 8000 **only from `AlbSg`**. Direct internet access to the application instances is strictly blocked.
   - Outbound: Allows traffic to AWS APIs (Secrets Manager, S3, ECR, CloudWatch) and to the RDS database on port 3306.
3. **`DbSg` (RDS MySQL Database)**:
   - Inbound: Accepts TCP port 3306 **only from `AppSg`**.
   - No direct access from the internet or the load balancer is possible.

### 5. Amazon RDS MySQL 8 Database (`DBSubnetGroup`, `DBInstance`)
- **What it is**: A managed relational database instance running MySQL 8.
- **Why it exists**: Maintains the metadata index for users, notebooks, tags, notes metadata, search text, and trash flags.
- **Key Settings**:
  - `DBInstanceClass`: Configurable via parameter (default `db.t3.micro`).
  - `AllocatedStorage`: 20 GB `gp3` storage with encryption at rest (`StorageEncrypted: true`).
  - `PubliclyAccessible: false`: The database has no public IP address and lives entirely inside the VPC private network.
  - `MultiAZ: false`: Single Availability Zone deployment to minimize costs.
  - `BackupRetentionPeriod: 7`: Automated daily snapshots retained for 7 days.
  - `DeletionProtection: false` and `DeleteAutomatedBackups: true`: Ensures teardown can be executed cleanly.
  - `DeletionPolicy: Delete`: Skips the final snapshot upon CloudFormation stack deletion for clean, immediate removal.
  - `DBSubnetGroup`: Spans across the provided subnet IDs in multiple AZs.

### 6. CloudWatch Log Group (`AppLogGroup`)
- **What it is**: Centralized AWS log management.
- **Why it exists**: Collects structured JSON application logs emitted by the Gunicorn application container.
- **Key Settings**:
  - `LogGroupName: /cloudnotes/{ProjectName}`
  - `RetentionInDays: 14`: Retains logs for 14 days and automatically expires older entries to keep storage costs minimal.

### 7. IAM Role and Instance Profile (`AppInstanceRole`, `AppInstanceProfile`)
- **What it is**: Identity and Access Management credentials attached directly to EC2 instances via an Instance Profile.
- **Why it exists**: Allows EC2 instances to interact securely with AWS services without hard-coding AWS access keys or secret keys in files or environment variables.
- **Least-Privilege Policy Actions**:
  - **S3**: `s3:ListBucket` and `s3:GetBucketLocation` on the bucket ARN; `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` scoped specifically to `arn:aws:s3:::{bucket}/*`.
  - **Secrets Manager**: `secretsmanager:GetSecretValue` scoped strictly to `AppSecret` ARN and `DBInstance.MasterUserSecret.SecretArn`.
  - **ECR**: `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, and `ecr:BatchGetImage` scoped strictly to the ECR repository ARN; `ecr:GetAuthorizationToken` on `*` (required by AWS API as it does not support resource-level permissions).
  - **CloudWatch Logs**: `logs:CreateLogStream`, `logs:PutLogEvents`, and `logs:DescribeLogStreams` scoped strictly to the log group ARN.
  - **Status Page Read-Only**: `autoscaling:DescribeAutoScalingGroups`, `cloudwatch:GetMetricStatistics`, and `rds:DescribeDBInstances` on `*` (used by `/api/status` to query server count, CPU, and backup timestamps without modifying any resources).

---

## Stack Outputs

The template exports outputs so that compute and routing resources in subsequent stages can reference them:
- `EcrRepositoryUri`: ECR repository endpoint for docker push.
- `S3BucketName` / `S3BucketArn`: Storage bucket identifier and ARN.
- `AppSecretArn`: Secrets Manager ARN for application secret key.
- `DbSecretArn`: Secrets Manager ARN for database credentials.
- `DbEndpointAddress` / `DbEndpointPort`: RDS MySQL host and port.
- `AlbSecurityGroupId` / `AppSecurityGroupId` / `DbSecurityGroupId`: Security group IDs.
- `LogGroupName` / `LogGroupArn`: Application log group details.
- `InstanceProfileArn` / `InstanceProfileName`: IAM instance profile attached to EC2 instances.

---

## Validation Instructions

To validate the CloudFormation template syntax and declaration using the AWS CLI:

```bash
aws cloudformation validate-template \
  --template-body file://infra/stack.yaml \
  --region ap-south-1
```

If `cfn-lint` is installed on your workstation, you can also run:

```bash
cfn-lint infra/stack.yaml
```

---

## Teardown & Manual Cleanup

When the CloudFormation stack is deleted:
1. **ECR Repository**: Automatically deleted because `EmptyOnDelete: true` is configured.
2. **RDS Database**: Automatically deleted without creating a final snapshot because `DeletionPolicy: Delete` is configured.
3. **Secrets Manager & Log Group**: Automatically deleted because `DeletionPolicy: Delete` is configured.
4. **S3 Bucket (`NotesBucket`)**:
   - Because `DeletionPolicy: Retain` is set, CloudFormation does **not** delete the bucket automatically if it contains objects.
   - To clean up the S3 bucket completely:
     ```bash
     # List objects and versions
     aws s3 ls s3://<S3BucketName> --recursive

     # Empty all objects and object versions
     aws s3 rm s3://<S3BucketName> --recursive

     # If versioning created delete markers or versions:
     # Delete the bucket after emptying:
     aws s3 rb s3://<S3BucketName> --force
     ```
