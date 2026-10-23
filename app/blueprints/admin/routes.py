"""Admin blueprint routes.

Handles authenticated admin access, dashboard views, session management,
and Stage 3 Content Management CRUD for:
- Portfolio Projects & Categories
- Cloudinary Media Images (upload, reorder, delete with orphan prevention)
- YouTube Video Embeds (validated ID extraction, privacy-enhanced embeds)
- Consulting Services
- Internal Draft Previews
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
from app.models.portfolio import (
    PortfolioCategory,
    PortfolioProject,
    PortfolioImage,
    PortfolioVideo,
)
from app.models.service import Service
from app.models.enquiry import Enquiry
from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo
from app.blueprints.admin.forms import (
    AdminLoginForm,
    AdminChangePasswordForm,
    AdminForgotPasswordRequestForm,
    AdminResetPasswordForm,
    PortfolioCategoryForm,
    PortfolioProjectForm,
    PortfolioImageUploadForm,
    PortfolioImageEditForm,
    PortfolioVideoForm,
    ServiceForm,
    HomePagePhotoForm,
    HomePagePhotoEditForm,
    PartnerLogoUploadForm,
    PartnerLogoEditForm,
    slugify,
)
from app.services.video import (
    extract_youtube_id,
    get_youtube_embed_url,
    get_youtube_thumbnail_url,
    VideoValidationError,
)
from app.services.media import (
    save_portfolio_image_safely,
    delete_portfolio_image_safely,
    save_home_page_photo_safely,
    delete_home_page_photo_safely,
    save_partner_logo_safely,
    delete_partner_logo_safely,
    upload_image_to_cloudinary,
    delete_image_from_cloudinary,
    get_optimized_delivery_url,
    MediaValidationError,
    CloudinaryUploadError,
)
from app.services.email import process_enquiry_notification, send_password_reset_email

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def is_safe_url(target: str | None) -> bool:
    """Validate that redirect target is on the same host to prevent open redirects."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def log_admin_audit(
    event_type: str,
    entity_type: str | None = None,
    entity_id=None,
    metadata: dict | None = None,
    user_id=None,
) -> None:
    """Record an administrative audit event."""
    effective_user_id = user_id if user_id is not None else (current_user.id if current_user.is_authenticated else None)
    audit_event = AdminAuditEvent(
        admin_user_id=effective_user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        safe_metadata=metadata or {},
    )
    db.session.add(audit_event)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


# ============================================================================
# Authentication Routes
# ============================================================================

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

            log_admin_audit("login_success", "admin_user", user.id, {"ip": request.remote_addr}, user_id=user.id)

            flash("Signed in successfully.", "success")
            next_url = request.args.get("next")
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for("admin.dashboard"))

        if user:
            log_admin_audit("login_failure", "admin_user", user.id, {"ip": request.remote_addr}, user_id=user.id)

        flash("Invalid email address or password.", "error")
        return render_template("admin/login.html", form=form), 401

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Safely terminate administrator session."""
    log_admin_audit("logout", "admin_user", current_user.id, {"ip": request.remote_addr})
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow authenticated administrator to update their password."""
    form = AdminChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Incorrect current password.", "error")
            return render_template("admin/change_password.html", form=form), 400

        current_user.set_password(form.new_password.data)
        log_admin_audit("password_changed", "admin_user", current_user.id, {"ip": request.remote_addr})
        db.session.commit()
        flash("Your password has been successfully updated.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/change_password.html", form=form)


