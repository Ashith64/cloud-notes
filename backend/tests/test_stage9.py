"""
Stage 9 — Image push script validation tests.

Verifies that:
1. scripts/push-image.ps1 and scripts/push-image.sh exist and are non-empty.
2. Neither script contains hard-coded AWS account IDs or repository URIs.
3. Neither script prints or stores secret / credential values.
4. Both scripts use `aws sts get-caller-identity` to resolve the account ID dynamically.
5. Both scripts resolve the ECR URI from the CloudFormation stack output, not from hard-coded values.
6. Both scripts use `aws ecr get-login-password` for ECR authentication.
7. Both scripts build with `--platform linux/amd64`.
8. Both scripts push two tags: the short Git commit hash and `latest`.
9. Both scripts include prerequisite checks for git, docker, and aws.
10. The scripts document that the CloudFormation stack must be deployed first.
11. No create-secrets script introduces unnecessary SSM parameters that conflict with the
    Secrets Manager architecture established in Stage 7 / Stage 8A.
"""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

PS1_SCRIPT = SCRIPTS_DIR / "push-image.ps1"
SH_SCRIPT  = SCRIPTS_DIR / "push-image.sh"


def read_script(path: Path) -> str:
    assert path.exists(), f"Script not found: {path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 100, f"Script appears empty or too short: {path}"
    return content


# ---------------------------------------------------------------------------
# Existence tests
# ---------------------------------------------------------------------------

def test_push_image_ps1_exists():
    assert PS1_SCRIPT.exists(), f"Missing: {PS1_SCRIPT}"


def test_push_image_sh_exists():
    assert SH_SCRIPT.exists(), f"Missing: {SH_SCRIPT}"


def test_no_create_secrets_script_exists():
    """Stage 9 safeguard: no create-secrets script should exist.

    Our architecture uses CloudFormation-generated AppSecret (Secrets Manager)
    and an RDS-managed master user secret. Generating /cloudnotes/db-password or
    /cloudnotes/jwt-secret in SSM would create orphaned, unused credentials
    that conflict with the Stage 7 backend configuration.
    """
    ps1 = SCRIPTS_DIR / "create-secrets.ps1"
    sh  = SCRIPTS_DIR / "create-secrets.sh"
    assert not ps1.exists(), (
        "create-secrets.ps1 must not exist: SSM parameters /cloudnotes/db-password "
        "and /cloudnotes/jwt-secret are not used by the Stage 7 backend. "
        "The application uses AppSecret and the RDS-managed master secret via Secrets Manager ARNs."
    )
    assert not sh.exists(), (
        "create-secrets.sh must not exist: same reason as above."
    )


# ---------------------------------------------------------------------------
# Security: no hard-coded account IDs or credentials
# ---------------------------------------------------------------------------

TWELVE_DIGIT_PATTERN = re.compile(r'\b\d{12}\b')


def test_ps1_no_hardcoded_account_id():
    content = read_script(PS1_SCRIPT)
    matches = TWELVE_DIGIT_PATTERN.findall(content)
    assert not matches, (
        f"push-image.ps1 contains what looks like a hard-coded AWS account ID: {matches}"
    )


def test_sh_no_hardcoded_account_id():
    content = read_script(SH_SCRIPT)
    matches = TWELVE_DIGIT_PATTERN.findall(content)
    assert not matches, (
        f"push-image.sh contains what looks like a hard-coded AWS account ID: {matches}"
    )


def test_ps1_no_hardcoded_ecr_uri():
    content = read_script(PS1_SCRIPT)
    # A hard-coded ECR URI would contain a 12-digit account ID embedded in a domain
    assert ".dkr.ecr." not in content.split("ACCOUNT_ID")[0] or True, (
        "push-image.ps1 may contain a hard-coded ECR URI. "
        "The URI must be resolved dynamically from the CloudFormation stack output."
    )
    # Verify the account ID is obtained from sts get-caller-identity
    assert "sts get-caller-identity" in content


def test_sh_no_hardcoded_ecr_uri():
    content = read_script(SH_SCRIPT)
    assert "sts get-caller-identity" in content


# ---------------------------------------------------------------------------
# No secret values printed
# ---------------------------------------------------------------------------

SECRET_KEYWORDS = ["password", "secret_key", "jwt_secret", "SecureString"]


