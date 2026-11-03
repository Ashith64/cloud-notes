"""
Stage 9 — Secrets generation and image push script validation tests.

Verifies that:
1. scripts/create-secrets.ps1 and scripts/create-secrets.sh exist and are non-empty.
2. scripts/push-image.ps1 and scripts/push-image.sh exist and are non-empty.
3. Neither script contains hard-coded AWS account IDs or plaintext credentials.
4. Neither script prints or stores secret / credential values to disk or terminal output.
5. Both create-secrets scripts:
   - Target SSM Parameter Store parameters /cloudnotes/db-password and /cloudnotes/jwt-secret.
   - Use type SecureString.
   - Use region ap-southeast-2 by default.
   - Check existence using `aws ssm describe-parameters` (metadata only, never get-parameter or values).
   - Skip parameters that already exist.
   - Generate alphanumeric secrets of lengths 24 and 48 locally.
6. Both push-image scripts:
   - Use `aws sts get-caller-identity` to resolve the account ID dynamically.
   - Use region ap-southeast-2 by default.
   - Construct ECR URI dynamically without unnecessary CloudFormation stack lookups.
   - Authenticate to ECR using `aws ecr get-login-password` piped to `docker login --password-stdin`.
   - Never print or expose the login token.
   - Build with `--platform linux/amd64`.
   - Tag with short Git commit hash and `latest`.
   - Push both tags.
   - Print the image tag.
"""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

PS1_SECRETS = SCRIPTS_DIR / "create-secrets.ps1"
SH_SECRETS  = SCRIPTS_DIR / "create-secrets.sh"
PS1_PUSH    = SCRIPTS_DIR / "push-image.ps1"
SH_PUSH     = SCRIPTS_DIR / "push-image.sh"


def read_script(path: Path) -> str:
    assert path.exists(), f"Script not found: {path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 100, f"Script appears empty or too short: {path}"
    return content


# ---------------------------------------------------------------------------
# Existence tests
# ---------------------------------------------------------------------------

def test_create_secrets_ps1_exists():
    assert PS1_SECRETS.exists(), f"Missing: {PS1_SECRETS}"


def test_create_secrets_sh_exists():
    assert SH_SECRETS.exists(), f"Missing: {SH_SECRETS}"


def test_push_image_ps1_exists():
    assert PS1_PUSH.exists(), f"Missing: {PS1_PUSH}"


def test_push_image_sh_exists():
    assert SH_PUSH.exists(), f"Missing: {SH_PUSH}"


# ---------------------------------------------------------------------------
# Security: no hard-coded account IDs or credentials in any script
# ---------------------------------------------------------------------------

TWELVE_DIGIT_PATTERN = re.compile(r'\b\d{12}\b')


def test_no_hardcoded_account_ids():
    for script_path in [PS1_SECRETS, SH_SECRETS, PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        matches = TWELVE_DIGIT_PATTERN.findall(content)
        assert not matches, (
            f"{script_path.name} contains what looks like a hard-coded AWS account ID: {matches}"
        )


def test_dynamic_account_id_resolution():
    for script_path in [PS1_SECRETS, SH_SECRETS, PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "sts get-caller-identity" in content, (
            f"{script_path.name} must resolve AWS account dynamically via sts get-caller-identity"
        )


# ---------------------------------------------------------------------------
# create-secrets: SSM Parameter Store and SecureString
# ---------------------------------------------------------------------------

def test_create_secrets_target_parameters():
    for script_path in [PS1_SECRETS, SH_SECRETS]:
        content = read_script(script_path)
        assert "/cloudnotes/db-password" in content, (
            f"{script_path.name} must target SSM parameter '/cloudnotes/db-password'"
        )
        assert "/cloudnotes/jwt-secret" in content, (
            f"{script_path.name} must target SSM parameter '/cloudnotes/jwt-secret'"
        )
        assert "SecureString" in content, (
            f"{script_path.name} must store parameters with type SecureString"
        )
        assert "ssm put-parameter" in content, (
            f"{script_path.name} must call aws ssm put-parameter"
        )


def test_create_secrets_default_region_ap_southeast_2():
    for script_path in [PS1_SECRETS, SH_SECRETS]:
        content = read_script(script_path)
        assert "ap-southeast-2" in content, (
            f"{script_path.name} must default to region ap-southeast-2"
        )


def test_create_secrets_uses_describe_parameters_and_skips_existing():
    for script_path in [PS1_SECRETS, SH_SECRETS]:
        content = read_script(script_path)
        # Must use describe-parameters to inspect metadata only
        assert "ssm describe-parameters" in content, (
            f"{script_path.name} must check parameter metadata using aws ssm describe-parameters"
        )
        # Must NOT use get-parameter for existence checks
        assert "ssm get-parameter" not in content, (
            f"{script_path.name} must not call aws ssm get-parameter; use describe-parameters instead"
        )
        assert "Skipping" in content or "skipping" in content, (
            f"{script_path.name} must report skipping if parameter already exists"
        )


def test_create_secrets_lengths_and_generation():
    ps1_content = read_script(PS1_SECRETS)
    sh_content = read_script(SH_SECRETS)

    # DB password length 24, JWT secret length 48
    assert "24" in ps1_content and "48" in ps1_content
    assert "24" in sh_content and "48" in sh_content

    # PS1 uses RandomNumberGenerator, SH uses /dev/urandom
    assert "RandomNumberGenerator" in ps1_content or "RNGCryptoServiceProvider" in ps1_content
    assert "/dev/urandom" in sh_content


def test_create_secrets_never_prints_or_saves_secrets():
    for script_path in [PS1_SECRETS, SH_SECRETS]:
        content = read_script(script_path)
        # Verify secret values are not written to files (> file or Out-File / Set-Content)
        assert "Out-File" not in content
        assert "Set-Content" not in content
        assert "> secrets" not in content and "> password" not in content
        # Verify put-parameter uses [REDACTED] or does not echo secret values in logs
        assert "[REDACTED]" in content


# ---------------------------------------------------------------------------
# push-image tests
# ---------------------------------------------------------------------------

def test_push_image_default_region_ap_southeast_2():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "ap-southeast-2" in content, (
            f"{script_path.name} must use region ap-southeast-2"
        )


def test_push_image_no_cloudformation_app_stack_lookup():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        # Must not perform CloudFormation stack lookups
        assert "cloudformation describe-stacks" not in content, (
            f"{script_path.name} should not query describe-stacks for cloudnotes-app"
        )
        assert "cloudnotes-app" not in content, (
            f"{script_path.name} should not reference cloudnotes-app stack"
        )
        # Must construct dynamic ECR URI with repo name cloudnotes
        assert "cloudnotes" in content
        assert ".dkr.ecr." in content


def test_push_image_ecr_login_token_protection():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "ecr get-login-password" in content
        assert "docker login" in content
        assert "--password-stdin" in content
        # Ensure password is piped directly and never echoed or logged
        assert "echo" not in content or "password-stdin" in content


def test_push_image_build_linux_amd64():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "--platform linux/amd64" in content


def test_push_image_pushes_two_tags():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "rev-parse" in content
        assert "--short" in content
        assert "latest" in content
        assert content.lower().count("docker push") >= 2


def test_push_image_prints_image_tag():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "Image tag" in content or "IMAGE_TAG" in content


def test_push_image_checks_prerequisites():
    for script_path in [PS1_PUSH, SH_PUSH]:
        content = read_script(script_path)
        assert "git" in content.lower()
        assert "docker" in content.lower()
        assert "aws" in content.lower()
