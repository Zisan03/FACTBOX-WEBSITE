"""Public website blueprint.

Handles the approved public pages: Home, About Us, Services, and Our Work.
"""
from flask import Blueprint, render_template

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    """Home page."""
    return render_template("public/home.html")


@public_bp.route("/about")
def about():
    """About Us page."""
    return render_template("public/about.html")


@public_bp.route("/services")
def services():
    """Services page."""
    return render_template("public/services.html")


@public_bp.route("/work")
def work():
    """Our Work (single portfolio page)."""
    return render_template("public/work.html")
