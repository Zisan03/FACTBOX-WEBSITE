"""Contact enquiry blueprint.

Handles enquiry form rendering and submission.
Enquiries must be persisted to PostgreSQL before email delivery is attempted (FR-05).
"""
from flask import Blueprint, render_template

contact_bp = Blueprint("contact", __name__, url_prefix="/contact")


@contact_bp.route("", methods=["GET"])
def index():
    """Render contact page."""
    return render_template("contact/index.html")
