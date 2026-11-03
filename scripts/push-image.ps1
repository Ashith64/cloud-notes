#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and push the Cloud Notes Docker image to AWS ECR.

.DESCRIPTION
    This script builds the production Docker image for Cloud Notes (linux/amd64),
    tags it with the current short Git commit hash and 'latest', then pushes both
    tags to the project ECR repository in AWS region ap-southeast-2.

.PARAMETER StackName
    Name of the deployed CloudFormation stack (optional, used to resolve repository output if present).
    Default: cloudnotes-app

.PARAMETER RepoName
    ECR repository name if stack output is not used. Default: cloudnotes

.PARAMETER Region
    AWS region. Default: ap-southeast-2

.EXAMPLE
    .\scripts\push-image.ps1
    .\scripts\push-image.ps1 -Region ap-southeast-2
#>
[CmdletBinding()]
param(
    [string]$StackName = "cloudnotes-app",
    [string]$RepoName = "cloudnotes",
    [string]$Region = "ap-southeast-2"
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
# 2. Verify AWS credentials and get account ID dynamically
# ---------------------------------------------------------------------------
Write-Host "`n[2/6] Verifying AWS credentials and resolving account ID..." -ForegroundColor Cyan
Write-Host "  Running: aws sts get-caller-identity --region $Region --query Account --output text"
try {
    $ACCOUNT_ID = (aws sts get-caller-identity --region $Region --query Account --output text 2>&1).Trim()
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
# 3. Resolve ECR repository URI
# ---------------------------------------------------------------------------
Write-Host "`n[3/6] Resolving ECR repository URI..." -ForegroundColor Cyan

$ECR_REPO_URI = $null
if (-not [string]::IsNullOrWhiteSpace($StackName)) {
    Write-Host "  Attempting stack resolution from '$StackName'..."
    Write-Host "  Running: aws cloudformation describe-stacks --stack-name $StackName --region $Region ..."
    $stackOutput = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri' || OutputKey=='RepositoryUri'].OutputValue" `
        --output text 2>&1
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($stackOutput) -and $stackOutput -ne "None") {
        $ECR_REPO_URI = $stackOutput.Trim().Split()[0]
    }
}

if ([string]::IsNullOrWhiteSpace($ECR_REPO_URI)) {
    # Default direct repository URI from dynamic account ID and region
    $ECR_REPO_URI = "${ACCOUNT_ID}.dkr.ecr.${Region}.amazonaws.com/${RepoName}"
}

Write-Host "  [OK] ECR repository URI: $ECR_REPO_URI"

# ---------------------------------------------------------------------------
# 4. Get the current short Git commit hash for the image tag
# ---------------------------------------------------------------------------
Write-Host "`n[4/6] Resolving image tag from Git..." -ForegroundColor Cyan
Write-Host "  Running: git rev-parse --short HEAD"
$GIT_TAG = (git rev-parse --short HEAD 2>&1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($GIT_TAG)) {
    Write-Error "Could not read current Git commit hash. Ensure you are inside a Git repository."
    exit 1
}
Write-Host "  [OK] Git short commit: $GIT_TAG"

$IMAGE_TAG_COMMIT = "${ECR_REPO_URI}:${GIT_TAG}"
$IMAGE_TAG_LATEST = "${ECR_REPO_URI}:latest"

# ---------------------------------------------------------------------------
# 5. Authenticate Docker to ECR using aws ecr get-login-password
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
    # Clear variable so the token is not retained in memory
    Remove-Variable -Name loginPassword -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 6. Build, tag, and push — two tags: short commit hash and 'latest'
# ---------------------------------------------------------------------------
Write-Host "`n[6/6] Building and pushing image..." -ForegroundColor Cyan

# Change to project root so Dockerfile COPY paths resolve correctly
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
Write-Host "  Image tag (commit) : $GIT_TAG"
Write-Host "  Image tag (latest) : latest"
Write-Host "  Commit-tagged URI  : $IMAGE_TAG_COMMIT"
Write-Host "  Latest-tagged URI  : $IMAGE_TAG_LATEST"
Write-Host ""
Write-Host "To verify, run:"
Write-Host "  aws ecr describe-images --repository-name $RepoName --region $Region"
