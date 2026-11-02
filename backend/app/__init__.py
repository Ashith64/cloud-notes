from flask import Flask, jsonify
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.from_mapping(config_class)
    else:
        app.config.from_object(config_class)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "ok",
            "version": app.config.get("APP_VERSION", "0.1.0")
        }), 200

    return app