@admin_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes")
def forgot_password():
    """Initiate administrator password recovery via secure email link."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminForgotPasswordRequestForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = AdminUser.query.filter_by(email=normalized_email).first()

        if user and user.is_active:
            token = user.get_reset_token()
            reset_url = url_for("admin.reset_password", token=token, _external=True)
            send_password_reset_email(user, reset_url)
            log_admin_audit("password_reset_requested", "admin_user", user.id, {"ip": request.remote_addr}, user_id=user.id)

        # Constant message prevents account enumeration
        flash(
            "If an active administrator account exists with that email address, a password reset link has been sent.",
            "info",
        )
        return redirect(url_for("admin.login"))

    return render_template("admin/forgot_password.html", form=form)


@admin_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Verify reset token and update administrator password."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    user = AdminUser.verify_reset_token(token)
    if not user:
        flash("The password reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("admin.forgot_password"))

    form = AdminResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        log_admin_audit("password_reset_completed", "admin_user", user.id, {"ip": request.remote_addr}, user_id=user.id)
        db.session.commit()
        flash("Your password has been successfully reset. You may now sign in.", "success")
        return redirect(url_for("admin.login"))

    return render_template("admin/reset_password.html", form=form)



# ============================================================================
# Dashboard Overview
# ============================================================================

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    """Administrator control panel overview."""
    total_projects = PortfolioProject.query.count()
    published_projects = PortfolioProject.query.filter_by(status="published").count()
    draft_projects = PortfolioProject.query.filter_by(status="draft").count()

    total_categories = PortfolioCategory.query.count()
    total_services = Service.query.count()
    published_services = Service.query.filter_by(is_published=True).count()

    total_enquiries = Enquiry.query.count()
    new_enquiries = Enquiry.query.filter_by(status="new").count()
    pending_notifications = Enquiry.query.filter_by(notification_status="pending").count()
    failed_notifications = Enquiry.query.filter_by(notification_status="failed").count()

    total_home_photos = HomePagePhoto.query.count()
    active_home_photos = HomePagePhoto.query.filter_by(is_active=True).count()

    total_partner_logos = PartnerLogo.query.count()
    published_partner_logos = PartnerLogo.query.filter_by(is_published=True).count()

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
        total_categories=total_categories,
        total_services=total_services,
        published_services=published_services,
        total_enquiries=total_enquiries,
        new_enquiries=new_enquiries,
        pending_notifications=pending_notifications,
        failed_notifications=failed_notifications,
        total_home_photos=total_home_photos,
        active_home_photos=active_home_photos,
        total_partner_logos=total_partner_logos,
        published_partner_logos=published_partner_logos,
        recent_events=recent_events,
    )



# ============================================================================
# Portfolio Categories CRUD
# ============================================================================

@admin_bp.route("/categories")
@login_required
def list_categories():
    """List all portfolio categories."""
    categories = PortfolioCategory.query.order_by(
        PortfolioCategory.display_order.asc(),
        PortfolioCategory.name.asc()
    ).all()
    return render_template("admin/categories/index.html", categories=categories)


@admin_bp.route("/categories/new", methods=["GET", "POST"])
@login_required
def new_category():
    """Create a new portfolio category."""
    form = PortfolioCategoryForm()
    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.name.data)
        if not base_slug:
            base_slug = "category"

        # Ensure slug uniqueness
        existing = PortfolioCategory.query.filter_by(slug=base_slug).first()
        if existing:
            form.slug.errors.append(f"A category with slug '{base_slug}' already exists. Please choose another.")
            return render_template("admin/categories/form.html", form=form, title="Create Category")

        category = PortfolioCategory(
            name=form.name.data.strip(),
            slug=base_slug,
            display_order=form.display_order.data or 0,
            is_active=form.is_active.data,
        )
        db.session.add(category)
        db.session.commit()

        log_admin_audit("create_category", "portfolio_category", category.id, {"name": category.name, "slug": category.slug})
        flash(f"Category '{category.name}' created successfully.", "success")
        return redirect(url_for("admin.list_categories"))

    return render_template("admin/categories/form.html", form=form, title="Create Category")


@admin_bp.route("/categories/<uuid:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    """Edit an existing portfolio category."""
    category = db.get_or_404(PortfolioCategory, category_id)
    form = PortfolioCategoryForm(obj=category)

    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.name.data)
        if not base_slug:
            base_slug = "category"

        # Ensure slug uniqueness excluding current record
        existing = PortfolioCategory.query.filter(
            PortfolioCategory.slug == base_slug,
            PortfolioCategory.id != category.id
        ).first()
        if existing:
            form.slug.errors.append(f"Another category with slug '{base_slug}' already exists.")
            return render_template("admin/categories/form.html", form=form, title=f"Edit Category: {category.name}", category=category)

        category.name = form.name.data.strip()
        category.slug = base_slug
        category.display_order = form.display_order.data or 0
        category.is_active = form.is_active.data

        db.session.commit()
        log_admin_audit("update_category", "portfolio_category", category.id, {"name": category.name, "slug": category.slug})
        flash(f"Category '{category.name}' updated successfully.", "success")
        return redirect(url_for("admin.list_categories"))

    return render_template("admin/categories/form.html", form=form, title=f"Edit Category: {category.name}", category=category)


@admin_bp.route("/categories/<uuid:category_id>/toggle-active", methods=["POST"])
@login_required
def toggle_category_active(category_id):
    """Toggle a category's active availability status."""
    category = db.get_or_404(PortfolioCategory, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    status_label = "active" if category.is_active else "inactive"
    log_admin_audit("toggle_category_active", "portfolio_category", category.id, {"is_active": category.is_active})
    flash(f"Category '{category.name}' is now {status_label}.", "success")
    return redirect(url_for("admin.list_categories"))


@admin_bp.route("/categories/<uuid:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    """Delete a category if no projects are linked to it (enforces RESTRICT)."""
    category = db.get_or_404(PortfolioCategory, category_id)
    linked_projects_count = category.projects.count()

    if linked_projects_count > 0:
        flash(
            f"Cannot delete category '{category.name}' because it contains {linked_projects_count} project(s). "
            f"Please reassign or delete the projects first.",
            "error",
        )
        return redirect(url_for("admin.list_categories"))

    db.session.delete(category)
    db.session.commit()
    log_admin_audit("delete_category", "portfolio_category", category_id, {"name": category.name})
    flash(f"Category '{category.name}' was successfully deleted.", "success")
    return redirect(url_for("admin.list_categories"))


# ============================================================================
# Portfolio Projects CRUD & Draft Isolation
# ============================================================================

@admin_bp.route("/projects")
@login_required
def list_projects():
    """List portfolio projects with status and category filtering."""
    status_filter = request.args.get("status", "all")
    category_slug = request.args.get("category")

    query = PortfolioProject.query

    if status_filter in ("draft", "published"):
        query = query.filter(PortfolioProject.status == status_filter)

    active_category = None
    if category_slug:
        active_category = PortfolioCategory.query.filter_by(slug=category_slug).first()
        if active_category:
            query = query.filter(PortfolioProject.category_id == active_category.id)

    projects = query.order_by(
        PortfolioProject.display_order.asc(),
        PortfolioProject.created_at.desc(),
    ).all()

    categories = PortfolioCategory.query.order_by(PortfolioCategory.name.asc()).all()

    return render_template(
        "admin/projects/index.html",
        projects=projects,
        categories=categories,
        status_filter=status_filter,
        active_category=active_category,
    )


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    """Create a new portfolio project."""
    form = PortfolioProjectForm()
    # Populate category dropdown with active categories
    categories = PortfolioCategory.query.filter_by(is_active=True).order_by(PortfolioCategory.display_order.asc()).all()
    form.category_id.choices = [(str(c.id), c.name) for c in categories]

    if not categories:
        flash("You must create at least one category before adding portfolio projects.", "error")
        return redirect(url_for("admin.new_category"))

    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.title.data)
        if not base_slug:
            base_slug = "project"

        existing = PortfolioProject.query.filter_by(slug=base_slug).first()
        if existing:
            form.slug.errors.append(f"A project with slug '{base_slug}' already exists. Please customize the slug.")
            return render_template("admin/projects/form.html", form=form, title="Create Project")

        published_at = datetime.now(timezone.utc) if form.status.data == "published" else None

        project = PortfolioProject(
            title=form.title.data.strip(),
            slug=base_slug,
            category_id=form.category_id.data,
            summary=form.summary.data.strip(),
            description=form.description.data.strip(),
            client_name=form.client_name.data.strip() if form.client_name.data else None,
            project_date=form.project_date.data,
            display_order=form.display_order.data or 0,
            is_featured=form.is_featured.data,
            status=form.status.data,
            published_at=published_at,
        )

        db.session.add(project)
        db.session.commit()

        log_admin_audit(
            "create_project",
            "portfolio_project",
            project.id,
            {"title": project.title, "status": project.status, "slug": project.slug},
        )
        flash(f"Project '{project.title}' created successfully.", "success")
        return redirect(url_for("admin.view_project", project_id=project.id))

    return render_template("admin/projects/form.html", form=form, title="Create Project")


@admin_bp.route("/projects/<uuid:project_id>")
@login_required
def view_project(project_id):
    """View project detail, media gallery, videos, and management actions."""
    project = db.get_or_404(PortfolioProject, project_id)
    image_form = PortfolioImageUploadForm()
    video_form = PortfolioVideoForm()

    return render_template(
        "admin/projects/detail.html",
        project=project,
        image_form=image_form,
        video_form=video_form,
        get_youtube_embed_url=get_youtube_embed_url,
        get_youtube_thumbnail_url=get_youtube_thumbnail_url,
        get_optimized_delivery_url=get_optimized_delivery_url,
    )


@admin_bp.route("/projects/<uuid:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    """Edit project information."""
    project = db.get_or_404(PortfolioProject, project_id)
    form = PortfolioProjectForm(obj=project)

    # Populate categories
    categories = PortfolioCategory.query.order_by(PortfolioCategory.display_order.asc()).all()
    form.category_id.choices = [(str(c.id), c.name) for c in categories]

    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.title.data)
        if not base_slug:
            base_slug = "project"

        existing = PortfolioProject.query.filter(
            PortfolioProject.slug == base_slug,
            PortfolioProject.id != project.id
        ).first()
        if existing:
            form.slug.errors.append(f"Another project with slug '{base_slug}' already exists.")
            return render_template("admin/projects/form.html", form=form, title=f"Edit: {project.title}", project=project)

        old_status = project.status
        new_status = form.status.data

        project.title = form.title.data.strip()
        project.slug = base_slug
        project.category_id = form.category_id.data
        project.summary = form.summary.data.strip()
        project.description = form.description.data.strip()
        project.client_name = form.client_name.data.strip() if form.client_name.data else None
        project.project_date = form.project_date.data
        project.display_order = form.display_order.data or 0
        project.is_featured = form.is_featured.data
        project.status = new_status

        if new_status == "published" and old_status != "published" and not project.published_at:
            project.published_at = datetime.now(timezone.utc)

        db.session.commit()
        log_admin_audit(
            "update_project",
            "portfolio_project",
            project.id,
            {"title": project.title, "status": project.status},
        )
        flash(f"Project '{project.title}' updated successfully.", "success")
        return redirect(url_for("admin.view_project", project_id=project.id))

    # Pre-select category on GET
    form.category_id.data = str(project.category_id)
    return render_template("admin/projects/form.html", form=form, title=f"Edit: {project.title}", project=project)


@admin_bp.route("/projects/<uuid:project_id>/toggle-status", methods=["POST"])
@login_required
def toggle_project_status(project_id):
    """Immediate toggle between Draft and Published state."""
    project = db.get_or_404(PortfolioProject, project_id)
    if project.status == "published":
        project.status = "draft"
        status_msg = "moved to Drafts (hidden from public site)"
    else:
        project.status = "published"
        if not project.published_at:
            project.published_at = datetime.now(timezone.utc)
        status_msg = "published live"

    db.session.commit()
    log_admin_audit("toggle_project_status", "portfolio_project", project.id, {"status": project.status})
    flash(f"Project '{project.title}' is now {status_msg}.", "success")
    return redirect(request.referrer or url_for("admin.view_project", project_id=project.id))


@admin_bp.route("/projects/<uuid:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    """Delete a project and its associated Cloudinary assets cleanly."""
    project = db.get_or_404(PortfolioProject, project_id)
    title = project.title

    # Snapshot public IDs before cascade delete
    images_to_check = [img.cloudinary_public_id for img in project.images]

    db.session.delete(project)
    db.session.commit()

    # Clean up Cloudinary assets if not referenced by any other record
    for public_id in images_to_check:
        remaining = PortfolioImage.query.filter_by(cloudinary_public_id=public_id).first()
        if not remaining:
            delete_image_from_cloudinary(public_id)

    log_admin_audit("delete_project", "portfolio_project", project_id, {"title": title})
    flash(f"Project '{title}' and all associated media have been deleted.", "success")
    return redirect(url_for("admin.list_projects"))


@admin_bp.route("/projects/<uuid:project_id>/preview")
@login_required
def preview_project(project_id):
    """Internal administrator draft preview reproducing the portfolio layout."""
    project = db.get_or_404(PortfolioProject, project_id)
    return render_template(
        "admin/projects/preview.html",
        project=project,
        get_youtube_embed_url=get_youtube_embed_url,
        get_optimized_delivery_url=get_optimized_delivery_url,
    )


# ============================================================================
# Cloudinary Image Management (Server-Side Upload & Safe Rollback)
# ============================================================================

@admin_bp.route("/projects/<uuid:project_id>/images/upload", methods=["POST"])
@login_required
def upload_project_image(project_id):
    """Upload an image file to Cloudinary and link to project."""
    project = db.get_or_404(PortfolioProject, project_id)
    form = PortfolioImageUploadForm()

    if form.validate_on_submit():
        try:
            image = save_portfolio_image_safely(
                project_id=project.id,
                file_storage=form.image_file.data,
                alt_text=form.alt_text.data,
                caption=form.caption.data,
                display_order=form.display_order.data or 0,
            )
            log_admin_audit(
                "upload_image",
                "portfolio_image",
                image.id,
                {"project_id": str(project.id), "public_id": image.cloudinary_public_id},
            )
            flash("Image uploaded to Cloudinary and added to project.", "success")
        except (MediaValidationError, CloudinaryUploadError) as e:
            flash(f"Upload error: {str(e)}", "error")
        except Exception as e:
            flash(f"An unexpected error occurred during upload: {str(e)}", "error")
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", "error")

    return redirect(url_for("admin.view_project", project_id=project.id))


@admin_bp.route("/projects/<uuid:project_id>/images/<uuid:image_id>/edit", methods=["POST"])
@login_required
def edit_project_image(project_id, image_id):
    """Update alt text, caption, or display order of an existing image."""
    project = db.get_or_404(PortfolioProject, project_id)
    image = PortfolioImage.query.filter_by(id=image_id, project_id=project.id).first_or_404()

    form = PortfolioImageEditForm()
    if form.validate_on_submit():
        image.alt_text = form.alt_text.data.strip()
        image.caption = form.caption.data.strip() if form.caption.data else None
        image.display_order = form.display_order.data or 0

        db.session.commit()
        log_admin_audit("update_image_metadata", "portfolio_image", image.id)
        flash("Image details updated successfully.", "success")
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{err}", "error")

    return redirect(url_for("admin.view_project", project_id=project.id))


@admin_bp.route("/projects/<uuid:project_id>/images/<uuid:image_id>/delete", methods=["POST"])
@login_required
def delete_project_image(project_id, image_id):
    """Delete an image and purge external asset if unshared."""
    project = db.get_or_404(PortfolioProject, project_id)
    success = delete_portfolio_image_safely(image_id)
    if success:
        log_admin_audit("delete_image", "portfolio_image", image_id, {"project_id": str(project.id)})
        flash("Image removed from project and cleaned from Cloudinary.", "success")
    else:
        flash("Image could not be found.", "error")

    return redirect(url_for("admin.view_project", project_id=project.id))


# ============================================================================
# YouTube Video Embeds Management
# ============================================================================

@admin_bp.route("/projects/<uuid:project_id>/videos/add", methods=["POST"])
@login_required
def add_project_video(project_id):
    """Validate YouTube URL, extract 11-char ID, and store embed."""
    project = db.get_or_404(PortfolioProject, project_id)
    form = PortfolioVideoForm()

    if form.validate_on_submit():
        try:
            clean_video_id = extract_youtube_id(form.youtube_url.data)
            video = PortfolioVideo(
                project_id=project.id,
                youtube_video_id=clean_video_id,
                title=form.title.data.strip() if form.title.data else None,
                display_order=form.display_order.data or 0,
            )
            db.session.add(video)
            db.session.commit()

            log_admin_audit(
                "add_video",
                "portfolio_video",
                video.id,
                {"project_id": str(project.id), "youtube_id": clean_video_id},
            )
            flash("YouTube video embed added successfully.", "success")
        except VideoValidationError as e:
            flash(f"Invalid YouTube URL: {str(e)}", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to record video embed: {str(e)}", "error")
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{err}", "error")

    return redirect(url_for("admin.view_project", project_id=project.id))


@admin_bp.route("/projects/<uuid:project_id>/videos/<uuid:video_id>/edit", methods=["POST"])
@login_required
def edit_project_video(project_id, video_id):
    """Update title or display order of an existing video embed."""
    project = db.get_or_404(PortfolioProject, project_id)
    video = PortfolioVideo.query.filter_by(id=video_id, project_id=project.id).first_or_404()

    form = PortfolioVideoForm()
    # On edit, youtube_url is validated again
    try:
        clean_video_id = extract_youtube_id(form.youtube_url.data)
        video.youtube_video_id = clean_video_id
        video.title = form.title.data.strip() if form.title.data else None
        video.display_order = form.display_order.data or 0
        db.session.commit()
        log_admin_audit("update_video", "portfolio_video", video.id)
        flash("Video embed updated.", "success")
    except VideoValidationError as e:
        flash(f"Invalid YouTube URL: {str(e)}", "error")

    return redirect(url_for("admin.view_project", project_id=project.id))


@admin_bp.route("/projects/<uuid:project_id>/videos/<uuid:video_id>/delete", methods=["POST"])
@login_required
def delete_project_video(project_id, video_id):
    """Remove a YouTube video embed from the project."""
    project = db.get_or_404(PortfolioProject, project_id)
    video = PortfolioVideo.query.filter_by(id=video_id, project_id=project.id).first_or_404()

    db.session.delete(video)
    db.session.commit()
    log_admin_audit("delete_video", "portfolio_video", video_id, {"project_id": str(project.id)})
    flash("Video embed removed from project.", "success")
    return redirect(url_for("admin.view_project", project_id=project.id))


# ============================================================================
# Consulting Services CRUD
# ============================================================================

@admin_bp.route("/services")
@login_required
def list_services():
    """List all consulting services."""
    services = Service.query.order_by(
        Service.display_order.asc(),
        Service.created_at.asc(),
    ).all()
    return render_template("admin/services/index.html", services=services)


@admin_bp.route("/services/new", methods=["GET", "POST"])
@login_required
def new_service():
    """Create a new consulting service."""
    form = ServiceForm()
    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.title.data)
        if not base_slug:
            base_slug = "service"

        existing = Service.query.filter_by(slug=base_slug).first()
        if existing:
            form.slug.errors.append(f"A service with slug '{base_slug}' already exists. Please customize.")
            return render_template("admin/services/form.html", form=form, title="Create Service")

        service = Service(
            title=form.title.data.strip(),
            slug=base_slug,
            summary=form.summary.data.strip(),
            description=form.description.data.strip(),
            icon_key=form.icon_key.data,
            display_order=form.display_order.data or 0,
            is_published=form.is_published.data,
        )
        db.session.add(service)
        db.session.commit()

        log_admin_audit("create_service", "service", service.id, {"title": service.title, "slug": service.slug})
        flash(f"Service '{service.title}' created successfully.", "success")
        return redirect(url_for("admin.list_services"))

    return render_template("admin/services/form.html", form=form, title="Create Service")


@admin_bp.route("/services/<uuid:service_id>/edit", methods=["GET", "POST"])
@login_required
def edit_service(service_id):
    """Edit an existing consulting service."""
    service = db.get_or_404(Service, service_id)
    form = ServiceForm(obj=service)

    if form.validate_on_submit():
        base_slug = form.slug.data.strip().lower() if form.slug.data else slugify(form.title.data)
        if not base_slug:
            base_slug = "service"

        existing = Service.query.filter(
            Service.slug == base_slug,
            Service.id != service.id
        ).first()
        if existing:
            form.slug.errors.append(f"Another service with slug '{base_slug}' already exists.")
            return render_template("admin/services/form.html", form=form, title=f"Edit: {service.title}", service=service)

        service.title = form.title.data.strip()
        service.slug = base_slug
        service.summary = form.summary.data.strip()
        service.description = form.description.data.strip()
        service.icon_key = form.icon_key.data
        service.display_order = form.display_order.data or 0
        service.is_published = form.is_published.data

        db.session.commit()
        log_admin_audit("update_service", "service", service.id, {"title": service.title, "slug": service.slug})
        flash(f"Service '{service.title}' updated successfully.", "success")
        return redirect(url_for("admin.list_services"))

    return render_template("admin/services/form.html", form=form, title=f"Edit: {service.title}", service=service)


@admin_bp.route("/services/<uuid:service_id>/toggle-publish", methods=["POST"])
@login_required
def toggle_service_publish(service_id):
    """Immediate toggle between published and unpublished state for a service."""
    service = db.get_or_404(Service, service_id)
    service.is_published = not service.is_published
    db.session.commit()
    status_label = "published live" if service.is_published else "unpublished (hidden from public Services page)"
    log_admin_audit("toggle_service_publish", "service", service.id, {"is_published": service.is_published})
    flash(f"Service '{service.title}' is now {status_label}.", "success")
    return redirect(request.referrer or url_for("admin.list_services"))


@admin_bp.route("/services/<uuid:service_id>/delete", methods=["POST"])
@login_required
def delete_service(service_id):
    """Delete a consulting service."""
    service = db.get_or_404(Service, service_id)
    title = service.title
    db.session.delete(service)
    db.session.commit()
    log_admin_audit("delete_service", "service", service_id, {"title": title})
    flash(f"Service '{title}' has been deleted.", "success")
    return redirect(url_for("admin.list_services"))


# ============================================================================
# Contact Enquiries Management (Stage 4)
# ============================================================================

@admin_bp.route("/enquiries")
@login_required
def list_enquiries():
    """List contact enquiries with review status and notification delivery filters."""
    status_filter = request.args.get("status", "").strip().lower()
    notification_filter = request.args.get("notification_status", "").strip().lower()

    query = Enquiry.query
    if status_filter in ("new", "in_review", "closed"):
        query = query.filter_by(status=status_filter)
    if notification_filter in ("pending", "sent", "failed"):
        query = query.filter_by(notification_status=notification_filter)

    enquiries = query.order_by(Enquiry.created_at.desc()).all()

    # Aggregate metric counters
    total_count = Enquiry.query.count()
    new_count = Enquiry.query.filter_by(status="new").count()
    in_review_count = Enquiry.query.filter_by(status="in_review").count()
    closed_count = Enquiry.query.filter_by(status="closed").count()
    pending_notif_count = Enquiry.query.filter_by(notification_status="pending").count()
    failed_notif_count = Enquiry.query.filter_by(notification_status="failed").count()

    return render_template(
        "admin/enquiries/list.html",
        enquiries=enquiries,
        status_filter=status_filter,
        notification_filter=notification_filter,
        total_count=total_count,
        new_count=new_count,
        in_review_count=in_review_count,
        closed_count=closed_count,
        pending_notif_count=pending_notif_count,
        failed_notif_count=failed_notif_count,
    )


@admin_bp.route("/enquiries/<uuid:enquiry_id>")
@login_required
def view_enquiry(enquiry_id):
    """View enquiry detail with safely escaped user content."""
    enquiry = db.get_or_404(Enquiry, enquiry_id)
    return render_template("admin/enquiries/detail.html", enquiry=enquiry)


@admin_bp.route("/enquiries/<uuid:enquiry_id>/status", methods=["POST"])
@login_required
def update_enquiry_status(enquiry_id):
    """Update review status of an enquiry (new, in_review, closed)."""
    enquiry = db.get_or_404(Enquiry, enquiry_id)
    new_status = request.form.get("status", "").strip().lower()

    if new_status not in ("new", "in_review", "closed"):
        flash("Invalid status specified.", "error")
        return redirect(url_for("admin.view_enquiry", enquiry_id=enquiry_id))

    old_status = enquiry.status
    enquiry.status = new_status
    db.session.commit()

    log_admin_audit(
        "update_enquiry_status",
        "enquiry",
        enquiry.id,
        {"old_status": old_status, "new_status": new_status, "email": enquiry.email},
    )
    flash(f"Enquiry status updated to '{new_status}'.", "success")
    return redirect(url_for("admin.view_enquiry", enquiry_id=enquiry_id))


@admin_bp.route("/enquiries/<uuid:enquiry_id>/retry-notification", methods=["POST"])
@login_required
def retry_enquiry_notification(enquiry_id):
    """Retry sending the internal notification email for an enquiry."""
    enquiry = db.get_or_404(Enquiry, enquiry_id)
    success, error_code = process_enquiry_notification(enquiry, is_retry=True)

    log_admin_audit(
        "retry_enquiry_notification",
        "enquiry",
        enquiry.id,
        {
            "success": success,
            "error_code": error_code,
            "attempts": enquiry.notification_attempts,
        },
    )

    if success:
        flash("Internal email notification delivered successfully.", "success")
    else:
        flash(
            f"Notification retry failed ({error_code or 'UNKNOWN'}). Enquiry remains safely preserved.",
            "error",
        )

    return redirect(url_for("admin.view_enquiry", enquiry_id=enquiry_id))


# ============================================================================
# Home Page Photos Management (Hero Background Gallery - Stage 5, ADR-010)
# ============================================================================

@admin_bp.route("/home-photos")
@login_required
def list_home_photos():
    """List all hero background slideshow photos."""
    photos = HomePagePhoto.query.order_by(
        HomePagePhoto.display_order.asc(),
        HomePagePhoto.created_at.desc(),
    ).all()
    return render_template("admin/home_photos/index.html", photos=photos)


@admin_bp.route("/home-photos/new", methods=["GET", "POST"])
@login_required
def create_home_photo():
    """Upload and configure a new hero background photo."""
    form = HomePagePhotoForm()
    if form.validate_on_submit():
        try:
            photo = save_home_page_photo_safely(
                file_storage=form.image_file.data,
                alt_text=form.alt_text.data,
                title=form.title.data,
                caption=form.caption.data,
                display_order=form.display_order.data,
                is_active=form.is_active.data,
            )
            log_admin_audit(
                "create_home_page_photo",
                "home_page_photo",
                photo.id,
                {"cloudinary_public_id": photo.cloudinary_public_id, "title": photo.title},
            )
            flash("Hero background photo uploaded successfully.", "success")
            return redirect(url_for("admin.list_home_photos"))
        except (MediaValidationError, CloudinaryUploadError) as e:
            flash(f"Upload failed: {str(e)}", "error")
        except Exception as e:
            current_app.logger.exception(f"Unexpected error uploading hero photo: {e}")
            flash("An unexpected error occurred while saving the photo.", "error")

    return render_template("admin/home_photos/form.html", form=form, photo=None)


@admin_bp.route("/home-photos/<uuid:photo_id>/edit", methods=["GET", "POST"])
@login_required
def edit_home_photo(photo_id):
    """Update metadata for an existing home page photo."""
    photo = db.get_or_404(HomePagePhoto, photo_id)
    form = HomePagePhotoEditForm(obj=photo)

    if form.validate_on_submit():
        photo.title = form.title.data.strip() if form.title.data else None
        photo.alt_text = form.alt_text.data.strip()
        photo.caption = form.caption.data.strip() if form.caption.data else None
        photo.display_order = form.display_order.data
        photo.is_active = form.is_active.data
        photo.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_admin_audit(
            "update_home_page_photo",
            "home_page_photo",
            photo.id,
            {"title": photo.title, "display_order": photo.display_order, "is_active": photo.is_active},
        )
        flash("Photo details updated successfully.", "success")
        return redirect(url_for("admin.list_home_photos"))

    return render_template("admin/home_photos/form.html", form=form, photo=photo)


@admin_bp.route("/home-photos/<uuid:photo_id>/toggle", methods=["POST"])
@login_required
def toggle_home_photo(photo_id):
    """Toggle active status of a hero background photo."""
    photo = db.get_or_404(HomePagePhoto, photo_id)
    photo.is_active = not photo.is_active
    photo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_admin_audit(
        "toggle_home_page_photo",
        "home_page_photo",
        photo.id,
        {"is_active": photo.is_active},
    )
    status_str = "activated" if photo.is_active else "deactivated"
    flash(f"Photo '{photo.title or photo.alt_text}' has been {status_str}.", "success")
    return redirect(url_for("admin.list_home_photos"))


@admin_bp.route("/home-photos/<uuid:photo_id>/delete", methods=["POST"])
@login_required
def delete_home_photo(photo_id):
    """Delete a hero background photo and remove Cloudinary asset."""
    photo = db.get_or_404(HomePagePhoto, photo_id)
    photo_title = photo.title or photo.alt_text

    success = delete_home_page_photo_safely(photo.id)
    if success:
        log_admin_audit(
            "delete_home_page_photo",
            "home_page_photo",
            photo_id,
            {"title": photo_title},
        )
        flash("Hero background photo deleted successfully.", "success")
    else:
        flash("Could not delete photo.", "error")

    return redirect(url_for("admin.list_home_photos"))


# ============================================================================
# Partner & Client Logo Management
# ============================================================================

@admin_bp.route("/partner-logos")
@login_required
def list_partner_logos():
    """List all client and partner organization logos."""
    logos = PartnerLogo.query.order_by(
        PartnerLogo.display_order.asc(),
        PartnerLogo.created_at.asc(),
    ).all()
    return render_template("admin/partner_logos/index.html", logos=logos)


@admin_bp.route("/partner-logos/upload", methods=["GET", "POST"])
@login_required
def upload_partner_logo():
    """Upload a new client/partner logo image to Cloudinary and register in DB."""
    form = PartnerLogoUploadForm()
    if form.validate_on_submit():
        try:
            logo = save_partner_logo_safely(
                file_storage=form.logo_file.data,
                name=form.name.data.strip(),
                alt_text=form.alt_text.data.strip(),
                website_url=form.website_url.data.strip() if form.website_url.data else None,
                display_order=form.display_order.data,
                is_published=form.is_published.data,
            )
            log_admin_audit(
                "upload_partner_logo",
                "partner_logo",
                logo.id,
                {"name": logo.name, "display_order": logo.display_order, "is_published": logo.is_published},
            )
            flash(f"Partner logo for '{logo.name}' uploaded successfully.", "success")
            return redirect(url_for("admin.list_partner_logos"))
        except MediaValidationError as e:
            flash(str(e), "error")
        except CloudinaryUploadError as e:
            flash(f"Media storage service error: {e}", "error")
        except Exception as e:
            flash(f"An unexpected error occurred while saving the logo: {e}", "error")

    return render_template("admin/partner_logos/form.html", form=form, logo=None)


@admin_bp.route("/partner-logos/<uuid:logo_id>/edit", methods=["GET", "POST"])
@login_required
def edit_partner_logo(logo_id):
    """Edit metadata or optionally replace image of an existing partner logo."""
    logo = db.get_or_404(PartnerLogo, logo_id)
    form = PartnerLogoEditForm(obj=logo)

    if form.validate_on_submit():
        try:
            if form.logo_file.data:
                old_public_id = logo.logo_cloudinary_public_id
                upload_meta = upload_image_to_cloudinary(form.logo_file.data, folder="factbox/partner_logos")
                logo.logo_cloudinary_public_id = upload_meta["public_id"]
                logo.logo_secure_url = upload_meta["secure_url"]
                if old_public_id:
                    delete_image_from_cloudinary(old_public_id)

            logo.name = form.name.data.strip()
            logo.website_url = form.website_url.data.strip() if form.website_url.data else None
            logo.alt_text = form.alt_text.data.strip()
            logo.display_order = form.display_order.data
            logo.is_published = form.is_published.data
            logo.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            log_admin_audit(
                "update_partner_logo",
                "partner_logo",
                logo.id,
                {"name": logo.name, "display_order": logo.display_order, "is_published": logo.is_published},
            )
            flash(f"Partner logo '{logo.name}' updated successfully.", "success")
            return redirect(url_for("admin.list_partner_logos"))
        except MediaValidationError as e:
            flash(str(e), "error")
        except CloudinaryUploadError as e:
            flash(f"Media storage service error: {e}", "error")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "error")

    return render_template("admin/partner_logos/form.html", form=form, logo=logo)


@admin_bp.route("/partner-logos/<uuid:logo_id>/toggle", methods=["POST"])
@login_required
def toggle_partner_logo(logo_id):
    """Toggle visibility status of a partner logo."""
    logo = db.get_or_404(PartnerLogo, logo_id)
    logo.is_published = not logo.is_published
    logo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_admin_audit(
        "toggle_partner_logo",
        "partner_logo",
        logo.id,
        {"is_published": logo.is_published},
    )
    status_str = "published in footer" if logo.is_published else "hidden from footer"
    flash(f"Logo '{logo.name}' is now {status_str}.", "success")
    return redirect(url_for("admin.list_partner_logos"))


@admin_bp.route("/partner-logos/<uuid:logo_id>/delete", methods=["POST"])
@login_required
def delete_partner_logo(logo_id):
    """Delete a partner logo and remove Cloudinary asset."""
    logo = db.get_or_404(PartnerLogo, logo_id)
    logo_name = logo.name

    success = delete_partner_logo_safely(logo.id)
    if success:
        log_admin_audit(
            "delete_partner_logo",
            "partner_logo",
            logo_id,
            {"name": logo_name},
        )
        flash(f"Partner logo '{logo_name}' deleted successfully.", "success")
    else:
        flash("Could not delete logo.", "error")

    return redirect(url_for("admin.list_partner_logos"))


