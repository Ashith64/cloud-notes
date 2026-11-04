"""Application configuration.

Production secret resolution (D3.10):
  When DB_SECRET_ARN, DB_HOST, DB_NAME and APP_SECRET_ARN are all set, the app
  fetches the database credentials and the Flask SECRET_KEY from AWS Secrets
  Manager at start-up using the default boto3 credential chain (instance role
  in production).  Fetched values are cached in-memory so each process only
  makes two Secrets Manager calls at startup.

  When any of those four variables is absent the app behaves exactly as before:
  DATABASE_URL and SECRET_KEY are read directly from the environment.
"""
import json
import logging
import os

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache for secrets fetched from AWS Secrets Manager.
# Cached values persist for the lifetime of the process.
# ---------------------------------------------------------------------------
_SECRETS_CACHE: dict[str, str] = {}


def _get_secret(arn: str, region: str) -> str:
    """Fetch a secret string from AWS Secrets Manager, with in-memory caching."""
    if arn in _SECRETS_CACHE:
        return _SECRETS_CACHE[arn]

    import boto3  # lazy import — only needed in production

    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.get_secret_value(SecretId=arn)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to retrieve secret '{arn}' from AWS Secrets Manager: {exc}"
        ) from exc

    secret = resp.get("SecretString") or ""
    _SECRETS_CACHE[arn] = secret
    return secret


def _resolve_secrets() -> dict:
    """Build a config override dict using Secrets Manager when ARNs are configured.

    Returns an empty dict when the ARN variables are not set (dev / test mode).
    """
    db_secret_arn = os.environ.get("DB_SECRET_ARN", "")
    db_host = os.environ.get("DB_HOST", "")
    db_name = os.environ.get("DB_NAME", "")
    app_secret_arn = os.environ.get("APP_SECRET_ARN", "")

    if not all([db_secret_arn, db_host, db_name, app_secret_arn]):
        # Dev/test: use environment variables directly.
        return {}

    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    log.info("Fetching secrets from AWS Secrets Manager (region=%s)…", region)

    # --- Database credentials ---
    db_secret_raw = _get_secret(db_secret_arn, region)
    try:
        db_creds = json.loads(db_secret_raw)
        db_user = db_creds["username"]
        db_pass = db_creds["password"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(
            "DB secret must be JSON with 'username' and 'password' keys"
        ) from exc

    db_port = os.environ.get("DB_PORT", "3306")
    database_url = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        "?charset=utf8mb4"
    )

    # --- Application secret key ---
    secret_key = _get_secret(app_secret_arn, region).strip()
    if not secret_key:
        raise RuntimeError("APP_SECRET_ARN resolved to an empty secret value.")

    log.info("Secrets resolved successfully from AWS Secrets Manager.")
    return {
        "DATABASE_URL": database_url,
        "SECRET_KEY": secret_key,
    }


# ---------------------------------------------------------------------------
# Resolve secrets once at import time so create_app() picks them up.
# In dev/test the dict is empty and the env-var defaults below apply.
# ---------------------------------------------------------------------------
_aws_overrides = _resolve_secrets()


class Config:
    # Secret key — overridden from Secrets Manager when APP_SECRET_ARN is set.
    SECRET_KEY: str = _aws_overrides.get(
        "SECRET_KEY",
        os.environ.get(
            "SECRET_KEY",
            "cloudnotes-dev-secret-key-32bytes-minimum-length-security-passphrase",
        ),
    )

    # Database URL — overridden from Secrets Manager when DB_SECRET_ARN is set.
    DATABASE_URL: str = _aws_overrides.get(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "sqlite:///dev.db"),
    )

    STORAGE_BACKEND: str = os.environ.get("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_PATH: str = os.environ.get("LOCAL_STORAGE_PATH", "./local_data")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "")
    AWS_REGION: str = os.environ.get("AWS_REGION", "ap-southeast-2")
    JWT_EXPIRY_DAYS: int = int(os.environ.get("JWT_EXPIRY_DAYS", "7"))
    ASG_NAME: str = os.environ.get("ASG_NAME", "")
    DB_INSTANCE_ID: str = os.environ.get("DB_INSTANCE_ID", "")
    APP_VERSION: str = "0.1.0"
    TRASH_PURGE_DAYS: int = int(os.environ.get("TRASH_PURGE_DAYS", "30"))

    # COOKIE_SECURE (D3.8): set to true/1/yes in production (HTTPS).
    # Defaults to False so http://localhost:8000 works in Docker Compose.
    COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # Path to the built React frontend dist folder (used for SPA serving).
    FRONTEND_DIST_DIR: str = os.environ.get(
        "FRONTEND_DIST_DIR",
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "frontend", "dist"
            )
        ),
    )

    # Allow tests to override TESTING without inheriting irrelevant config keys.
    TESTING: bool = False
