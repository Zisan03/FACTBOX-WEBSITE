"""Application factory module.

Constructs and configures the Flask application instance according to project specifications.
Enforces ADR-001, ADR-009, and Stage 2 requirements.
"""
import logging
import sys
import uuid
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request
from app.config import get_config
from app.extensions import db, migrate, csrf, login_manager, limiter, mail
from app.blueprints.health import health_bp
from app.blueprints.public import public_bp
from app.blueprints.contact import contact_bp
from app.blueprints.admin import admin_bp
import app.models  # Ensures all models are registered with SQLAlchemy metadata


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

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        if request.path.startswith("/api/") or request.path == "/health":
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
        return render_template(
            "errors/400.html",
            error_message="Too many requests. Please wait a moment before trying again.",
        ), 429

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


def register_cli_commands(app: Flask):
    """Register administrative CLI commands."""
    import click
    from app.models.admin import AdminUser, AdminAuditEvent

    @app.cli.command("create-admin")
    @click.option("--email", prompt="Admin Email", help="Administrator email address")
    @click.password_option(help="Administrator password (minimum 8 characters)")
    def create_admin(email, password):
        """Provision an administrator account securely."""
        normalized_email = email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            click.echo("Error: Please provide a valid email address.")
            sys.exit(1)

        if len(password) < 8:
            click.echo("Error: Password must be at least 8 characters long.")
            sys.exit(1)

        existing = AdminUser.query.filter_by(email=normalized_email).first()
        if existing:
            click.echo(f"Error: Admin user with email '{normalized_email}' already exists.")
            sys.exit(1)

        admin = AdminUser(email=normalized_email, is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        audit = AdminAuditEvent(
            admin_user_id=admin.id,
            event_type="admin_provisioned_cli",
            safe_metadata={"email": normalized_email},
        )
        db.session.add(audit)
        db.session.commit()
        click.echo(f"Successfully provisioned administrator: {normalized_email}")

    @app.cli.command("reset-admin-password")
    @click.option("--email", prompt="Admin Email", help="Administrator email address")
    @click.password_option(help="New administrator password (minimum 8 characters)")
    def reset_admin_password(email, password):
        """Emergency reset of an administrator's password via CLI."""
        normalized_email = email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            click.echo("Error: Please provide a valid email address.")
            sys.exit(1)

        if len(password) < 8:
            click.echo("Error: Password must be at least 8 characters long.")
            sys.exit(1)

        admin = AdminUser.query.filter_by(email=normalized_email).first()
        if not admin:
            click.echo(f"Error: Admin user with email '{normalized_email}' not found.")
            sys.exit(1)

        admin.set_password(password)
        audit = AdminAuditEvent(
            admin_user_id=admin.id,
            event_type="admin_password_reset_cli",
            safe_metadata={"email": normalized_email},
        )
        db.session.add(audit)
        db.session.commit()
        click.echo(f"Successfully reset password for administrator: {normalized_email}")

    @app.cli.command("seed-partner-logos")
    def seed_partner_logos():
        """Seed the 7 verified partner organizations into PostgreSQL."""
        from app.models.content import PartnerLogo

        partners_data = [
            {
                "name": "Mercy Corps",
                "logo_cloudinary_public_id": "static/img/partners/mercy-corps",
                "logo_secure_url": "/static/img/partners/mercy-corps.png",
                "website_url": "https://www.mercycorps.org",
                "alt_text": "Mercy Corps official emblem",
                "display_order": 1,
            },
            {
                "name": "International Alert",
                "logo_cloudinary_public_id": "static/img/partners/international-alert",
                "logo_secure_url": "/static/img/partners/international-alert.jpg",
                "website_url": "https://www.international-alert.org",
                "alt_text": "International Alert organization logo",
                "display_order": 2,
            },
            {
                "name": "Malaria Consortium",
                "logo_cloudinary_public_id": "static/img/partners/malaria-consortium",
                "logo_secure_url": "/static/img/partners/malaria-consortium.png",
                "website_url": "https://www.malariaconsortium.org",
                "alt_text": "Malaria Consortium - disease control, better health",
                "display_order": 3,
            },
            {
                "name": "GIZ",
                "logo_cloudinary_public_id": "static/img/partners/giz",
                "logo_secure_url": "/static/img/partners/giz.png",
                "website_url": "https://www.giz.de",
                "alt_text": "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH",
                "display_order": 4,
            },
            {
                "name": "Norwegian Refugee Council (NRC)",
                "logo_cloudinary_public_id": "static/img/partners/nrc",
                "logo_secure_url": "/static/img/partners/norwegian-refugee-council.gif",
                "website_url": "https://www.nrc.no",
                "alt_text": "Norwegian Refugee Council (NRC) official logo",
                "display_order": 5,
            },
            {
                "name": "Public Services International (PSI)",
                "logo_cloudinary_public_id": "static/img/partners/psi",
                "logo_secure_url": "/static/img/partners/psi.png",
                "website_url": "https://publicservices.international",
                "alt_text": "Public Services International (PSI) emblem",
                "display_order": 6,
            },
            {
                "name": "Capacity 4 Sustainable Development Ltd.",
                "logo_cloudinary_public_id": "static/img/partners/capacity4dev",
                "logo_secure_url": "/static/img/partners/capacity-4-dev.jpg",
                "website_url": None,
                "alt_text": "Capacity 4 Sustainable Development Ltd. logo",
                "display_order": 7,
            },
        ]

        count = 0
        for p in partners_data:
            existing = PartnerLogo.query.filter_by(name=p["name"]).first()
            if not existing:
                logo = PartnerLogo(
                    name=p["name"],
                    logo_cloudinary_public_id=p["logo_cloudinary_public_id"],
                    logo_secure_url=p["logo_secure_url"],
                    website_url=p["website_url"],
                    alt_text=p["alt_text"],
                    display_order=p["display_order"],
                    is_published=True,
                )
                db.session.add(logo)
                count += 1
            else:
                existing.logo_secure_url = p["logo_secure_url"]
                existing.alt_text = p["alt_text"]
                existing.display_order = p["display_order"]
                existing.is_published = True

        db.session.commit()
        click.echo(f"Successfully processed partner logos ({count} new records added).")


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
    login_manager.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    # Configure user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models.admin import AdminUser
            return db.session.get(AdminUser, uuid.UUID(user_id))
        except (ValueError, TypeError):
            return None

    # Global context processor for site-wide template variables
    @app.context_processor
    def inject_global_data():
        try:
            from app.models.content import PartnerLogo
            logos = (
                PartnerLogo.query.filter_by(is_published=True)
                .order_by(PartnerLogo.display_order.asc(), PartnerLogo.created_at.asc())
                .all()
            )
        except Exception:
            logos = []
        return {
            "partner_logos": logos,
            "current_year": datetime.now(timezone.utc).year,
        }

    # Template filters
    @app.template_filter("org_slug")
    def org_slug_filter(value):
        from app.constants import get_org_slug
        return get_org_slug(value)


    # Configure logging, error handlers, and security headers
    configure_logging(app)
    register_error_handlers(app)
    register_security_headers(app)
    register_cli_commands(app)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(admin_bp)

    return app
