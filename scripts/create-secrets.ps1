#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Generate and store production secrets in AWS Systems Manager (SSM) Parameter Store.

.DESCRIPTION
    This script generates a random 24-character alphanumeric database password and
    a random 48-character alphanumeric JWT secret locally, and stores them as
    SecureString parameters in AWS Systems Manager (SSM) Parameter Store:
      - /cloudnotes/db-password
      - /cloudnotes/jwt-secret

    Security:
      - Secrets are generated locally using cryptographically secure random bytes.
      - Secrets are never echoed, printed to console, or written to disk.
      - Secrets are passed securely to the AWS CLI.
      - If a parameter already exists, it is safely skipped (not overwritten).

.PARAMETER Region
    AWS region. Default: ap-southeast-2

.PARAMETER DbParamName
    SSM parameter name for the database password. Default: /cloudnotes/db-password

.PARAMETER JwtParamName
    SSM parameter name for the JWT secret key. Default: /cloudnotes/jwt-secret

.EXAMPLE
    .\scripts\create-secrets.ps1
    .\scripts\create-secrets.ps1 -Region ap-southeast-2
#>
[CmdletBinding()]
param(
    [string]$Region = "ap-southeast-2",
    [string]$DbParamName = "/cloudnotes/db-password",
    [string]$JwtParamName = "/cloudnotes/jwt-secret"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helper: Generate cryptographically secure random alphanumeric string
# ---------------------------------------------------------------------------
function New-RandomAlphanumeric {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789".ToCharArray()
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        $result = New-Object char[] $Length
        for ($i = 0; $i -lt $Length; $i++) {
            $result[$i] = $chars[$bytes[$i] % $chars.Length]
        }
        return -join $result
    } finally {
        $rng.Dispose()
    }
}

# ---------------------------------------------------------------------------
# 1. Prerequisite checks
# ---------------------------------------------------------------------------
Write-Host "`n[1/3] Checking prerequisites..." -ForegroundColor Cyan

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Error "AWS CLI is not installed or not in PATH. Install AWS CLI v2."
    exit 1
}
Write-Host "  [OK] AWS CLI found: $((Get-Command aws).Source)"

# ---------------------------------------------------------------------------
# 2. Verify AWS credentials without revealing sensitive data
# ---------------------------------------------------------------------------
Write-Host "`n[2/3] Verifying AWS credentials..." -ForegroundColor Cyan
Write-Host "  Running: aws sts get-caller-identity --region $Region --query Account --output text"

try {
    $ACCOUNT_ID = aws sts get-caller-identity --region $Region --query Account --output text 2>&1
    if ($LASTEXITCODE -ne 0 -or -not ($ACCOUNT_ID -match '^\d{12}$')) {
        Write-Error "AWS credentials are not configured or are invalid. Run 'aws configure' or check credentials."
        exit 1
    }
    Write-Host "  [OK] Authenticated to account: $ACCOUNT_ID (region: $Region)"
} catch {
    Write-Error "Failed to verify AWS credentials: $_"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Store secrets in AWS SSM Parameter Store
# ---------------------------------------------------------------------------
Write-Host "`n[3/3] Checking and creating SSM SecureString parameters in $Region..." -ForegroundColor Cyan

function Set-SsmSecretParameter {
    param(
        [string]$ParamName,
        [int]$SecretLength,
        [string]$Description
    )

    # Check if parameter already exists
    Write-Host "  Checking if parameter '$ParamName' exists..."
    $null = aws ssm get-parameter --name $ParamName --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [SKIP] Parameter '$ParamName' already exists in SSM ($Region). Skipping." -ForegroundColor Yellow
        return
    }

    Write-Host "  Parameter '$ParamName' not found. Generating $SecretLength-character random secret..."
    $secretValue = New-RandomAlphanumeric -Length $SecretLength

    try {
        # Put parameter as SecureString without ever printing or writing the secret to disk
        Write-Host "  Running: aws ssm put-parameter --name $ParamName --value [REDACTED] --type SecureString --region $Region"
        $null = aws ssm put-parameter `
            --name $ParamName `
            --value $secretValue `
            --type SecureString `
            --description $Description `
            --region $Region 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create SSM parameter '$ParamName'."
            exit 1
        }
        Write-Host "  [OK] Parameter '$ParamName' created successfully as SecureString." -ForegroundColor Green
    } finally {
        # Explicitly remove secret value from memory
        Remove-Variable -Name secretValue -ErrorAction SilentlyContinue
    }
}

# Database password: 24 characters
Set-SsmSecretParameter `
    -ParamName $DbParamName `
    -SecretLength 24 `
    -Description "Cloud Notes database master password"

# JWT secret: 48 characters
Set-SsmSecretParameter `
    -ParamName $JwtParamName `
    -SecretLength 48 `
    -Description "Cloud Notes JWT secret key"

Write-Host "`n[DONE] Secret setup complete in region $Region." -ForegroundColor Green
Write-Host "  - $DbParamName (SecureString)"
Write-Host "  - $JwtParamName (SecureString)"
