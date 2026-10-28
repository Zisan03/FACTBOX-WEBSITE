"""Public website blueprint.

Handles the approved public pages: Home, About Us, Services, and Our Work.
Enforces draft isolation: only published projects and active published services
are queried and displayed to public visitors.
"""
from flask import Blueprint, render_template
from app.models.portfolio import PortfolioProject, PortfolioCategory
from app.models.service import Service
from app.models.home_photo import HomePagePhoto
from app.services.video import get_youtube_embed_url
from app.services.media import get_optimized_delivery_url
from app.constants import ORGANIZATIONS, match_client_to_org

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    """Home page displaying hero photo slideshow, featured work, and active services."""
    home_photos = (
        HomePagePhoto.query.filter_by(is_active=True)
        .order_by(HomePagePhoto.display_order.asc(), HomePagePhoto.created_at.desc())
        .all()
    )
    featured_projects = (
        PortfolioProject.query.filter_by(status="published", is_featured=True)
        .order_by(PortfolioProject.display_order.asc(), PortfolioProject.published_at.desc())
        .limit(3)
        .all()
    )
    services = (
        Service.query.filter_by(is_published=True)
        .order_by(Service.display_order.asc())
        .limit(4)
        .all()
    )
    return render_template(
        "public/home.html",
        home_photos=home_photos,
        featured_projects=featured_projects,
        services=services,
        get_optimized_delivery_url=get_optimized_delivery_url,
    )



@public_bp.route("/about")
def about():
    """About Us page."""
    return render_template("public/about.html")


@public_bp.route("/services")
def services():
    """Services page displaying all published consulting services."""
    home_photos = (
        HomePagePhoto.query.filter_by(is_active=True)
        .order_by(HomePagePhoto.display_order.asc(), HomePagePhoto.created_at.desc())
        .all()
    )
    services_list = (
        Service.query.filter_by(is_published=True)
        .order_by(Service.display_order.asc())
        .all()
    )
    return render_template(
        "public/services.html", 
        services=services_list,
        home_photos=home_photos,
    )


@public_bp.route("/work")
def work():
    """Our Work single-page portfolio with category and organization filtering (drafts excluded)."""
    # Strict draft isolation: query only status == 'published'
    published_projects = (
        PortfolioProject.query.filter_by(status="published")
        .order_by(PortfolioProject.display_order.asc(), PortfolioProject.published_at.desc())
        .all()
    )

    # Annotate projects with matched organization metadata
    for p in published_projects:
        matched = match_client_to_org(p.client_name)
        p.matched_org = matched
        p.org_slug = matched["slug"] if matched else "other"

    # Categories with at least one published project
    category_ids = {p.category_id for p in published_projects}
    categories = (
        PortfolioCategory.query.filter(PortfolioCategory.id.in_(category_ids), PortfolioCategory.is_active == True)
        .order_by(PortfolioCategory.display_order.asc(), PortfolioCategory.name.asc())
        .all()
    ) if category_ids else []

    return render_template(
        "public/work.html",
        projects=published_projects,
        categories=categories,
        organizations=ORGANIZATIONS,
        get_youtube_embed_url=get_youtube_embed_url,
        get_optimized_delivery_url=get_optimized_delivery_url,
    )
