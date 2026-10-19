"""Admin blueprint routes.

Handles authenticated admin access, dashboard views, and session management.
Enforces ADR-001, ADR-009, and ROADMAP Stage 2 specifications:
- Secure login with rate-limiting and audit logging
- Safe redirect verification preventing open redirects
- Protected dashboard requiring authentication
"""
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, limiter
from app.models.admin import AdminUser, AdminAuditEvent
from app.models.portfolio import PortfolioProject
from app.models.service import Service
from app.models.enquiry import Enquiry
from app.blueprints.admin.forms import AdminLoginForm

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def is_safe_url(target: str | None) -> bool:
    """Validate that redirect target is on the same host to prevent open redirects."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """Administrator sign in route with rate limiting and audit logging."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = AdminUser.query.filter_by(email=normalized_email).first()

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(timezone.utc)

            audit_event = AdminAuditEvent(
                admin_user_id=user.id,
                event_type="login_success",
                safe_metadata={"ip": request.remote_addr},
            )
            db.session.add(audit_event)
            db.session.commit()

            flash("Signed in successfully.", "success")
            next_url = request.args.get("next")
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for("admin.dashboard"))

        # Audit failed login attempt if user exists
        if user:
            audit_event = AdminAuditEvent(
                admin_user_id=user.id,
                event_type="login_failure",
                safe_metadata={"ip": request.remote_addr},
            )
            db.session.add(audit_event)
            db.session.commit()

        flash("Invalid email address or password.", "error")
        return render_template("admin/login.html", form=form), 401

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Safely terminate administrator session."""
    if current_user.is_authenticated:
        audit_event = AdminAuditEvent(
            admin_user_id=current_user.id,
            event_type="logout",
            safe_metadata={"ip": request.remote_addr},
        )
        db.session.add(audit_event)
        db.session.commit()

    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    """Administrator control panel overview."""
    total_projects = PortfolioProject.query.count()
    published_projects = PortfolioProject.query.filter_by(status="published").count()
    draft_projects = PortfolioProject.query.filter_by(status="draft").count()

    total_services = Service.query.count()
    published_services = Service.query.filter_by(is_published=True).count()

    total_enquiries = Enquiry.query.count()
    new_enquiries = Enquiry.query.filter_by(status="new").count()
    pending_notifications = Enquiry.query.filter_by(notification_status="pending").count()

    recent_events = (
        AdminAuditEvent.query.order_by(AdminAuditEvent.occurred_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_projects=total_projects,
        published_projects=published_projects,
        draft_projects=draft_projects,
        total_services=total_services,
        published_services=published_services,
        total_enquiries=total_enquiries,
        new_enquiries=new_enquiries,
        pending_notifications=pending_notifications,
        recent_events=recent_events,
    )
