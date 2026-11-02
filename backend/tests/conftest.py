"""Shared pytest fixtures for the test suite."""
import os
import tempfile

import pytest

from app import create_app
from app.db import init_db


@pytest.fixture(scope="session")
def app():
    """Create an application instance backed by a temp SQLite database."""
    db_path = tempfile.mktemp(suffix=".db")  # path only, not opened yet

    test_config = {
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{db_path}",
        # 32-byte key to keep PyJWT happy (and silence InsecureKeyLengthWarning)
        "SECRET_KEY": "test-secret-key-exactly-32-bytes",
        "JWT_EXPIRY_DAYS": 1,
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_PATH": tempfile.mkdtemp(),
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
