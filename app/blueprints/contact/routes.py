"""Contact enquiry blueprint.

Handles enquiry form rendering and submission.
Enforces:
- ADR-006 & PRD FR-05: Enquiries are committed to PostgreSQL before email delivery is attempted
- Server-side validation, CSRF, honeypot spam protection, and rate limiting
- Safe visitor feedback without leaking email delivery failures
"""
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from app.extensions import db, limiter
from app.models.enquiry import Enquiry
from app.blueprints.contact.forms import ContactEnquiryForm
from app.services.email import process_enquiry_notification

contact_bp = Blueprint("contact", __name__, url_prefix="/contact")


@contact_bp.route("", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def index():
    """Render contact page and process enquiry submissions."""
    form = ContactEnquiryForm()

    if form.validate_on_submit():
        # Check honeypot field for spam bot rejection
        if form.company_website.data and form.company_website.data.strip():
            current_app.logger.warning(
                "Contact submission blocked by honeypot (remote_ip=%s)",
                request.remote_addr,
            )
            # Silently swallow spam submission while showing standard success feedback
            flash(
                "Thank you for reaching out! Your message has been received, and our team will get back to you shortly.",
                "success",
            )
            return redirect(url_for("contact.index"))

        # Normalize and construct enquiry
        enquiry = Enquiry(
            full_name=form.full_name.data.strip(),
            organization=form.organization.data.strip() if form.organization.data else None,
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip() if form.phone.data else None,
            subject=form.subject.data.strip(),
            message=form.message.data.strip(),
            status="new",
            notification_status="pending",
            notification_attempts=0,
        )

        # 1. Commit to PostgreSQL first (ADR-006)
        try:
            db.session.add(enquiry)
            db.session.commit()
            current_app.logger.info("Enquiry %s committed to PostgreSQL successfully", enquiry.id)
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error("Failed to commit enquiry to database: %s", exc)
            flash(
                "We encountered a temporary server error while saving your message. Please try again shortly.",
                "error",
            )
            return render_template("contact/index.html", form=form), 500

        # 2. Attempt email notification AFTER successful database commit
        process_enquiry_notification(enquiry)

        # 3. Always confirm reception to visitor (email failure does not invalidate enquiry)
        flash(
            "Thank you for reaching out! Your message has been received, and our team will get back to you shortly.",
            "success",
        )
        return redirect(url_for("contact.index"))

    # Return 400 status if POST failed validation
    status_code = 400 if request.method == "POST" and not form.validate() else 200
    return render_template("contact/index.html", form=form), status_code
