#!/usr/bin/env bash
# push-image.sh — Build and push the Cloud Notes Docker image to AWS ECR.
#
# Usage:
#   ./scripts/push-image.sh [--stack-name cloudnotes-app] [--repo-name cloudnotes] [--region ap-southeast-2]
#
set -euo pipefail

STACK_NAME="cloudnotes-app"
REPO_NAME="cloudnotes"
REGION="ap-southeast-2"

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stack-name) STACK_NAME="$2"; shift 2 ;;
        --repo-name)  REPO_NAME="$2";  shift 2 ;;
        --region)     REGION="$2";     shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Colour helpers (degrade gracefully when not a tty)
cyan=""  green=""  reset=""
if [[ -t 1 ]]; then cyan="\033[0;36m"; green="\033[0;32m"; reset="\033[0m"; fi

# ---------------------------------------------------------------------------
# 1. Prerequisite checks
# ---------------------------------------------------------------------------
echo -e "${cyan}[1/6] Checking prerequisites...${reset}"

check_command() {
    local cmd="$1" hint="$2"
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' is not installed or not in PATH." >&2
        echo "       $hint" >&2
        exit 1
    fi
    echo "  [OK] $cmd found: $(command -v "$cmd")"
}

check_command git    "Install Git from https://git-scm.com/"
check_command docker "Install Docker from https://docs.docker.com/get-docker/"
check_command aws    "Install AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"

# ---------------------------------------------------------------------------
# 2. Verify AWS credentials and get account ID dynamically
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[2/6] Verifying AWS credentials and resolving account ID...${reset}"
echo "  Running: aws sts get-caller-identity --region ${REGION} --query Account --output text"

ACCOUNT_ID=$(aws sts get-caller-identity --region "${REGION}" --query Account --output text 2>&1) || {
    echo "ERROR: AWS credentials are not configured or are invalid." >&2
    echo "       Run 'aws configure' or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY." >&2
    exit 1
}

if ! [[ "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    echo "ERROR: Unexpected account ID format: $ACCOUNT_ID" >&2
    exit 1
fi
echo "  [OK] Authenticated to account: ${ACCOUNT_ID} (region: ${REGION})"

# ---------------------------------------------------------------------------
# 3. Resolve ECR repository URI
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[3/6] Resolving ECR repository URI...${reset}"

ECR_REPO_URI=""
if [[ -n "${STACK_NAME}" ]]; then
    echo "  Attempting stack resolution from '${STACK_NAME}'..."
    echo "  Running: aws cloudformation describe-stacks --stack-name ${STACK_NAME} ..."
    STACK_OUTPUT=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri' || OutputKey=='RepositoryUri'].OutputValue" \
        --output text 2>/dev/null || true)
    if [[ -n "${STACK_OUTPUT}" && "${STACK_OUTPUT}" != "None" ]]; then
        ECR_REPO_URI=$(echo "${STACK_OUTPUT}" | awk '{print $1}')
    fi
fi

if [[ -z "${ECR_REPO_URI}" ]]; then
    ECR_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
fi

echo "  [OK] ECR repository URI: ${ECR_REPO_URI}"

# ---------------------------------------------------------------------------
# 4. Get the current short Git commit hash
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[4/6] Resolving image tag from Git...${reset}"
echo "  Running: git rev-parse --short HEAD"
GIT_TAG=$(git rev-parse --short HEAD)
echo "  [OK] Git short commit: ${GIT_TAG}"

IMAGE_TAG_COMMIT="${ECR_REPO_URI}:${GIT_TAG}"
IMAGE_TAG_LATEST="${ECR_REPO_URI}:latest"

# ---------------------------------------------------------------------------
# 5. Authenticate Docker to ECR using aws ecr get-login-password
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[5/6] Authenticating Docker to ECR...${reset}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
echo "  Running: aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
echo "  [OK] Docker authenticated to ${ECR_REGISTRY}"

# ---------------------------------------------------------------------------
# 6. Build, tag, and push — commit hash tag and 'latest'
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[6/6] Building and pushing image...${reset}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
cd "${PROJECT_ROOT}"

echo "  Running: docker build --platform linux/amd64 -t ${IMAGE_TAG_COMMIT} -t ${IMAGE_TAG_LATEST} ."
docker build --platform linux/amd64 -t "${IMAGE_TAG_COMMIT}" -t "${IMAGE_TAG_LATEST}" .

echo "  Running: docker push ${IMAGE_TAG_COMMIT}"
docker push "${IMAGE_TAG_COMMIT}"

echo "  Running: docker push ${IMAGE_TAG_LATEST}"
docker push "${IMAGE_TAG_LATEST}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo -e "\n${green}[DONE] Image pushed successfully.${reset}"
echo "  Image tag (commit) : ${GIT_TAG}"
echo "  Image tag (latest) : latest"
echo "  Commit-tagged URI  : ${IMAGE_TAG_COMMIT}"
echo "  Latest-tagged URI  : ${IMAGE_TAG_LATEST}"
echo ""
echo "To verify, run:"
echo "  aws ecr describe-images --repository-name ${REPO_NAME} --region ${REGION}"
