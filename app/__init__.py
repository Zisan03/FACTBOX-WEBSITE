"""Application factory module.

Constructs and configures the Flask application instance according to project specifications.
"""
import logging
import sys
from flask import Flask, render_template, jsonify, request
from app.config import get_config
from app.extensions import db, migrate, csrf
from app.blueprints.health import health_bp
from app.blueprints.public import public_bp
from app.blueprints.contact import contact_bp
from app.blueprints.admin import admin_bp


def configure_logging(app: Flask):
    """Set up structured application logging."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    handler.setFormatter(formatter)

    # Clean existing handlers and set level
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO if not app.debug else logging.DEBUG)


def register_error_handlers(app: Flask):
    """Register safe custom error handlers preventing stack trace leakage."""
    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith("/api/") or request.path == "/health":
            return jsonify({"error": "Bad request"}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error("Unhandled exception: %s", error)
        if request.path.startswith("/api/") or request.path == "/health":
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500


def register_security_headers(app: Flask):
    """Inject modern security headers into all responses."""
    @app.after_request
    def set_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


def create_app(config_name: str | None = None) -> Flask:
    """Application factory for Fact Box Consult web application."""
    app = Flask(__name__)

    # Load configuration
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Configure logging, error handlers, and security headers
    configure_logging(app)
    register_error_handlers(app)
    register_security_headers(app)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(admin_bp)

    return app
