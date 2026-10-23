"""Tests for Stage 5 — Public Pages & Stitch Design Implementation.

Validates ROADMAP.md Stage 5 & PRD.md criteria:
- The five approved public pages render with HTTP 200: Home, About Us, Services, Our Work, Contact Us
- Home hero background gallery queries and renders active HomePagePhoto slides (FR-04a, ADR-010)
- Inactive hero photos and draft portfolio projects are strictly isolated from public views
- About Us presents the verified company copy (RC: 7592601) and vision statement
- Services page renders published services with Stitch card styling
- Our Work renders single-page portfolio with category filter pills and media embeds
- Explicitly excluded features (individual project pages, blog, team profiles, quote page) return 404
- SEO essentials (meta title, description, h1 hierarchy) and accessibility (skip-link, alt text)
"""
import uuid
import pytest
from app.models.portfolio import PortfolioCategory, PortfolioProject, PortfolioImage
from app.models.service import Service
from app.models.home_photo import HomePagePhoto


def test_public_pages_render(client):
    """Verify that all five approved public routes render with HTTP 200."""
    routes = ["/", "/about", "/services", "/work", "/contact"]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, f"Route {route} failed with status {response.status_code}"
        assert b"FACT BOX CONSULT" in response.data


def test_security_headers_present(client):
    """Verify that mandatory security headers are attached to responses."""
    response = client.get("/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_custom_404_page(client):
    """Verify that 404 returns the branded template without error leak."""
    response = client.get("/non-existent-page-url")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data


def test_home_page_with_active_slideshow_photos(client, db_session):
    """Home hero renders active HomePagePhoto slides while excluding inactive photos (FR-04a)."""
    active_photo = HomePagePhoto(
        title="Active Field Unit",
        cloudinary_public_id="home_hero/active_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/active_01.jpg",
        alt_text="Documentary crew shooting in golden hour",
        display_order=0,
        is_active=True,
    )
    inactive_photo = HomePagePhoto(
        title="Inactive Testing Photo",
        cloudinary_public_id="home_hero/inactive_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/inactive_01.jpg",
        alt_text="Hidden photo not visible publicly",
        display_order=1,
        is_active=False,
    )
    db_session.add_all([active_photo, inactive_photo])
    db_session.commit()

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Active photo must appear in hero slideshow
    assert "https://res.cloudinary.com/factbox/image/upload/v1/active_01.jpg" in html
    assert "Documentary crew shooting in golden hour" in html

    # Inactive photo must NOT appear
    assert "https://res.cloudinary.com/factbox/image/upload/v1/inactive_01.jpg" not in html
    assert "Hidden photo not visible publicly" not in html


def test_about_page_verified_content(client):
    """About Us displays authorized company profile and RC number without placeholder claims."""
    res = client.get("/about")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "RC: 7592601" in html
    assert "Vision Statement" in html
    assert "To create credible, timely, and impactful content" in html
    assert "multicultural environment" in html
    assert "Our Approach" in html


def test_services_page_renders_published_services(client, db_session):
    """Services page renders only published services from database."""
    published_svc = Service(
        title="Investigative Documentary Production",
        slug="investigative-documentary-production",
        summary="High-impact broadcast documentary filmmaking.",
        description="Full end-to-end documentary production from research to color grading.",
        icon_key="film",
        display_order=0,
        is_published=True,
    )
    draft_svc = Service(
        title="Internal Unreleased Service",
        slug="internal-unreleased-service",
        summary="Not ready for public offering.",
        description="Draft service description.",
        icon_key="briefcase",
        display_order=1,
        is_published=False,
    )
    db_session.add_all([published_svc, draft_svc])
    db_session.commit()

    res = client.get("/services")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "Investigative Documentary Production" in html
    assert "High-impact broadcast documentary filmmaking" in html
    # Draft service must be isolated
    assert "Internal Unreleased Service" not in html


def test_work_page_draft_isolation_and_filters(client, db_session):
    """Our Work page displays published projects with category filters while excluding drafts."""
    cat = PortfolioCategory(name="Public Health", slug="public-health", display_order=0, is_active=True)
    db_session.add(cat)
    db_session.commit()

    pub_proj = PortfolioProject(
        title="Maternal Health Community Report",
        slug="maternal-health-community-report",
        summary="Documenting grassroots healthcare delivery in rural clinics.",
        description="Comprehensive documentary investigation into maternal health outcomes.",
        category_id=cat.id,
        client_name="Health Development Initiative",
        status="published",
        display_order=0,
    )
    draft_proj = PortfolioProject(
        title="Confidential Unreleased Investigation",
        slug="confidential-unreleased-investigation",
        summary="Internal confidential draft.",
        description="Not for public release.",
        category_id=cat.id,
        status="draft",
        display_order=1,
    )
    db_session.add_all([pub_proj, draft_proj])
    db_session.commit()

    # Add image to published project
    img = PortfolioImage(
        project_id=pub_proj.id,
        cloudinary_public_id="factbox/portfolio/health_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/health_01.jpg",
        alt_text="Healthcare worker administering vaccine",
        display_order=0,
    )
    db_session.add(img)
    db_session.commit()

    res = client.get("/work")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Published project and category filter must be present
    assert "Maternal Health Community Report" in html
    assert "Health Development Initiative" in html
    assert "Public Health" in html
    assert "https://res.cloudinary.com/factbox/image/upload/v1/health_01.jpg" in html

    # Draft project must NEVER appear
    assert "Confidential Unreleased Investigation" not in html


def test_no_individual_project_detail_routes(client, db_session):
    """Individual project detail routes are explicitly out of scope (PRD Section 5 / ADR-009)."""
    cat = PortfolioCategory(name="Advocacy", slug="advocacy", is_active=True)
    db_session.add(cat)
    db_session.commit()

    proj = PortfolioProject(
        title="Advocacy Project",
        slug="advocacy-project",
        summary="Advocacy summary",
        description="Full description",
        category_id=cat.id,
        status="published",
    )
    db_session.add(proj)
    db_session.commit()

    # Attempting to access an individual project page must return 404
    assert client.get(f"/work/{proj.slug}").status_code == 404
    assert client.get(f"/work/{proj.id}").status_code == 404
    assert client.get(f"/projects/{proj.slug}").status_code == 404


def test_excluded_pages_return_404(client):
    """Features deferred beyond V1 must not be accessible (PRD Section 5)."""
    excluded_routes = [
        "/blog",
        "/team",
        "/our-team",
        "/quote",
        "/request-a-quote",
        "/clients",
        "/partners",
        "/clients-partners",
        "/register",
        "/signup",
    ]
    for route in excluded_routes:
        res = client.get(route)
        assert res.status_code == 404, f"Excluded route '{route}' should not exist (status {res.status_code})"


def test_contact_page_details_and_form(client):
    """Contact page displays office location (Jos, Plateau State) and durable contact form."""
    res = client.get("/contact")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "Jos, Plateau State, Nigeria" in html
    assert "RC: 7592601" in html
    assert "name=\"full_name\"" in html
    assert "name=\"email\"" in html
    assert "name=\"message\"" in html
    assert "Submit Enquiry" in html



def test_seo_and_accessibility_essentials(client):
    """Each page must include descriptive titles, meta descriptions, semantic h1, and skip navigation."""
    pages = ["/", "/about", "/services", "/work", "/contact"]
    for p in pages:
        res = client.get(p)
        assert res.status_code == 200
        html = res.get_data(as_text=True)

        assert "<title>" in html
        assert "Fact Box Consult" in html
        assert "<meta name=\"description\"" in html
        assert "Skip to main content" in html
        assert "<h1" in html, f"Page {p} missing semantic <h1> heading"
        assert "mobile-drawer" in html
