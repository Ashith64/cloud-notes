#!/usr/bin/env bash
# push-image.sh — Build and push the Cloud Notes Docker image to AWS ECR.
#
# Usage:
#   ./scripts/push-image.sh [--stack-name cloudnotes-app] [--region ap-south-1]
#
# PREREQUISITE: The CloudFormation stack (infra/stack.yaml) MUST be deployed
# before this script is run. The ECR repository is created by that stack.
# Run:
#   aws cloudformation deploy --template-file infra/stack.yaml \
#       --stack-name cloudnotes-app --capabilities CAPABILITY_IAM \
#       --region ap-south-1 \
#       --parameter-overrides VpcId=<vpc-id> SubnetIds=<sub1>,<sub2> \
#           AlertEmail=<email> DesiredCapacity=1 MinCapacity=1
#
# Secrets are managed entirely by CloudFormation (AppSecret) and RDS
# (ManageMasterUserPassword). No SSM parameters need to be created separately.
#
set -euo pipefail

STACK_NAME="cloudnotes-app"
REGION="ap-south-1"

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stack-name) STACK_NAME="$2"; shift 2 ;;
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
# 2. Verify AWS credentials (without revealing them)
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[2/6] Verifying AWS credentials...${reset}"
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
# 3. Resolve ECR repository URI from the deployed CloudFormation stack
# ---------------------------------------------------------------------------
echo -e "\n${cyan}[3/6] Resolving ECR repository URI from CloudFormation stack '${STACK_NAME}'...${reset}"
echo "  Running: aws cloudformation describe-stacks --stack-name ${STACK_NAME} ..."

ECR_REPO_URI=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" \
    --output text 2>&1) || {
    echo "ERROR: Could not query CloudFormation stack '${STACK_NAME}'." >&2
    echo "       Ensure the stack is deployed before running this script." >&2
    exit 1
}

if [[ -z "$ECR_REPO_URI" || "$ECR_REPO_URI" == "None" ]]; then
    cat >&2 <<EOF

ERROR: ECR repository URI not found in stack '${STACK_NAME}' outputs.
Deploy the CloudFormation stack first:
  aws cloudformation deploy \\
      --template-file infra/stack.yaml \\
      --stack-name ${STACK_NAME} \\
      --capabilities CAPABILITY_IAM \\
      --region ${REGION} \\
      --parameter-overrides VpcId=<vpc-id> SubnetIds=<sub1>,<sub2> \\
          AlertEmail=<email> DesiredCapacity=1 MinCapacity=1
EOF
    exit 1
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
# 5. Authenticate Docker to ECR (credential piped, never printed)
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
# Navigate to project root so Dockerfile COPY paths resolve correctly
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
echo "  Commit-tagged : ${IMAGE_TAG_COMMIT}"
echo "  Latest-tagged : ${IMAGE_TAG_LATEST}"
echo ""
echo "To verify, run:"
echo "  aws ecr describe-images --repository-name cloudnotes-repo --region ${REGION}"
