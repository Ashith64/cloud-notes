"""Database initialisation helpers.

init_db() calls Base.metadata.create_all().  On MySQL it wraps the call in a
named advisory lock (GET_LOCK / RELEASE_LOCK) so concurrent container starts
don't race to create the schema simultaneously.
"""
import logging

from sqlalchemy import text

from .models import Base

log = logging.getLogger(__name__)

_MYSQL_LOCK_NAME = "cloudnotes_init_db"
_MYSQL_LOCK_TIMEOUT = 30  # seconds


def init_db() -> None:
    """Create all tables.  Safe to call every startup (create_all is idempotent).

    Must be called while an application context is active.  The engine is
    retrieved from the extensions module at call time (after create_app() has
    initialised it).
    """
    from . import extensions  # late import so the global is already set

    eng = extensions.engine
    if eng is None:
        raise RuntimeError("init_db() called before init_extensions().  "
                           "Make sure you call it inside an app context.")

    is_mysql = eng.dialect.name == "mysql"

    if is_mysql:
        _init_db_mysql(eng)
    else:
        Base.metadata.create_all(eng)
        log.info("Database tables created (SQLite / non-MySQL)")


def _init_db_mysql(eng) -> None:
    """Acquire a MySQL named lock before running create_all."""
    with eng.connect() as conn:
        result = conn.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": _MYSQL_LOCK_NAME, "timeout": _MYSQL_LOCK_TIMEOUT},
        )
        lock_acquired = result.scalar() == 1
        if not lock_acquired:
            log.warning(
                "Could not acquire MySQL lock '%s'; another server may be "
                "initialising the database.  Skipping create_all.",
                _MYSQL_LOCK_NAME,
            )
            return

        try:
            Base.metadata.create_all(eng)
            log.info("Database tables created (MySQL, under advisory lock)")
        finally:
            conn.execute(
                text("SELECT RELEASE_LOCK(:name)"), {"name": _MYSQL_LOCK_NAME}
            )
