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
    app.register_blueprint(auth_bp)

    # ------------------------------------------------------------------
    # Public routes
    # ------------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "version": app.config.get("APP_VERSION", "0.1.0")}), 200

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

    return app
