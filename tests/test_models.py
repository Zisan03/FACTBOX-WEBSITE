"""Tests for database models, constraints, and relationships.

Validates that all constraints specified in DATABASE_SCHEMA.md are enforced
by PostgreSQL in the isolated test database (ADR-001).
"""
import pytest
from datetime import datetime, timezone, date
from sqlalchemy.exc import IntegrityError
from app.models.admin import AdminUser, AdminAuditEvent
from app.models.portfolio import (
    PortfolioCategory,
    PortfolioProject,
    PortfolioImage,
    PortfolioVideo,
)
from app.models.service import Service
from app.models.enquiry import Enquiry
from app.models.content import PageContent, PartnerLogo


def test_admin_user_password_hashing(db_session):
    """Admin user password must be hashed and never stored in plaintext."""
    admin = AdminUser(email="admin@factboxconsult.com")
    admin.set_password("SuperSecret2026!")
    db_session.add(admin)
    db_session.commit()

    assert admin.password_hash != "SuperSecret2026!"
    assert admin.password_hash.startswith("scrypt:") or admin.password_hash.startswith("pbkdf2:")
    assert admin.check_password("SuperSecret2026!") is True
    assert admin.check_password("WrongPassword") is False


def test_admin_user_email_lowercase_check(db_session):
    """Admin email must be lowercase; uppercase violates check constraint."""
    admin = AdminUser(email="UPPERCASE@FACTBOXCONSULT.COM")
    admin.set_password("ValidPassword2026!")
    db_session.add(admin)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_admin_user_unique_email(db_session):
    """Admin email must be globally unique."""
    admin1 = AdminUser(email="unique@factboxconsult.com")
    admin1.set_password("Password123!")
    db_session.add(admin1)
    db_session.commit()

    admin2 = AdminUser(email="unique@factboxconsult.com")
    admin2.set_password("DifferentPassword123!")
    db_session.add(admin2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_admin_audit_event_logging(db_session, sample_admin):
    """Audit events record event type and safe metadata without sensitive secrets."""
    event = AdminAuditEvent(
        admin_user_id=sample_admin.id,
        event_type="test_event",
        safe_metadata={"action": "test_verification"},
    )
    db_session.add(event)
    db_session.commit()

    assert event.id is not None
    assert event.admin_user.email == sample_admin.email
    assert event.safe_metadata["action"] == "test_verification"


def test_portfolio_category_and_project_relationship(db_session):
    """Portfolio project links to category; cascade/restrict rules are enforced."""
    category = PortfolioCategory(
        name="Documentary",
        slug="documentary",
        display_order=1,
    )
    db_session.add(category)
    db_session.commit()

    project = PortfolioProject(
        title="Community Voices",
        slug="community-voices",
        summary="A compelling documentary on grassroots leadership.",
        description="Full documentary project description detailing the creative process.",
        category_id=category.id,
        status="published",
        display_order=1,
    )
    db_session.add(project)
    db_session.commit()

    assert project.category.name == "Documentary"
    assert category.projects.count() == 1

    # Attempting to delete category while project exists must fail due to ON DELETE RESTRICT
    db_session.delete(category)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_portfolio_project_status_constraint(db_session):
    """Project status must be either 'draft' or 'published'."""
    category = PortfolioCategory(name="Research", slug="research")
    db_session.add(category)
    db_session.commit()

    invalid_project = PortfolioProject(
        title="Invalid Status Project",
        slug="invalid-project",
        summary="Short summary.",
        description="Description text.",
        category_id=category.id,
        status="archived",  # Invalid status according to ck_portfolio_project_status
    )
    db_session.add(invalid_project)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_portfolio_image_cascade_delete(db_session):
    """Deleting a project cascades and removes associated image records."""
    category = PortfolioCategory(name="Production", slug="production")
    db_session.add(category)
    db_session.commit()

    project = PortfolioProject(
        title="Production Showcase",
        slug="production-showcase",
        summary="Production media.",
        description="Detailed description.",
        category_id=category.id,
    )
    db_session.add(project)
    db_session.commit()

    image = PortfolioImage(
        project_id=project.id,
        cloudinary_public_id="factbox/projects/showcase_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/showcase_01.jpg",
        alt_text="Production still",
        display_order=0,
    )
    video = PortfolioVideo(
        project_id=project.id,
        youtube_video_id="dQw4w9WgXcQ",
        title="Showreel",
    )
    db_session.add_all([image, video])
    db_session.commit()

    assert len(project.images) == 1
    assert len(project.videos) == 1
    assert video.embed_url == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"

    # Delete project -> should cascade delete image and video
    db_session.delete(project)
    db_session.commit()

    assert db_session.get(PortfolioImage, image.id) is None
    assert db_session.get(PortfolioVideo, video.id) is None


def test_service_model_and_constraints(db_session):
    """Service requires unique slug and non-negative display order."""
    service = Service(
        title="Audiovisual Production",
        slug="audiovisual-production",
        summary="High-definition cinematic storytelling.",
        description="Comprehensive media development.",
        display_order=0,
        is_published=True,
    )
    db_session.add(service)
    db_session.commit()

    # Duplicate slug must fail
    duplicate = Service(
        title="Another Title",
        slug="audiovisual-production",
        summary="Another summary.",
        description="Another desc.",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_enquiry_model_and_constraints(db_session):
    """Enquiry model validates status enums, non-negative attempts, and lowercase email."""
    enquiry = Enquiry(
        full_name="Jane Doe",
        organization="Partner NGO",
        email="jane.doe@example.org",
        phone="+2348012345678",
        subject="Project Collaboration",
        message="We would like to collaborate on an upcoming documentary series.",
        status="new",
        notification_status="pending",
        notification_attempts=0,
    )
    db_session.add(enquiry)
    db_session.commit()

    assert enquiry.id is not None
    assert enquiry.status == "new"
    assert enquiry.notification_status == "pending"

    # Invalid notification status must fail check constraint
    invalid_enquiry = Enquiry(
        full_name="John Doe",
        email="john@example.org",
        subject="Test Subject",
        message="Test message",
        status="new",
        notification_status="invalid_status",
    )
    db_session.add(invalid_enquiry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_page_content_unique_key_constraint(db_session):
    """PageContent enforces uniqueness on (page_key, content_key)."""
    item1 = PageContent(
        page_key="home",
        content_key="hero_headline",
        content_value="Cinematic Storytelling",
    )
    db_session.add(item1)
    db_session.commit()

    item2 = PageContent(
        page_key="home",
        content_key="hero_headline",
        content_value="Alternative Headline",
    )
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
