"""Shared Flask extensions, initialised in the app factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Engine and session are created per app instance via init_extensions().
# These module-level names are updated by init_extensions() and read
# by other modules (db.py, routes) that import from here.
engine = None
SessionLocal = None


def init_extensions(app):
    """Bind SQLAlchemy engine and session factory to the Flask app.

    Stores the engine and scoped session on the app object so that multiple
    app instances (e.g. in tests) don't overwrite each other's globals.
    """
    global engine, SessionLocal

    _engine = create_engine(
        app.config["DATABASE_URL"],
        pool_pre_ping=True,
        # SQLite needs check_same_thread=False so requests from different
        # threads can reuse the same connection.
        connect_args=(
            {"check_same_thread": False}
            if app.config["DATABASE_URL"].startswith("sqlite")
            else {}
        ),
    )
    session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    _session = scoped_session(session_factory)

    # Store on the app so each instance has its own engine/session.
    app._db_engine = _engine
    app._db_session = _session

    # Update module globals (used by code outside a request context,
    # e.g. the CLI command and db.py).  The last app to call init_extensions
    # wins, which is fine for production (single app) and acceptable for tests
    # when only one app is active at a time.
    engine = _engine
    SessionLocal = _session

    # Tear down the scoped session after every request.
    @app.teardown_appcontext
    def remove_session(exc=None):
        app._db_session.remove()
