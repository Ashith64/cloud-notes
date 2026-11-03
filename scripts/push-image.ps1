#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and push the Cloud Notes Docker image to AWS ECR.

.DESCRIPTION
    This script builds the production Docker image for Cloud Notes (linux/amd64),
    tags it with the current short Git commit hash and 'latest', then pushes both
    tags to the project ECR repository.

    PREREQUISITE: The CloudFormation stack (infra/stack.yaml) MUST be deployed
    before this script is run. The ECR repository is created by that stack.
    Run:
        aws cloudformation deploy --template-file infra/stack.yaml \
            --stack-name cloudnotes-app --capabilities CAPABILITY_IAM \
            --region ap-south-1 ...

    Secrets are managed entirely by CloudFormation (AppSecret) and RDS
    (ManageMasterUserPassword). No SSM secrets need to be created separately.

.PARAMETER StackName
    Name of the deployed CloudFormation stack. Default: cloudnotes-app

.PARAMETER Region
    AWS region. Default: ap-south-1

.EXAMPLE
    .\scripts\push-image.ps1
    .\scripts\push-image.ps1 -StackName cloudnotes-app -Region ap-south-1
#>
[CmdletBinding()]
param(
    [string]$StackName = "cloudnotes-app",
    [string]$Region = "ap-south-1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# 1. Prerequisite checks — fail clearly rather than mislead
# ---------------------------------------------------------------------------
Write-Host "`n[1/6] Checking prerequisites..." -ForegroundColor Cyan

function Assert-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name is not installed or not in PATH. $Hint"
        exit 1
    }
    Write-Host "  [OK] $Name found: $((Get-Command $Name).Source)"
}

Assert-Command "git"    "Install Git from https://git-scm.com/"
Assert-Command "docker" "Install Docker Desktop from https://docs.docker.com/get-docker/"
Assert-Command "aws"    "Install AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"

# ---------------------------------------------------------------------------
# 2. Verify AWS credentials are configured (without revealing them)
# ---------------------------------------------------------------------------
Write-Host "`n[2/6] Verifying AWS credentials..." -ForegroundColor Cyan
Write-Host "  Running: aws sts get-caller-identity --region $Region --query Account --output text"
try {
    $ACCOUNT_ID = aws sts get-caller-identity --region $Region --query Account --output text 2>&1
    if ($LASTEXITCODE -ne 0 -or -not ($ACCOUNT_ID -match '^\d{12}$')) {
        Write-Error "AWS credentials are not configured or are invalid. Run 'aws configure' or set environment variables."
        exit 1
    }
    Write-Host "  [OK] Authenticated to account: $ACCOUNT_ID (region: $Region)"
} catch {
    Write-Error "Failed to verify AWS credentials: $_"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Resolve ECR repository URI from the deployed CloudFormation stack
# ---------------------------------------------------------------------------
Write-Host "`n[3/6] Resolving ECR repository URI from CloudFormation stack '$StackName'..." -ForegroundColor Cyan
Write-Host "  Running: aws cloudformation describe-stacks --stack-name $StackName --region $Region ..."

try {
    $ECR_REPO_URI = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" `
        --output text 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ECR_REPO_URI) -or $ECR_REPO_URI -eq "None") {
        Write-Error @"
Could not resolve ECR repository URI from stack '$StackName'.
Make sure the CloudFormation stack is deployed first:
  aws cloudformation deploy ``
      --template-file infra/stack.yaml ``
      --stack-name $StackName ``
      --capabilities CAPABILITY_IAM ``
      --region $Region ``
      --parameter-overrides VpcId=<vpc-id> SubnetIds=<sub1>,<sub2> AlertEmail=<email> DesiredCapacity=1 MinCapacity=1
"@
        exit 1
    }
    Write-Host "  [OK] ECR repository URI: $ECR_REPO_URI"
} catch {
    Write-Error "Failed to query CloudFormation stack: $_"
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Get the current short Git commit hash for the image tag
# ---------------------------------------------------------------------------
Write-Host "`n[4/6] Resolving image tag from Git..." -ForegroundColor Cyan
Write-Host "  Running: git rev-parse --short HEAD"
$GIT_TAG = git rev-parse --short HEAD
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($GIT_TAG)) {
    Write-Error "Could not read current Git commit hash. Ensure you are inside a Git repository."
    exit 1
}
Write-Host "  [OK] Git short commit: $GIT_TAG"

$IMAGE_TAG_COMMIT = "${ECR_REPO_URI}:${GIT_TAG}"
$IMAGE_TAG_LATEST = "${ECR_REPO_URI}:latest"

# ---------------------------------------------------------------------------
# 5. Authenticate Docker to ECR using the instance / CLI role (no static creds)
# ---------------------------------------------------------------------------
Write-Host "`n[5/6] Authenticating Docker to ECR..." -ForegroundColor Cyan
$ECR_REGISTRY = "${ACCOUNT_ID}.dkr.ecr.${Region}.amazonaws.com"
Write-Host "  Running: aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $ECR_REGISTRY"
try {
    $loginPassword = aws ecr get-login-password --region $Region
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to obtain ECR login token from AWS."
        exit 1
    }
    # Pipe password to docker login — password is never printed
    $loginPassword | docker login --username AWS --password-stdin $ECR_REGISTRY
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker login to ECR failed."
        exit 1
    }
    Write-Host "  [OK] Docker authenticated to $ECR_REGISTRY"
} catch {
    Write-Error "ECR authentication failed: $_"
    exit 1
} finally {
    # Clear variable so the token is not retained in memory any longer than needed
    Remove-Variable -Name loginPassword -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 6. Build, tag and push — two tags: short commit hash and 'latest'
# ---------------------------------------------------------------------------
Write-Host "`n[6/6] Building and pushing image..." -ForegroundColor Cyan

# Change to project root so the Dockerfile COPY paths resolve correctly
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
Push-Location $PROJECT_ROOT

try {
    Write-Host "  Running: docker build --platform linux/amd64 -t $IMAGE_TAG_COMMIT -t $IMAGE_TAG_LATEST ."
    docker build --platform linux/amd64 -t $IMAGE_TAG_COMMIT -t $IMAGE_TAG_LATEST .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed."
        exit 1
    }

    Write-Host "  Running: docker push $IMAGE_TAG_COMMIT"
    docker push $IMAGE_TAG_COMMIT
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker push (commit tag) failed."; exit 1 }

    Write-Host "  Running: docker push $IMAGE_TAG_LATEST"
    docker push $IMAGE_TAG_LATEST
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker push (latest tag) failed."; exit 1 }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host "`n[DONE] Image pushed successfully." -ForegroundColor Green
Write-Host "  Commit-tagged : $IMAGE_TAG_COMMIT"
Write-Host "  Latest-tagged : $IMAGE_TAG_LATEST"
Write-Host ""
Write-Host "To verify, run:"
Write-Host "  aws ecr describe-images --repository-name cloudnotes-repo --region $Region"
