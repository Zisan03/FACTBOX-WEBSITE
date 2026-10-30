"""Application factory module.

Constructs and configures the Flask application instance according to project specifications.
Enforces ADR-001, ADR-009, and Stage 2 requirements.
"""
import logging
import os
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

    @app.cli.command("init-admin")
    def init_admin():
        """Ensure initial administrator exists (safe for automated deployment)."""
        email = os.environ.get("INITIAL_ADMIN_EMAIL", "admin@factboxconsult.com").strip().lower()
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "FactBox2026!")

        existing = AdminUser.query.filter_by(email=email).first()
        if existing:
            click.echo(f"Administrator '{email}' already exists. No action needed.")
            return

        admin = AdminUser(email=email, is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        audit = AdminAuditEvent(
            admin_user_id=admin.id,
            event_type="admin_provisioned_cli",
            safe_metadata={"email": email, "automated_init": True},
        )
        db.session.add(audit)
        db.session.commit()
        click.echo(f"Successfully provisioned initial administrator: {email}")

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
        """Seed the 7 verified partner organizations into PostgreSQL with Cloudinary CDN assets."""
        from app.models.content import PartnerLogo
        from app.services.media import get_optimized_delivery_url

        partners_data = [
            {
                "name": "Mercy Corps",
                "logo_cloudinary_public_id": "factbox/partner_logos/gsjax2legfdz502bt23d",
                "website_url": "https://www.mercycorps.org",
                "alt_text": "Mercy Corps official emblem",
                "display_order": 1,
            },
            {
                "name": "International Alert",
                "logo_cloudinary_public_id": "factbox/partner_logos/g725yqqj331tkqwrr2yn",
                "website_url": "https://www.international-alert.org",
                "alt_text": "International Alert organization logo",
                "display_order": 2,
            },
            {
                "name": "Malaria Consortium",
                "logo_cloudinary_public_id": "factbox/partner_logos/wxxsdt6cjltdr0sua0v7",
                "website_url": "https://www.malariaconsortium.org",
                "alt_text": "Malaria Consortium - disease control, better health",
                "display_order": 3,
            },
            {
                "name": "GIZ",
                "logo_cloudinary_public_id": "factbox/partner_logos/gdxqtejvs8qkswywzvax",
                "website_url": "https://www.giz.de",
                "alt_text": "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH",
                "display_order": 4,
            },
            {
                "name": "Norwegian Refugee Council (NRC)",
                "logo_cloudinary_public_id": "factbox/partner_logos/pwf156ifhqoe6ckfedim",
                "website_url": "https://www.nrc.no",
                "alt_text": "Norwegian Refugee Council (NRC) official logo",
                "display_order": 5,
            },
            {
                "name": "Public Services International (PSI)",
                "logo_cloudinary_public_id": "factbox/partner_logos/ort5r7yhkpguiy9gpve5",
                "website_url": "https://publicservices.international",
                "alt_text": "Public Services International (PSI) emblem",
                "display_order": 6,
            },
            {
                "name": "Capacity 4 Sustainable Development Ltd.",
                "logo_cloudinary_public_id": "factbox/partner_logos/mluqwd4yhmbkdfso5zrr",
                "website_url": None,
                "alt_text": "Capacity 4 Sustainable Development Ltd. logo",
                "display_order": 7,
            },
        ]

        count = 0
        for p in partners_data:
            existing = PartnerLogo.query.filter_by(name=p["name"]).first()
            secure_url = get_optimized_delivery_url(p["logo_cloudinary_public_id"])
            if not existing:
                logo = PartnerLogo(
                    name=p["name"],
                    logo_cloudinary_public_id=p["logo_cloudinary_public_id"],
                    logo_secure_url=secure_url,
                    website_url=p["website_url"],
                    alt_text=p["alt_text"],
                    display_order=p["display_order"],
                    is_published=True,
                )
                db.session.add(logo)
                count += 1
            else:
                existing.logo_cloudinary_public_id = p["logo_cloudinary_public_id"]
                existing.logo_secure_url = secure_url
                existing.alt_text = p["alt_text"]
                existing.display_order = p["display_order"]
                existing.is_published = True

        db.session.commit()
        click.echo(f"Successfully processed partner logos ({count} new records added).")

    @app.cli.command("seed-home-photos")
    def seed_home_photos():
        """Seed verified Cloudinary showcase photos into PostgreSQL for hero background showcase."""
        from app.models.home_photo import HomePagePhoto
        from app.services.media import get_optimized_delivery_url

        photos_data = [
            {
                "title": "Documentary Field Unit",
                "cloudinary_public_id": "factbox/home_hero/vobloojextsk2ucwsmsi",
                "alt_text": "Fact Box Consult documentary director and field production unit on location",
                "caption": "On-location investigative filming across West African rural communities.",
                "display_order": 1,
            },
            {
                "title": "Audiovisual Storytelling",
                "cloudinary_public_id": "factbox/home_hero/emwghkdazvbdt153sfpp",
                "alt_text": "High-impact documentary filming and audiovisual storytelling",
                "caption": "Cinematic visual documentation capturing authentic community narratives.",
                "display_order": 2,
            },
            {
                "title": "Field Research & Evidence",
                "cloudinary_public_id": "factbox/home_hero/i53doietpynralczswjz",
                "alt_text": "Community engagement and evidence-based field research",
                "caption": "Empirical field research and structured stakeholder interviews.",
                "display_order": 3,
            },
            {
                "title": "Camera Operations & Lighting",
                "cloudinary_public_id": "factbox/home_hero/xfx85kgr4mjtucwdim4b",
                "alt_text": "Documentary camera operations and production still",
                "caption": "Broadcast-grade camera equipment and specialized production units.",
                "display_order": 4,
            },
            {
                "title": "Community Dialogue",
                "cloudinary_public_id": "factbox/home_hero/lj9nzuu4v4arvvugst1t",
                "alt_text": "Documentary fieldwork and community storytelling",
                "caption": "Participatory community media sessions documenting civic perspectives.",
                "display_order": 5,
            },
            {
                "title": "On-Location Cinematography",
                "cloudinary_public_id": "factbox/home_hero/cdouvflfzmyzjp6nknfn",
                "alt_text": "On-location documentary cinematography and lighting",
                "caption": "Cinematography capturing real-world social impact and resilience.",
                "display_order": 6,
            },
            {
                "title": "Field Production Team",
                "cloudinary_public_id": "factbox/home_hero/o6mgonjjkggcthkaqnkc",
                "alt_text": "Audiovisual media production unit and field recording",
                "caption": "Multidisciplinary production team executing field communication campaigns.",
                "display_order": 7,
            },
            {
                "title": "Investigative Research",
                "cloudinary_public_id": "factbox/home_hero/ksgxefammqhfcylffoks",
                "alt_text": "Fact Box Consult documentary investigation on location",
                "caption": "Deep-dive documentary research informing policy and advocacy.",
                "display_order": 8,
            },
            {
                "title": "Field Directing",
                "cloudinary_public_id": "factbox/home_hero/yiqhjp6bjrdqq6g6fbz2",
                "alt_text": "Documentary field camera operations and lighting crew",
                "caption": "Directing complex field productions in challenging environments.",
                "display_order": 9,
            },
            {
                "title": "High-Definition Monitoring",
                "cloudinary_public_id": "factbox/home_hero/uys8oulusdarerrqxxe9",
                "alt_text": "Field directing and high-definition video monitoring",
                "caption": "Quality control and precise visual framing during field shoots.",
                "display_order": 10,
            },
            {
                "title": "On-Location Audio & Video",
                "cloudinary_public_id": "factbox/home_hero/smgb4jqqcx8wyafbhcwh",
                "alt_text": "Cinematography and on-location sound recording in action",
                "caption": "Crystal-clear field audio capture paired with 4K cinematography.",
                "display_order": 11,
            },
            {
                "title": "Empirical Fieldwork",
                "cloudinary_public_id": "factbox/home_hero/hb8e8lltox5qgkw41uj0",
                "alt_text": "Empirical research and investigative fieldwork on site",
                "caption": "Evidence collection, survey facilitation, and documentary interviews.",
                "display_order": 12,
            },
            {
                "title": "Civic Engagement Sessions",
                "cloudinary_public_id": "factbox/home_hero/lsh4rvjzg62kntvjqw7x",
                "alt_text": "Digital media and community dialogue session",
                "caption": "Empowering local voices through participatory visual workshops.",
                "display_order": 13,
            },
            {
                "title": "Visual Documentation & Heritage",
                "cloudinary_public_id": "factbox/home_hero/oax73qwkxjsqzplsqdim",
                "alt_text": "Visual documentation and cultural heritage filming",
                "caption": "Archiving institutional memory and cultural stories with precision.",
                "display_order": 14,
                "is_active": True,
            },
            # --- Standby Reserve Pool (Slots 15 - 31) ---
            {
                "title": "Investigative Field Documentation",
                "cloudinary_public_id": "factbox/home_hero/ilumutz6z4phyb2vmleh",
                "alt_text": "Fact Box Consult documentary researchers collecting field observations",
                "caption": "Structured observational research in local development hubs.",
                "display_order": 15,
                "is_active": False,
            },
            {
                "title": "Community Consultation Forum",
                "cloudinary_public_id": "factbox/home_hero/hcdz2x3fxtztfhkuvet9",
                "alt_text": "Documentary dialogue session with local community stakeholders",
                "caption": "Grassroots stakeholder forums capturing institutional feedback.",
                "display_order": 16,
                "is_active": False,
            },
            {
                "title": "Participatory Field Research",
                "cloudinary_public_id": "factbox/home_hero/z6nidpkdiso8ygxxpuec",
                "alt_text": "Field researchers conducting structured community interviews",
                "caption": "Evidence-based qualitative research informing development programs.",
                "display_order": 17,
                "is_active": False,
            },
            {
                "title": "Audiovisual Production Setup",
                "cloudinary_public_id": "factbox/home_hero/ttktjsyf7j5dbnvqdyys",
                "alt_text": "Field camera unit preparing on-location visual recording",
                "caption": "Deploying broadcast rigs and audio gear in challenging terrain.",
                "display_order": 18,
                "is_active": False,
            },
            {
                "title": "Documentary Cinematography",
                "cloudinary_public_id": "factbox/home_hero/scpemyioaskwmoo7nlfg",
                "alt_text": "Cinematography capturing community development initiatives",
                "caption": "Visual storytelling highlighting social resilience across West Africa.",
                "display_order": 19,
                "is_active": False,
            },
            {
                "title": "Media Strategy & Dialogue",
                "cloudinary_public_id": "factbox/home_hero/a4j9fex45ramnrwumi80",
                "alt_text": "Facilitating communication and storytelling workshops",
                "caption": "Strategic media workshops designed to amplify community impact.",
                "display_order": 20,
                "is_active": False,
            },
            {
                "title": "In-Depth Field Interviews",
                "cloudinary_public_id": "factbox/home_hero/g7cupb5auuy6n6sqskkt",
                "alt_text": "Conducting in-depth stakeholder and documentary interviews",
                "caption": "Documenting authentic testimonies and empirical evidence.",
                "display_order": 21,
                "is_active": False,
            },
            {
                "title": "Visual Storytelling Unit",
                "cloudinary_public_id": "factbox/home_hero/ztowroteennxanfaz77q",
                "alt_text": "Capturing documentary photography and field stories",
                "caption": "Documenting the human impact behind institutional development initiatives.",
                "display_order": 22,
                "is_active": False,
            },
            {
                "title": "Stakeholder Consultation",
                "cloudinary_public_id": "factbox/home_hero/mwgwkyvyjkvd7ykpmd6c",
                "alt_text": "Community research gathering firsthand narratives",
                "caption": "Engaging local leaders and civic organizations in development research.",
                "display_order": 23,
                "is_active": False,
            },
            {
                "title": "Documentary Field Lighting",
                "cloudinary_public_id": "factbox/home_hero/ubxt7mjvtt2earl8hltp",
                "alt_text": "Professional location lighting and visual framing",
                "caption": "Precision cinematography lighting for high-impact documentary scenes.",
                "display_order": 24,
                "is_active": False,
            },
            {
                "title": "Institutional Research Protocol",
                "cloudinary_public_id": "factbox/home_hero/tqybvwohve0sn6pfnkf7",
                "alt_text": "Fact Box Consult researchers recording empirical development data",
                "caption": "Rigorous field documentation for international development partners.",
                "display_order": 25,
                "is_active": False,
            },
            {
                "title": "Grassroots Storytelling",
                "cloudinary_public_id": "factbox/home_hero/ugbot3wtqah57evrqal5",
                "alt_text": "Documenting community resilience and grassroots innovation",
                "caption": "Highlighting sustainable local solutions through compelling visual media.",
                "display_order": 26,
                "is_active": False,
            },
            {
                "title": "Community Field Observation",
                "cloudinary_public_id": "factbox/home_hero/ihlk1nigc6mpz6xi7uwy",
                "alt_text": "Documentary team observing institutional program impact",
                "caption": "Field monitoring capturing the tangible progress of humanitarian projects.",
                "display_order": 27,
                "is_active": False,
            },
            {
                "title": "Production Field Logistics",
                "cloudinary_public_id": "factbox/home_hero/xzi4oy5yyicj72zkkyuz",
                "alt_text": "Coordinating mobile production crews in remote locations",
                "caption": "Operational excellence supporting rapid audiovisual deployment.",
                "display_order": 28,
                "is_active": False,
            },
            {
                "title": "Development Communications",
                "cloudinary_public_id": "factbox/home_hero/np4nnhd9fgskvtopvhrh",
                "alt_text": "Translating complex social research into accessible visual media",
                "caption": "Strategic communications turning field findings into action.",
                "display_order": 29,
                "is_active": False,
            },
            {
                "title": "Environmental Field Cinematography",
                "cloudinary_public_id": "factbox/home_hero/ypl01q1pytvw4uvzmgal",
                "alt_text": "Cinematographer capturing authentic environmental documentation",
                "caption": "Capturing ecological and community challenges with journalistic rigor.",
                "display_order": 30,
                "is_active": False,
            },
            {
                "title": "Archival & Documentary Heritage",
                "cloudinary_public_id": "factbox/home_hero/l0cwq2erjuufwrjruf0w",
                "alt_text": "Comprehensive visual archiving for development partners",
                "caption": "Building enduring institutional media archives for partner organisations.",
                "display_order": 31,
                "is_active": False,
            },
        ]

        count = 0
        for p in photos_data:
            existing = HomePagePhoto.query.filter_by(cloudinary_public_id=p["cloudinary_public_id"]).first()
            secure_url = get_optimized_delivery_url(p["cloudinary_public_id"])
            is_active_val = p.get("is_active", True)
            if not existing:
                photo = HomePagePhoto(
                    title=p["title"],
                    caption=p["caption"],
                    cloudinary_public_id=p["cloudinary_public_id"],
                    secure_url=secure_url,
                    alt_text=p["alt_text"],
                    display_order=p["display_order"],
                    is_active=is_active_val,
                )
                db.session.add(photo)
                count += 1
            else:
                existing.secure_url = secure_url
                existing.title = p["title"]
                existing.caption = p["caption"]
                existing.alt_text = p["alt_text"]
                existing.display_order = p["display_order"]
                existing.is_active = is_active_val

        db.session.commit()
        click.echo(f"Successfully processed showcase photos ({count} new records added).")

    @app.cli.command("upload-showcase-to-cloudinary")
    @click.option(
        "--photos-dir",
        default=None,
        help="Custom directory containing showcase photos (defaults to app/static/img/photos)",
    )
    @click.option(
        "--upload-partners/--no-upload-partners",
        default=True,
        help="Also upload partner logos to Cloudinary",
    )
    def upload_showcase_to_cloudinary(photos_dir, upload_partners):
        """Upload local showcase photos and partner logos directly to Cloudinary and register in PostgreSQL.

        This keeps the Git repository clean while ensuring full media availability on Cloudinary.
        """
        import io
        from werkzeug.datastructures import FileStorage
        from app.models.home_photo import HomePagePhoto
        from app.models.content import PartnerLogo
        from app.services.media import (
            save_home_page_photo_safely,
            save_partner_logo_safely,
            upload_image_to_cloudinary,
        )

        cloud_name = app.config.get("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = app.config.get("CLOUDINARY_API_KEY") or os.getenv("CLOUDINARY_API_KEY")
        api_secret = app.config.get("CLOUDINARY_API_SECRET") or os.getenv("CLOUDINARY_API_SECRET")

        if not (cloud_name and api_key and api_secret) or cloud_name == "your_cloudinary_cloud_name":
            click.echo(
                "Error: Cloudinary credentials (CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET) "
                "are required to upload media to Cloudinary. Please set them in your .env or environment.",
                err=True,
            )
            sys.exit(1)

        target_dir = photos_dir or os.path.join(app.root_path, "static", "img", "photos")
        if not os.path.exists(target_dir):
            click.echo(f"Warning: Photos directory '{target_dir}' does not exist on disk.", err=True)
            target_dir = None

        showcase_items = [
            # --- Active Hero Showcase (Slots 1 - 14) ---
            {
                "filename": "photo_25.jpg",
                "title": "Documentary Field Unit",
                "alt_text": "Fact Box Consult documentary director and field production unit on location",
                "caption": "On-location investigative filming across West African rural communities.",
                "order": 1,
                "is_active": True,
            },
            {
                "filename": "photo_26.jpg",
                "title": "Audiovisual Storytelling",
                "alt_text": "High-impact documentary filming and audiovisual storytelling",
                "caption": "Cinematic visual documentation capturing authentic community narratives.",
                "order": 2,
                "is_active": True,
            },
            {
                "filename": "photo_20.jpg",
                "title": "Field Research & Evidence",
                "alt_text": "Community engagement and evidence-based field research",
                "caption": "Empirical field research and structured stakeholder interviews.",
                "order": 3,
                "is_active": True,
            },
            {
                "filename": "photo_21.jpg",
                "title": "Camera Operations & Lighting",
                "alt_text": "Documentary camera operations and production still",
                "caption": "Broadcast-grade camera equipment and specialized production units.",
                "order": 4,
                "is_active": True,
            },
            {
                "filename": "photo_07.jpg",
                "title": "Community Dialogue",
                "alt_text": "Documentary fieldwork and community storytelling",
                "caption": "Participatory community media sessions documenting civic perspectives.",
                "order": 5,
                "is_active": True,
            },
            {
                "filename": "photo_08.jpg",
                "title": "On-Location Cinematography",
                "alt_text": "On-location documentary cinematography and lighting",
                "caption": "Cinematography capturing real-world social impact and resilience.",
                "order": 6,
                "is_active": True,
            },
            {
                "filename": "photo_10.jpg",
                "title": "Field Production Team",
                "alt_text": "Audiovisual media production unit and field recording",
                "caption": "Multidisciplinary production team executing field communication campaigns.",
                "order": 7,
                "is_active": True,
            },
            {
                "filename": "photo_23.jpg",
                "title": "Investigative Research",
                "alt_text": "Fact Box Consult documentary investigation on location",
                "caption": "Deep-dive documentary research informing policy and advocacy.",
                "order": 8,
                "is_active": True,
            },
            {
                "filename": "photo_11.jpg",
                "title": "Field Directing",
                "alt_text": "Documentary field camera operations and lighting crew",
                "caption": "Directing complex field productions in challenging environments.",
                "order": 9,
                "is_active": True,
            },
            {
                "filename": "photo_12.jpg",
                "title": "High-Definition Monitoring",
                "alt_text": "Field directing and high-definition video monitoring",
                "caption": "Quality control and precise visual framing during field shoots.",
                "order": 10,
                "is_active": True,
            },
            {
                "filename": "photo_15.jpg",
                "title": "On-Location Audio & Video",
                "alt_text": "Cinematography and on-location sound recording in action",
                "caption": "Crystal-clear field audio capture paired with 4K cinematography.",
                "order": 11,
                "is_active": True,
            },
            {
                "filename": "photo_17.jpg",
                "title": "Empirical Fieldwork",
                "alt_text": "Empirical research and investigative fieldwork on site",
                "caption": "Evidence collection, survey facilitation, and documentary interviews.",
                "order": 12,
                "is_active": True,
            },
            {
                "filename": "photo_18.jpg",
                "title": "Civic Engagement Sessions",
                "alt_text": "Digital media and community dialogue session",
                "caption": "Empowering local voices through participatory visual workshops.",
                "order": 13,
                "is_active": True,
            },
            {
                "filename": "photo_22.jpg",
                "title": "Visual Documentation & Heritage",
                "alt_text": "Visual documentation and cultural heritage filming",
                "caption": "Archiving institutional memory and cultural stories with precision.",
                "order": 14,
                "is_active": True,
            },
            # --- Standby Reserve Pool (Slots 15 - 31: Auto-Promoted on Deletion) ---
            {
                "filename": "photo_01.jpg",
                "title": "Investigative Field Documentation",
                "alt_text": "Fact Box Consult documentary researchers collecting field observations",
                "caption": "Structured observational research in local development hubs.",
                "order": 15,
                "is_active": False,
            },
            {
                "filename": "photo_02.jpg",
                "title": "Community Consultation Forum",
                "alt_text": "Documentary dialogue session with local community stakeholders",
                "caption": "Grassroots stakeholder forums capturing institutional feedback.",
                "order": 16,
                "is_active": False,
            },
            {
                "filename": "photo_03.jpg",
                "title": "Participatory Field Research",
                "alt_text": "Field researchers conducting structured community interviews",
                "caption": "Evidence-based qualitative research informing development programs.",
                "order": 17,
                "is_active": False,
            },
            {
                "filename": "photo_04.jpg",
                "title": "Audiovisual Production Setup",
                "alt_text": "Field camera unit preparing on-location visual recording",
                "caption": "Deploying broadcast rigs and audio gear in challenging terrain.",
                "order": 18,
                "is_active": False,
            },
            {
                "filename": "photo_05.jpg",
                "title": "Documentary Cinematography",
                "alt_text": "Cinematography capturing community development initiatives",
                "caption": "Visual storytelling highlighting social resilience across West Africa.",
                "order": 19,
                "is_active": False,
            },
            {
                "filename": "photo_06.jpg",
                "title": "Media Strategy & Dialogue",
                "alt_text": "Facilitating communication and storytelling workshops",
                "caption": "Strategic media workshops designed to amplify community impact.",
                "order": 20,
                "is_active": False,
            },
            {
                "filename": "photo_09.jpg",
                "title": "In-Depth Field Interviews",
                "alt_text": "Conducting in-depth stakeholder and documentary interviews",
                "caption": "Documenting authentic testimonies and empirical evidence.",
                "order": 21,
                "is_active": False,
            },
            {
                "filename": "photo_13.jpg",
                "title": "Visual Storytelling Unit",
                "alt_text": "Capturing documentary photography and field stories",
                "caption": "Documenting the human impact behind institutional development initiatives.",
                "order": 22,
                "is_active": False,
            },
            {
                "filename": "photo_14.jpg",
                "title": "Stakeholder Consultation",
                "alt_text": "Community research gathering firsthand narratives",
                "caption": "Engaging local leaders and civic organizations in development research.",
                "order": 23,
                "is_active": False,
            },
            {
                "filename": "photo_16.jpg",
                "title": "Documentary Field Lighting",
                "alt_text": "Professional location lighting and visual framing",
                "caption": "Precision cinematography lighting for high-impact documentary scenes.",
                "order": 24,
                "is_active": False,
            },
            {
                "filename": "photo_19.jpg",
                "title": "Institutional Research Protocol",
                "alt_text": "Fact Box Consult researchers recording empirical development data",
                "caption": "Rigorous field documentation for international development partners.",
                "order": 25,
                "is_active": False,
            },
            {
                "filename": "photo_24.jpg",
                "title": "Grassroots Storytelling",
                "alt_text": "Documenting community resilience and grassroots innovation",
                "caption": "Highlighting sustainable local solutions through compelling visual media.",
                "order": 26,
                "is_active": False,
            },
            {
                "filename": "photo_27.jpg",
                "title": "Community Field Observation",
                "alt_text": "Documentary team observing institutional program impact",
                "caption": "Field monitoring capturing the tangible progress of humanitarian projects.",
                "order": 27,
                "is_active": False,
            },
            {
                "filename": "photo_28.jpg",
                "title": "Production Field Logistics",
                "alt_text": "Coordinating mobile production crews in remote locations",
                "caption": "Operational excellence supporting rapid audiovisual deployment.",
                "order": 28,
                "is_active": False,
            },
            {
                "filename": "photo_29.jpg",
                "title": "Development Communications",
                "alt_text": "Translating complex social research into accessible visual media",
                "caption": "Strategic communications turning field findings into action.",
                "order": 29,
                "is_active": False,
            },
            {
                "filename": "photo_30.jpg",
                "title": "Environmental Field Cinematography",
                "alt_text": "Cinematographer capturing authentic environmental documentation",
                "caption": "Capturing ecological and community challenges with journalistic rigor.",
                "order": 30,
                "is_active": False,
            },
            {
                "filename": "photo_31.jpg",
                "title": "Archival & Documentary Heritage",
                "alt_text": "Comprehensive visual archiving for development partners",
                "caption": "Building enduring institutional media archives for partner organisations.",
                "order": 31,
                "is_active": False,
            },
        ]

        # Clean up any legacy non-Cloudinary placeholder records
        legacy_deleted = HomePagePhoto.query.filter(HomePagePhoto.secure_url.like('/static%')).delete()
        if legacy_deleted:
            db.session.commit()
            click.echo(f"Cleaned up {legacy_deleted} legacy local placeholder records from database.")

        uploaded_photos = 0
        if target_dir:
            click.echo(f"Starting showcase photo upload from: {target_dir}")
            for item in showcase_items:
                filepath = os.path.join(target_dir, item["filename"])
                if not os.path.exists(filepath):
                    click.echo(f"  [Skip] {item['filename']} not found.")
                    continue

                existing = HomePagePhoto.query.filter_by(title=item["title"]).first()
                if existing:
                    # Update status and display order if needed
                    existing.display_order = item["order"]
                    existing.is_active = item["is_active"]
                    db.session.commit()
                    click.echo(f"  [Exists] '{item['title']}' active={existing.is_active} order={existing.display_order}.")
                    continue

                try:
                    with open(filepath, "rb") as f:
                        file_storage = FileStorage(
                            stream=io.BytesIO(f.read()),
                            filename=item["filename"],
                            content_type="image/jpeg",
                        )
                    photo = save_home_page_photo_safely(
                        file_storage=file_storage,
                        alt_text=item["alt_text"],
                        title=item["title"],
                        caption=item["caption"],
                        display_order=item["order"],
                        is_active=item["is_active"],
                    )
                    uploaded_photos += 1
                    status_str = "ACTIVE (Hero)" if item["is_active"] else "RESERVE (Standby)"
                    click.echo(f"  [Uploaded] '{item['title']}' [{status_str}] -> Cloudinary ID: {photo.cloudinary_public_id}")
                except Exception as e:
                    click.echo(f"  [Error] Failed to upload {item['filename']}: {e}", err=True)


        uploaded_partners = 0
        if upload_partners:
            partners_dir = os.path.join(app.root_path, "static", "img", "partners")
            partner_files = [
                ("Mercy Corps", "mercy-corps.png", "https://www.mercycorps.org", "Mercy Corps official emblem", 1),
                ("International Alert", "international-alert.jpg", "https://www.international-alert.org", "International Alert organization logo", 2),
                ("Malaria Consortium", "malaria-consortium.png", "https://www.malariaconsortium.org", "Malaria Consortium - disease control, better health", 3),
                ("GIZ", "giz.png", "https://www.giz.de", "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH", 4),
                ("Norwegian Refugee Council (NRC)", "norwegian-refugee-council.gif", "https://www.nrc.no", "Norwegian Refugee Council (NRC) official logo", 5),
                ("Public Services International (PSI)", "psi.png", "https://publicservices.international", "Public Services International (PSI) emblem", 6),
                ("Capacity 4 Sustainable Development Ltd.", "capacity-4-dev.jpg", None, "Capacity 4 Sustainable Development Ltd. logo", 7),
            ]
            if os.path.exists(partners_dir):
                click.echo(f"\nStarting partner logo upload to Cloudinary from: {partners_dir}")
                for name, filename, website, alt, order in partner_files:
                    filepath = os.path.join(partners_dir, filename)
                    if not os.path.exists(filepath):
                        continue

                    existing = PartnerLogo.query.filter_by(name=name).first()
                    if existing and existing.logo_cloudinary_public_id and existing.logo_cloudinary_public_id.startswith("factbox/"):
                        click.echo(f"  [Exists] Partner logo '{name}' already uploaded to Cloudinary.")
                        continue

                    try:
                        content_type = "image/png" if filename.endswith(".png") else "image/jpeg"
                        if filename.endswith(".gif"):
                            content_type = "image/gif"
                        with open(filepath, "rb") as f:
                            file_storage = FileStorage(
                                stream=io.BytesIO(f.read()),
                                filename=filename,
                                content_type=content_type,
                            )
                        if existing:
                            upload_meta = upload_image_to_cloudinary(file_storage, folder="factbox/partner_logos")
                            existing.logo_cloudinary_public_id = upload_meta["public_id"]
                            existing.logo_secure_url = upload_meta["secure_url"]
                            db.session.commit()
                            click.echo(f"  [Updated] Partner logo '{name}' -> Cloudinary URL: {existing.logo_secure_url}")
                        else:
                            logo = save_partner_logo_safely(
                                file_storage=file_storage,
                                name=name,
                                alt_text=alt,
                                website_url=website,
                                display_order=order,
                                is_published=True,
                            )
                            click.echo(f"  [Uploaded] Partner logo '{name}' -> Cloudinary URL: {logo.logo_secure_url}")
                        uploaded_partners += 1
                    except Exception as e:
                        click.echo(f"  [Error] Failed to upload partner logo {filename}: {e}", err=True)

        click.echo(f"\nCompleted: {uploaded_photos} showcase photos and {uploaded_partners} partner logos processed on Cloudinary.")


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

        class PhotoProxy:
            def __init__(self, p):
                self.secure_url = p.secure_url if p else ""
                self.alt_text = (
                    p.alt_text if (p and p.alt_text) else "Fact Box Consult documentary fieldwork"
                )
                self.title = p.title if (p and p.title) else "Fact Box Consult"
                self.caption = p.caption if (p and p.caption) else ""

        def get_showcase_photo(idx=0):
            from flask import g
            from app.models.home_photo import HomePagePhoto

            if not hasattr(g, "_cached_showcase_photos"):
                try:
                    photos = (
                        HomePagePhoto.query.filter_by(is_active=True)
                        .order_by(HomePagePhoto.display_order.asc(), HomePagePhoto.created_at.asc())
                        .all()
                    )
                    if not photos:
                        photos = HomePagePhoto.query.order_by(HomePagePhoto.created_at.desc()).all()
                    g._cached_showcase_photos = photos
                except Exception:
                    g._cached_showcase_photos = []

            photos = g._cached_showcase_photos
            if photos:
                return PhotoProxy(photos[idx % len(photos)])
            return PhotoProxy(None)

        return {
            "partner_logos": logos,
            "current_year": datetime.now(timezone.utc).year,
            "get_showcase_photo": get_showcase_photo,
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
