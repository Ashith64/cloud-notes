"""Flask application factory for Cloud Notes."""
import click
from flask import Flask, jsonify, request

from .config import Config
from .extensions import SessionLocal, init_extensions


def create_app(config_class=Config):
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
    # Public routes
    # ------------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "version": app.config.get("APP_VERSION", "0.1.0")}), 200

    @app.route("/api/user/storage", methods=["GET"])
    def user_storage():
        from .routes.auth import storage_usage
        return storage_usage()

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
