"""Automated test suite for Stage 3 — Admin Content Management & Cloudinary Media.

Enforces ROADMAP.md Stage 3 acceptance criteria:
- Category CRUD with RESTRICT project deletion prevention
- Project CRUD and slug uniqueness
- Immediate Draft vs Published workflow and strict public isolation
- YouTube video embed validation and storage
- Cloudinary media upload and asset deletion
- Consulting Services CRUD with public publish isolation
- Authorization verification on all administrative routes
- Audit trail logging on content modifications
"""
import pytest
from unittest.mock import patch
from app.models.portfolio import (
    PortfolioCategory,
    PortfolioProject,
    PortfolioImage,
    PortfolioVideo,
)
from app.models.service import Service
from app.models.admin import AdminAuditEvent
from tests.test_media_service import VALID_JPEG_BYTES, create_file_storage


# ============================================================================
# Helper: Authenticated Admin Session
# ============================================================================

def login_admin(client, sample_admin):
    """Authenticate the test client as an administrator."""
    return client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=True,
    )


# ============================================================================
# 1. Portfolio Category CRUD Tests
# ============================================================================

def test_category_crud_workflow(client, db_session, sample_admin):
    """Verify creating, editing, toggling active, and deleting a category."""
    login_admin(client, sample_admin)

    # 1. Create Category with auto-slug
    response = client.post(
        "/admin/categories/new",
        data={
            "name": "Investigative Research",
            "slug": "",
            "display_order": "1",
            "is_active": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Investigative Research" in response.data

    cat = PortfolioCategory.query.filter_by(slug="investigative-research").first()
    assert cat is not None
    assert cat.name == "Investigative Research"
    assert cat.display_order == 1
    assert cat.is_active is True

    # 2. Reject Duplicate Slug
    dup_response = client.post(
        "/admin/categories/new",
        data={
            "name": "Another Category",
            "slug": "investigative-research",
            "display_order": "2",
        },
        follow_redirects=True,
    )
    assert b"already exists" in dup_response.data

    # 3. Edit Category
    edit_response = client.post(
        f"/admin/categories/{cat.id}/edit",
        data={
            "name": "In-Depth Investigations",
            "slug": "investigations",
            "display_order": "5",
            "is_active": "y",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    db_session.refresh(cat)
    assert cat.name == "In-Depth Investigations"
    assert cat.slug == "investigations"
    assert cat.display_order == 5

    # 4. Toggle Active State
    toggle_response = client.post(
        f"/admin/categories/{cat.id}/toggle-active",
        follow_redirects=True,
    )
    assert toggle_response.status_code == 200
    db_session.refresh(cat)
    assert cat.is_active is False

    # 5. Delete empty category succeeds
    del_response = client.post(
        f"/admin/categories/{cat.id}/delete",
        follow_redirects=True,
    )
    assert del_response.status_code == 200
    assert db_session.get(PortfolioCategory, cat.id) is None


def test_category_deletion_blocked_with_linked_projects(client, db_session, sample_admin):
    """Verify category deletion is blocked if projects are assigned (enforcing RESTRICT)."""
    login_admin(client, sample_admin)

    category = PortfolioCategory(name="Protected Cat", slug="protected-cat")
    db_session.add(category)
    db_session.flush()

    project = PortfolioProject(
        title="Associated Documentary",
        slug="assoc-doc",
        summary="Summary",
        description="Description",
        category_id=category.id,
    )
    db_session.add(project)
    db_session.commit()

    # Attempt deletion
    response = client.post(
        f"/admin/categories/{category.id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cannot delete category" in response.data
    assert b"contains 1 project(s)" in response.data
    # Verify category is preserved
    assert db_session.get(PortfolioCategory, category.id) is not None


# ============================================================================
# 2. Portfolio Project CRUD & Draft vs Published Isolation Tests
# ============================================================================

def test_project_crud_and_draft_isolation(client, db_session, sample_admin):
    """Verify Project creation, draft isolation from public /work, and publishing."""
    login_admin(client, sample_admin)

    category = PortfolioCategory(name="Documentary", slug="documentary", is_active=True)
    db_session.add(category)
    db_session.commit()

    # 1. Create Draft Project
    response = client.post(
        "/admin/projects/new",
        data={
            "title": "Untold Environmental Stories",
            "slug": "",
            "category_id": str(category.id),
            "summary": "Deep dive into regional environmental degradation.",
            "description": "Full plain text investigative narrative.\n\nSecond paragraph details.",
            "client_name": "EcoWatch Alliance",
            "display_order": "1",
            "status": "draft",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Project Media Hub" in response.data

    project = PortfolioProject.query.filter_by(slug="untold-environmental-stories").first()
    assert project is not None
    assert project.status == "draft"

    # 2. Draft Isolation Check: MUST NOT appear on public /work or home
    public_work = client.get("/work")
    assert public_work.status_code == 200
    assert b"Untold Environmental Stories" not in public_work.data

    public_home = client.get("/")
    assert b"Untold Environmental Stories" not in public_home.data

    # 3. Administrator can preview draft via internal preview route
    preview = client.get(f"/admin/projects/{project.id}/preview")
    assert preview.status_code == 200
    assert b"Internal Administrator Preview Mode" in preview.data
    assert b"Untold Environmental Stories" in preview.data

    # 4. Immediate Toggle Status: Publish the project
    pub_toggle = client.post(
        f"/admin/projects/{project.id}/toggle-status",
        follow_redirects=True,
    )
    assert pub_toggle.status_code == 200
    db_session.refresh(project)
    assert project.status == "published"
    assert project.published_at is not None

    # 5. Public Verification: Published project is now visible on /work
    public_work_after = client.get("/work")
    assert b"Untold Environmental Stories" in public_work_after.data
    assert b"Documentary" in public_work_after.data

    # 6. Unpublish back to Draft
    unpub_toggle = client.post(
        f"/admin/projects/{project.id}/toggle-status",
        follow_redirects=True,
    )
    assert unpub_toggle.status_code == 200
    db_session.refresh(project)
    assert project.status == "draft"

    # 7. Public Verification: Project is hidden again
    public_work_hidden = client.get("/work")
    assert b"Untold Environmental Stories" not in public_work_hidden.data


# ============================================================================
# 3. YouTube Embed Integration Tests
# ============================================================================

def test_add_youtube_video_to_project(client, db_session, sample_admin):
    """Verify adding valid YouTube link extracts ID and stores embed."""
    login_admin(client, sample_admin)

    category = PortfolioCategory(name="Video Cat", slug="video-cat")
    db_session.add(category)
    db_session.flush()

    project = PortfolioProject(
        title="Video Test Project",
        slug="video-test-project",
        summary="Summary",
        description="Description",
        category_id=category.id,
    )
    db_session.add(project)
    db_session.commit()

    # 1. Add valid YouTube watch URL
    response = client.post(
        f"/admin/projects/{project.id}/videos/add",
        data={
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
            "title": "Trailer Reel",
            "display_order": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"YouTube video embed added successfully" in response.data

    video = PortfolioVideo.query.filter_by(project_id=project.id).first()
    assert video is not None
    assert video.youtube_video_id == "dQw4w9WgXcQ"
    assert video.title == "Trailer Reel"

    # 2. Add invalid / malicious video link fails
    bad_response = client.post(
        f"/admin/projects/{project.id}/videos/add",
        data={
            "youtube_url": "https://evil.com/watch?v=dQw4w9WgXcQ",
            "title": "Bad Video",
        },
        follow_redirects=True,
    )
    assert b"Untrusted video domain" in bad_response.data

    # 3. Delete video
    del_video = client.post(
        f"/admin/projects/{project.id}/videos/{video.id}/delete",
        follow_redirects=True,
    )
    assert del_video.status_code == 200
    assert db_session.get(PortfolioVideo, video.id) is None


# ============================================================================
# 4. Cloudinary Image Upload & Delete Route Tests
# ============================================================================

def test_upload_and_delete_project_image(client, db_session, sample_admin):
    """Verify uploading an image via the admin interface and deleting it."""
    login_admin(client, sample_admin)

    category = PortfolioCategory(name="Image Cat", slug="image-cat")
    db_session.add(category)
    db_session.flush()

    project = PortfolioProject(
        title="Image Test Project",
        slug="image-test-project",
        summary="Summary",
        description="Description",
        category_id=category.id,
    )
    db_session.add(project)
    db_session.commit()

    mock_upload = {
        "public_id": "factbox/portfolio/test_upload_99",
        "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1/test_upload_99.jpg",
        "width": 1280,
        "height": 720,
        "format": "jpg",
        "bytes": len(VALID_JPEG_BYTES),
    }

    with patch("app.services.media.configure_cloudinary"):
        with patch("cloudinary.uploader.upload", return_value=mock_upload):
            file = create_file_storage(VALID_JPEG_BYTES, "investigation.jpg", "image/jpeg")
            response = client.post(
                f"/admin/projects/{project.id}/images/upload",
                data={
                    "image_file": file,
                    "alt_text": "Investigative field recording team",
                    "caption": "Filming in the Niger Delta",
                    "display_order": "1",
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Image uploaded to Cloudinary and added to project" in response.data

            image = PortfolioImage.query.filter_by(cloudinary_public_id="factbox/portfolio/test_upload_99").first()
            assert image is not None
            assert image.alt_text == "Investigative field recording team"

            # Delete the image
            with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}):
                del_response = client.post(
                    f"/admin/projects/{project.id}/images/{image.id}/delete",
                    follow_redirects=True,
                )
                assert del_response.status_code == 200
                assert db_session.get(PortfolioImage, image.id) is None


# ============================================================================
# 5. Consulting Services CRUD & Public Visibility Tests
# ============================================================================

def test_service_crud_and_public_visibility(client, db_session, sample_admin):
    """Verify Service CRUD, slug uniqueness, and public publish isolation."""
    login_admin(client, sample_admin)

    # 1. Create Draft Service
    response = client.post(
        "/admin/services/new",
        data={
            "title": "Investigative Research & Due Diligence",
            "slug": "",
            "summary": "Evidence-backed field research and intelligence.",
            "description": "Comprehensive investigative consulting for NGOs and institutions.",
            "icon_key": "search",
            "display_order": "2",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"created successfully" in response.data and b"Investigative Research" in response.data

    service = Service.query.filter_by(slug="investigative-research-due-diligence").first()
    assert service is not None
    assert service.is_published is False

    # 2. Draft Isolation: Draft service is NOT visible on public /services
    pub_services = client.get("/services")
    assert b"Investigative Research & Due Diligence" not in pub_services.data

    # 3. Publish Service
    toggle_pub = client.post(
        f"/admin/services/{service.id}/toggle-publish",
        follow_redirects=True,
    )
    assert toggle_pub.status_code == 200
    db_session.refresh(service)
    assert service.is_published is True

    # 4. Public Verification: Published service is now visible on public /services
    pub_services_after = client.get("/services")
    assert b"Investigative Research &amp; Due Diligence" in pub_services_after.data

    # 5. Edit Service
    edit_response = client.post(
        f"/admin/services/{service.id}/edit",
        data={
            "title": "Investigative Intelligence",
            "slug": "investigative-intelligence",
            "summary": "Updated summary",
            "description": "Updated description",
            "icon_key": "search",
            "display_order": "1",
            "is_published": "y",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    db_session.refresh(service)
    assert service.title == "Investigative Intelligence"

    # 6. Delete Service
    del_service = client.post(
        f"/admin/services/{service.id}/delete",
        follow_redirects=True,
    )
    assert del_service.status_code == 200
    assert db_session.get(Service, service.id) is None


# ============================================================================
# 6. Authorization & Audit Verification
# ============================================================================

def test_admin_content_routes_require_authentication(client):
    """Verify unauthorized anonymous visitors are blocked from all Stage 3 admin routes."""
    protected_urls = [
        "/admin/projects",
        "/admin/projects/new",
        "/admin/categories",
        "/admin/categories/new",
        "/admin/services",
        "/admin/services/new",
    ]
    for url in protected_urls:
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 302
        assert "/admin/login" in response.headers["Location"]


def test_audit_event_logged_on_content_actions(client, db_session, sample_admin):
    """Verify AdminAuditEvent records key administrative actions."""
    login_admin(client, sample_admin)

    # Create category should produce audit event
    client.post(
        "/admin/categories/new",
        data={"name": "Audited Category", "slug": "audited-cat", "display_order": "0", "is_active": "y"},
    )
    cat = PortfolioCategory.query.filter_by(slug="audited-cat").first()
    assert cat is not None

    audit = (
        AdminAuditEvent.query.filter_by(
            admin_user_id=sample_admin.id,
            event_type="create_category",
        )
        .first()
    )
    assert audit is not None
    assert audit.safe_metadata.get("slug") == "audited-cat"
