"""Admin blueprint foundation.

Handles authenticated admin routes, content management, and enquiry reviews.
Authentication and authorization decorators will be attached in Stage 2.
"""
from flask import Blueprint, render_template

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login")
def login():
    """Admin login placeholder."""
    return render_template("admin/login.html")
