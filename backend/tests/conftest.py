"""Shared pytest fixtures for the test suite.

DATABASE_URL selection
----------------------
By default tests run against a temp SQLite database (fast, zero setup).
To run against MySQL, set the environment variable before running pytest:

    $env:TEST_DATABASE_URL = "mysql+pymysql://cloudnotes:cloudnotes_secret@127.0.0.1:3306/cloudnotes?charset=utf8mb4"
    pytest tests/ -v

The fixture automatically:
  - Drops and re-creates all tables for MySQL so every test session starts clean.
  - For SQLite uses a temporary file (auto-cleaned on teardown).
"""
import os
import tempfile

import pytest

from app import create_app
from app.db import init_db


def _test_database_url():
    """Return the database URL to use for the test session."""
    return os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session")
def app():
    """Create an application instance for the test session."""
    mysql_url = _test_database_url()

    if mysql_url:
        # ---- MySQL test session ----
        # Drop all tables first to ensure a clean slate, then create_all.
        from sqlalchemy import create_engine, text
        from app.models import Base

        _engine = create_engine(mysql_url, pool_pre_ping=True)
        with _engine.begin() as conn:
            # Disable FK checks so we can drop tables in any order.
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"DROP TABLE IF EXISTS `{table.name}`"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        _engine.dispose()

        test_config = {
            "TESTING": True,
            "DATABASE_URL": mysql_url,
            "SECRET_KEY": "test-secret-key-exactly-32-bytes",
            "JWT_EXPIRY_DAYS": 1,
            "STORAGE_BACKEND": "local",
            "LOCAL_STORAGE_PATH": tempfile.mkdtemp(),
            # Disable SPA fallback so tests get clean JSON 404s.
            "FRONTEND_DIST_DIR": "",
        }
        application = create_app(test_config)
        with application.app_context():
            init_db()
            yield application
        # No file cleanup needed for MySQL.

    else:
        # ---- SQLite test session (default) ----
        db_path = tempfile.mktemp(suffix=".db")  # path only, not opened yet
        test_config = {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{db_path}",
            # 32-byte key to keep PyJWT happy (and silence InsecureKeyLengthWarning)
            "SECRET_KEY": "test-secret-key-exactly-32-bytes",
            "JWT_EXPIRY_DAYS": 1,
            "STORAGE_BACKEND": "local",
            "LOCAL_STORAGE_PATH": tempfile.mkdtemp(),
            # Disable SPA fallback so tests get clean JSON 404s.
            "FRONTEND_DIST_DIR": "",
        }
        application = create_app(test_config)
        with application.app_context():
            init_db()
            yield application

        # Windows: SQLAlchemy may still hold the file open; ignore deletion errors.
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture()
def client(app):
    """HTTP test client (fresh cookie jar per test)."""
    return app.test_client()


# Convenience headers
CSRF = {"X-Requested-With": "cloudnotes"}