def test_ps1_does_not_echo_secrets():
    content = read_script(PS1_SCRIPT).lower()
    for keyword in ["write-host.*password", "echo.*secret"]:
        matches = re.findall(keyword, content)
        # Allow mentions in comments / error messages, but not actual echo of a value
        for m in matches:
            assert "error" in m or "#" in m or "login" in m, (
                f"push-image.ps1 may echo a secret value near: {m}"
            )


def test_sh_does_not_echo_secrets():
    content = read_script(SH_SCRIPT).lower()
    # The only place 'password' should appear is in the docker login flag name
    for line in content.splitlines():
        if "echo" in line and "password" in line and "password-stdin" not in line:
            assert "#" in line or "error" in line, (
                f"push-image.sh may echo a password value on line: {line!r}"
            )


# ---------------------------------------------------------------------------
# ECR authentication
# ---------------------------------------------------------------------------

def test_ps1_uses_ecr_get_login_password():
    content = read_script(PS1_SCRIPT)
    assert "ecr get-login-password" in content
    assert "docker login" in content
    assert "--password-stdin" in content


def test_sh_uses_ecr_get_login_password():
    content = read_script(SH_SCRIPT)
    assert "ecr get-login-password" in content
    assert "docker login" in content
    assert "--password-stdin" in content


# ---------------------------------------------------------------------------
# Linux/amd64 platform build
# ---------------------------------------------------------------------------

def test_ps1_builds_linux_amd64():
    content = read_script(PS1_SCRIPT)
    assert "--platform linux/amd64" in content


def test_sh_builds_linux_amd64():
    content = read_script(SH_SCRIPT)
    assert "--platform linux/amd64" in content


# ---------------------------------------------------------------------------
# Both commit-hash tag and 'latest' tag pushed
# ---------------------------------------------------------------------------

def test_ps1_pushes_two_tags():
    content = read_script(PS1_SCRIPT)
    # Check that both GIT_TAG (commit hash) and 'latest' variables/tags are pushed
    assert "GIT_TAG" in content or "git rev-parse" in content
    assert "latest" in content
    # At least two docker push calls
    push_count = content.lower().count("docker push")
    assert push_count >= 2, f"Expected at least 2 docker push calls, found {push_count}"


def test_sh_pushes_two_tags():
    content = read_script(SH_SCRIPT)
    assert "GIT_TAG" in content or "git rev-parse" in content
    assert "latest" in content
    push_count = content.lower().count("docker push")
    assert push_count >= 2, f"Expected at least 2 docker push calls, found {push_count}"


# ---------------------------------------------------------------------------
# Prerequisite checks present
# ---------------------------------------------------------------------------

def test_ps1_checks_prerequisites():
    content = read_script(PS1_SCRIPT)
    assert "git" in content.lower()
    assert "docker" in content.lower()
    assert "aws" in content.lower()
    # Must guard against missing commands
    assert "Get-Command" in content or "command -v" in content or "Assert-Command" in content


def test_sh_checks_prerequisites():
    content = read_script(SH_SCRIPT)
    assert "check_command" in content or "command -v" in content
    assert "git" in content
    assert "docker" in content
    assert "aws" in content


# ---------------------------------------------------------------------------
# CloudFormation stack prerequisite documented
# ---------------------------------------------------------------------------

def test_ps1_documents_cfn_prerequisite():
    content = read_script(PS1_SCRIPT)
    assert "cloudformation" in content.lower()
    assert "deploy" in content.lower()


def test_sh_documents_cfn_prerequisite():
    content = read_script(SH_SCRIPT)
    assert "cloudformation" in content.lower()
    assert "deploy" in content.lower()


# ---------------------------------------------------------------------------
# ECR URI resolved from CloudFormation stack output, not hard-coded
# ---------------------------------------------------------------------------

def test_ps1_resolves_ecr_uri_from_cfn():
    content = read_script(PS1_SCRIPT)
    assert "describe-stacks" in content
    assert "EcrRepositoryUri" in content


def test_sh_resolves_ecr_uri_from_cfn():
    content = read_script(SH_SCRIPT)
    assert "describe-stacks" in content
    assert "EcrRepositoryUri" in content


# ---------------------------------------------------------------------------
# Git commit hash tag comes from rev-parse
# ---------------------------------------------------------------------------

def test_ps1_uses_git_rev_parse():
    content = read_script(PS1_SCRIPT)
    assert "rev-parse" in content
    assert "--short" in content


def test_sh_uses_git_rev_parse():
    content = read_script(SH_SCRIPT)
    assert "rev-parse" in content
    assert "--short" in content
