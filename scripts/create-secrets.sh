#!/usr/bin/env bash
# create-secrets.sh — Generate and store production secrets in AWS SSM Parameter Store.
#
# Usage:
#   ./scripts/create-secrets.sh [--region ap-southeast-2]
#
# Generates a 24-character DB password and a 48-character JWT secret locally,
# and stores them as SecureString parameters in AWS Systems Manager:
#   - /cloudnotes/db-password
#   - /cloudnotes/jwt-secret
#
# Security:
#   - Secrets are generated locally using /dev/urandom.
#   - Secrets are never echoed, printed to console, or written to disk.
#   - Existence checks use 'aws ssm describe-parameters' to retrieve metadata only,
#     never parameter values.
#   - Parameters that already exist are safely skipped.
#
set -euo pipefail

REGION="ap-southeast-2"
DB_PARAM_NAME="/cloudnotes/db-password"
JWT_PARAM_NAME="/cloudnotes/jwt-secret"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --region) REGION="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Colour helpers (degrade gracefully when not a tty)
cyan=""  green=""  yellow=""  reset=""
if [[ -t 1 ]]; then cyan="\033[0;36m"; green="\033[0;32m"; yellow="\033[0;33m"; reset="\033[0m"; fi

# ---------------------------------------------------------------------------
# Helper: Generate cryptographically secure random alphanumeric string
# ---------------------------------------------------------------------------
generate_alphanumeric() {
    local length="$1"
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
}

# ---------------------------------------------------------------------------
# 1. Prerequisite checks
# ---------------------------------------------------------------------------
echo -e "${cyan}[1/3] Checking prerequisites...${reset}"
if ! command -v aws &>/dev/null; then
    echo "ERROR: 'aws' CLI is not installed or not in PATH." >&2
    echo "       Install AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html" >&2
    exit 1
fi
echo "  [OK] aws found: $(command -v aws)"

# ---------------------------------------------------------------------------
# 2. Verify AWS credentials (without revealing them)
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[2/3] Verifying AWS credentials...${reset}"
echo "  Running: aws sts get-caller-identity --region ${REGION} --query Account --output text"

ACCOUNT_ID=$(aws sts get-caller-identity --region "${REGION}" --query Account --output text 2>&1) || {
    echo "ERROR: AWS credentials are not configured or are invalid." >&2
    echo "       Run 'aws configure' or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY." >&2
    exit 1
}

ACCOUNT_ID="$(echo "${ACCOUNT_ID}" | tr -d '[:space:]')"

if ! [[ "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    echo "ERROR: Unexpected account ID format: $ACCOUNT_ID" >&2
    exit 1
fi
echo "  [OK] Authenticated to account: ${ACCOUNT_ID} (region: ${REGION})"

# ---------------------------------------------------------------------------
# 3. Store secrets in AWS SSM Parameter Store
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[3/3] Checking and creating SSM SecureString parameters in ${REGION}...${reset}"

# Store DB password (24 characters) if not already existing
echo "  Checking if parameter '${DB_PARAM_NAME}' exists via describe-parameters..."
EXISTING_DB=$(aws ssm describe-parameters \
    --parameter-filters "Key=Name,Option=Equals,Values=${DB_PARAM_NAME}" \
    --region "${REGION}" \
    --query "Parameters[0].Name" \
    --output text 2>/dev/null || true)
EXISTING_DB="$(echo "${EXISTING_DB}" | tr -d '[:space:]')"

if [[ "${EXISTING_DB}" == "${DB_PARAM_NAME}" ]]; then
    echo -e "  ${yellow}[SKIP] Parameter '${DB_PARAM_NAME}' already exists in SSM (${REGION}). Skipping.${reset}"
else
    echo "  Parameter '${DB_PARAM_NAME}' not found. Generating 24-character random secret..."
    DB_PASSWORD=$(generate_alphanumeric 24)
    echo "  Running: aws ssm put-parameter --name ${DB_PARAM_NAME} --value [REDACTED] --type SecureString --region ${REGION}"
    aws ssm put-parameter \
        --name "${DB_PARAM_NAME}" \
        --value "${DB_PASSWORD}" \
        --type SecureString \
        --description "Cloud Notes database master password" \
        --region "${REGION}" >/dev/null
    unset DB_PASSWORD
    echo -e "  ${green}[OK] Parameter '${DB_PARAM_NAME}' created successfully as SecureString.${reset}"
fi

# Store JWT secret (48 characters) if not already existing
echo "  Checking if parameter '${JWT_PARAM_NAME}' exists via describe-parameters..."
EXISTING_JWT=$(aws ssm describe-parameters \
    --parameter-filters "Key=Name,Option=Equals,Values=${JWT_PARAM_NAME}" \
    --region "${REGION}" \
    --query "Parameters[0].Name" \
    --output text 2>/dev/null || true)
EXISTING_JWT="$(echo "${EXISTING_JWT}" | tr -d '[:space:]')"

if [[ "${EXISTING_JWT}" == "${JWT_PARAM_NAME}" ]]; then
    echo -e "  ${yellow}[SKIP] Parameter '${JWT_PARAM_NAME}' already exists in SSM (${REGION}). Skipping.${reset}"
else
    echo "  Parameter '${JWT_PARAM_NAME}' not found. Generating 48-character random secret..."
    JWT_SECRET=$(generate_alphanumeric 48)
    echo "  Running: aws ssm put-parameter --name ${JWT_PARAM_NAME} --value [REDACTED] --type SecureString --region ${REGION}"
    aws ssm put-parameter \
        --name "${JWT_PARAM_NAME}" \
        --value "${JWT_SECRET}" \
        --type SecureString \
        --description "Cloud Notes JWT secret key" \
        --region "${REGION}" >/dev/null
    unset JWT_SECRET
    echo -e "  ${green}[OK] Parameter '${JWT_PARAM_NAME}' created successfully as SecureString.${reset}"
fi

echo -e "\n${green}[DONE] Secret setup complete in region ${REGION}.${reset}"
echo "  - ${DB_PARAM_NAME} (SecureString)"
echo "  - ${JWT_PARAM_NAME} (SecureString)"
