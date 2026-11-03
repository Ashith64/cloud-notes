"""Flask application factory for Cloud Notes."""
import json
import logging
import logging.config
import os
import time
import uuid

import click
from flask import Flask, g, jsonify, request, send_from_directory

from .config import Config
from .extensions import SessionLocal, init_extensions


# ---------------------------------------------------------------------------
# Structured JSON log formatter
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emits one JSON object per log record with keys required by the spec."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            # Request-scoped fields are set by the after_request hook; for
            # non-request log lines they default to None.
            "request_id": None,
            "route": None,
            "status": None,
            "duration_ms": None,
        }
        # Merge any extra fields attached by the request hooks.
        for key in ("request_id", "route", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_logging() -> None:
    """Replace the root handler with a JSON-to-stdout handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    # Remove any existing handlers set up by Flask's default config.
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def create_app(config_class=Config):
    _configure_logging()

    app = Flask(__name__)

    # ------------------------------------------------------------------
    # Load configuration
    # ------------------------------------------------------------------
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.from_mapping(config_class)
    else:
        app.config.from_object(config_class)

    # ------------------------------------------------------------------
    # Extensions (SQLAlchemy engine + session)
    # ------------------------------------------------------------------
    init_extensions(app)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from .routes.auth import auth_bp
    from .routes.notes import notes_bp
    from .routes.notebooks import notebooks_bp
    from .routes.tags import tags_bp
    from .routes.attachments import attachments_bp
    from .routes.export_routes import export_bp
    from .routes.status import status_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(notebooks_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(status_bp)

    # ------------------------------------------------------------------
    # Request lifecycle hooks — request ID tracking + structured logging
    # ------------------------------------------------------------------
    log = logging.getLogger(__name__)

    @app.before_request
    def _before():
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.start_time = time.perf_counter()

    @app.after_request
    def _after(response):
        duration_ms = round((time.perf_counter() - g.start_time) * 1000, 2)
        response.headers["X-Request-Id"] = g.request_id
        # Build a LogRecord with extra request fields so the JSON formatter
        # can include them.
        extra = {
            "request_id": g.request_id,
            "route": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }
        log.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra=extra,
        )
        return response

    # ------------------------------------------------------------------
    # Public API routes
    # ------------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "version": app.config.get("APP_VERSION", "0.1.0")}), 200

    @app.route("/api/user/storage", methods=["GET"])
    def user_storage():
        from .routes.auth import storage_usage
        return storage_usage()

    # ------------------------------------------------------------------
    # SPA static file serving + fallback to index.html (D3.1)
    #
    # Flask serves the built React files for every non-/api path.
    # This means page refreshes at /login, /app, /settings, /status all
    # return index.html and React Router handles the routing client-side.
    # ------------------------------------------------------------------
    dist_dir = app.config.get("FRONTEND_DIST_DIR", "")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_catch_all(path):
        # API paths: let the 404 error handler return JSON.
        if path.startswith("api/") or path == "api":
            return jsonify({"error": {"code": "not_found", "message": "Not found"}}), 404

        if dist_dir and os.path.isdir(dist_dir):
            # Serve a real static asset if it exists (e.g. /assets/main.js).
            candidate = os.path.join(dist_dir, path)
            if path and os.path.isfile(candidate):
                return send_from_directory(dist_dir, path)
            # Fall back to index.html for all other paths (client-side routing).
            index = os.path.join(dist_dir, "index.html")
            if os.path.isfile(index):
                return send_from_directory(dist_dir, "index.html")

        return jsonify({"error": {"code": "not_found", "message": "Frontend not built."}}), 404

    # ------------------------------------------------------------------
    # Global JSON error handlers  (spec D5 error format)
    # ------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(exc):
        return jsonify({"error": {"code": "bad_request", "message": str(exc)}}), 400

    @app.errorhandler(401)
    def unauthorized(exc):
        return jsonify({"error": {"code": "unauthorized", "message": str(exc)}}), 401

    @app.errorhandler(403)
    def forbidden(exc):
        return jsonify({"error": {"code": "forbidden", "message": str(exc)}}), 403

    @app.errorhandler(404)
    def not_found(exc):
        # Return JSON only for /api/* requests; let the SPA handler deal with
        # browser navigation paths (they never reach here because the catch-all
        # route is registered above).
        return jsonify({"error": {"code": "not_found", "message": str(exc)}}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return jsonify({"error": {"code": "method_not_allowed", "message": str(exc)}}), 405

    @app.errorhandler(409)
    def conflict(exc):
        return jsonify({"error": {"code": "conflict", "message": str(exc)}}), 409

    @app.errorhandler(422)
    def unprocessable(exc):
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 422

    @app.errorhandler(429)
    def too_many_requests(exc):
        return jsonify({"error": {"code": "rate_limited", "message": str(exc)}}), 429

    @app.errorhandler(500)
    def server_error(exc):
        return jsonify({"error": {"code": "server_error", "message": "An internal error occurred."}}), 500

    # ------------------------------------------------------------------
    # Flask CLI commands
    # ------------------------------------------------------------------
    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        from .db import init_db
        init_db()
        click.echo("Database initialised.")

    @app.cli.command("reindex")
    def reindex_command():
        """Rebuild notes index (title, snippet, search_text, tags) from stored files."""
        import frontmatter as fm
        from .models import Note, NoteTag, Tag
        from .storage.factory import get_storage
        from .utils import make_snippet, strip_markdown

        db = app._db_session()
        storage = get_storage(app)
        notes = db.query(Note).all()
        count = 0
        for note in notes:
            try:
                raw = storage.get_text(note.storage_key)
            except FileNotFoundError:
                click.echo(f"  SKIP {note.id}: file not found at {note.storage_key}")
                continue

            post = fm.loads(raw)
            note.title = post.metadata.get("title", "Untitled")
            note.snippet = make_snippet(post.content)
            note.search_text = strip_markdown(post.content)

            # Rebuild tags
            for nt in list(note.note_tags):
                db.delete(nt)
            db.flush()

            file_tags = post.metadata.get("tags") or []
            seen_tag_ids = set()
            for tag_name in file_tags:
                name = str(tag_name).strip().lower()[:30]
                if not name:
                    continue
                tag = db.query(Tag).filter_by(user_id=note.user_id, name=name).first()
                if not tag:
                    tag = Tag(user_id=note.user_id, name=name)
                    db.add(tag)
                    db.flush()
                if tag.id not in seen_tag_ids:
                    seen_tag_ids.add(tag.id)
                    db.add(NoteTag(note_id=note.id, tag_id=tag.id))

            count += 1

        db.commit()
        click.echo(f"Reindexed {count} note(s).")

    return app
