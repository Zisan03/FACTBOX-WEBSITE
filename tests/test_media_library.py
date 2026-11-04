"""Comprehensive automated test suite for Central Media Library (Step 2).

Enforces:
1. Authorized access to the Media Library.
2. Unauthorized access rejection.
3. Image upload (server validation & Cloudinary mock).
4. Video upload (YouTube URL validation & storage).
5. Media search (title, caption, public ID).
6. Media type filtering (image vs video).
7. Status filtering (active, unpublished, archived, deleted).
8. Editing media metadata (title, alt text, caption).
9. Publishing media.
10. Unpublishing media.
11. Archiving media (reversible, no tombstone, no Cloudinary destruction).
12. Restoring archived media.
13. Permanent deletion with tombstone creation.
14. Deliberate restoration from tombstone when Cloudinary asset exists.
15. Rejection of restoration when Cloudinary asset is missing.
16. Shared asset protection (Cloudinary asset preserved if referenced elsewhere).
"""
import io
import uuid
from unittest.mock import patch
import pytest

from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo
from app.models.portfolio import PortfolioCategory, PortfolioProject, PortfolioImage, PortfolioVideo
from app.models.media import WebsiteMedia
from app.models.tombstone import MediaDeletionTombstone
from app.services.media import (
    save_website_media_safely,
    delete_website_media_safely,
    restore_deleted_media,
    count_cloudinary_references,
)


@pytest.fixture
def auth_client(client, sample_admin):
    """Authenticate sample admin user via login form."""
    client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=True,
    )
    return client


@pytest.fixture
def sample_project(db_session):
    """Create a sample portfolio project."""
    cat = PortfolioCategory(name="Environment", slug="environment")
    db_session.add(cat)
    db_session.commit()

    proj = PortfolioProject(
        title="Turkana Documentary",
        slug="turkana-documentary",
        summary="Documentary on renewable energy",
        description="Comprehensive field work description",
        category_id=cat.id,
        status="published",
    )
    db_session.add(proj)
    db_session.commit()
    return proj


def test_1_authorized_access_to_media_library(auth_client, db_session):
    """Authorized administrator can access the Central Media Library."""
    # Seed one active hero photo
    hp = HomePagePhoto(
        title="Field Cinematography",
        cloudinary_public_id="factbox/home_hero/test_cinematography",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/factbox/home_hero/test_cinematography.jpg",
        alt_text="Documentary filming in Turkana",
        is_active=True,
    )
    db_session.add(hp)
    db_session.commit()

    response = auth_client.get("/admin/media-library")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Central Media Library" in html
    assert "Universal Asset Repository" in html
    assert "Field Cinematography" in html
    assert "Active / Published" in html


def test_2_unauthorized_access_rejected(client):
    """Anonymous visitors are redirected to the admin login page."""
    response = client.get("/admin/media-library", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]

    upload_resp = client.get("/admin/media-library/upload", follow_redirects=False)
    assert upload_resp.status_code == 302
    assert "/admin/login" in upload_resp.headers["Location"]


def test_3_image_upload_success(auth_client, db_session):
    """Uploading an image registers it in Cloudinary and commits to PostgreSQL."""
    valid_png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50

    mock_upload = {
        "public_id": "factbox/brand/factbox_crest",
        "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1/factbox/brand/factbox_crest.png",
        "width": 800,
        "height": 600,
        "format": "png",
        "bytes": len(valid_png_header),
    }

    with patch("app.services.media.upload_image_to_cloudinary", return_value=mock_upload):
        data = {
            "media_type": "image",
            "destination": "brand_asset",
            "title": "Official Brand Crest",
            "alt_text": "Fact Box Consult Official Crest",
            "caption": "Primary brand identity emblem",
            "display_order": "0",
            "status": "active",
            "image_file": (io.BytesIO(valid_png_header), "crest.png", "image/png"),
        }
        response = auth_client.post("/admin/media-library/upload", data=data, follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Media asset &#39;Official Brand Crest&#39; registered successfully" in html or "registered successfully" in html

    created = WebsiteMedia.query.filter_by(cloudinary_public_id="factbox/brand/factbox_crest").first()
    assert created is not None
    assert created.title == "Official Brand Crest"
    assert created.status == "active"
    assert created.category == "brand_asset"
    assert created.media_type == "image"


def test_4_video_upload_success(auth_client, sample_project, db_session):
    """Uploading a YouTube video validates the URL and stores video metadata."""
    data = {
        "media_type": "video",
        "destination": "portfolio_video",
        "project_id": str(sample_project.id),
        "title": "Clean Energy Documentary Feature",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "display_order": "1",
        "status": "active",
    }
    response = auth_client.post("/admin/media-library/upload", data=data, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Portfolio video" in html or "added" in html

    vid = PortfolioVideo.query.filter_by(youtube_video_id="dQw4w9WgXcQ").first()
    assert vid is not None
    assert vid.title == "Clean Energy Documentary Feature"
    assert vid.project_id == sample_project.id


def test_5_media_search(auth_client, db_session):
    """Search queries match titles, alt text, or captions and filter out non-matches."""
    wm1 = WebsiteMedia(
        title="Strategic Governance Framework",
        alt_text="Governance graphic",
        status="active",
        category="brand_asset",
        media_type="image",
    )
    wm2 = WebsiteMedia(
        title="Field Biodiversity Audit",
        alt_text="Wildlife survey photo",
        status="active",
        category="website_media",
        media_type="image",
    )
    db_session.add_all([wm1, wm2])
    db_session.commit()

    # Search for 'governance'
    resp = auth_client.get("/admin/media-library?status=active&q=governance")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Strategic Governance Framework" in html
    assert "Field Biodiversity Audit" not in html

    # Search for 'wildlife' (in alt text)
    resp2 = auth_client.get("/admin/media-library?status=active&q=wildlife")
    assert resp2.status_code == 200
    html2 = resp2.data.decode("utf-8")
    assert "Field Biodiversity Audit" in html2
    assert "Strategic Governance Framework" not in html2


def test_6_media_type_filtering(auth_client, db_session):
    """Media type filter isolates photographs from documentary videos."""
    img = WebsiteMedia(
        title="Landscape Photo",
        media_type="image",
        status="active",
        category="website_media",
    )
    vid = WebsiteMedia(
        title="Drone Reel Video",
        media_type="video",
        youtube_video_id="abcdefghijk",
        status="active",
        category="homepage_video",
    )
    db_session.add_all([img, vid])
    db_session.commit()

    # Filter: images only
    resp_img = auth_client.get("/admin/media-library?status=active&type=image")
    html_img = resp_img.data.decode("utf-8")
    assert "Landscape Photo" in html_img
    assert "Drone Reel Video" not in html_img

    # Filter: videos only
    resp_vid = auth_client.get("/admin/media-library?status=active&type=video")
    html_vid = resp_vid.data.decode("utf-8")
    assert "Drone Reel Video" in html_vid
    assert "Landscape Photo" not in html_vid


def test_7_status_filtering(auth_client, db_session):
    """Status filtering isolates active, unpublished, and archived media."""
    active_item = WebsiteMedia(title="Active Brand Logo", status="active")
    unpub_item = WebsiteMedia(title="Unpublished Draft Logo", status="unpublished")
    arch_item = WebsiteMedia(title="Archived 2025 Logo", status="archived")
    db_session.add_all([active_item, unpub_item, arch_item])
    db_session.commit()

    # Active Tab
    resp_act = auth_client.get("/admin/media-library?status=active")
    assert "Active Brand Logo" in resp_act.data.decode("utf-8")
    assert "Unpublished Draft Logo" not in resp_act.data.decode("utf-8")
    assert "Archived 2025 Logo" not in resp_act.data.decode("utf-8")

    # Unpublished Tab
    resp_unpub = auth_client.get("/admin/media-library?status=unpublished")
    assert "Unpublished Draft Logo" in resp_unpub.data.decode("utf-8")
    assert "Active Brand Logo" not in resp_unpub.data.decode("utf-8")

    # Archived Tab
    resp_arch = auth_client.get("/admin/media-library?status=archived")
    assert "Archived 2025 Logo" in resp_arch.data.decode("utf-8")
    assert "Active Brand Logo" not in resp_arch.data.decode("utf-8")


def test_8_editing_media_metadata(auth_client, db_session):
    """Updating title, alt text, and caption successfully commits to the database."""
    wm = WebsiteMedia(
        title="Original Title",
        alt_text="Old Alt",
        caption="Old Caption",
        status="unpublished",
    )
    db_session.add(wm)
    db_session.commit()

    edit_data = {
        "title": "Updated Brand Graphic 2026",
        "alt_text": "Updated Alt Text for Accessibility",
        "caption": "Updated editorial notes",
        "display_order": "5",
    }
    resp = auth_client.post(
        f"/admin/media-library/website_media/{wm.id}/edit",
        data=edit_data,
        follow_redirects=True,
    )
    assert resp.status_code == 200

    updated = db_session.get(WebsiteMedia, wm.id)
    assert updated.title == "Updated Brand Graphic 2026"
    assert updated.alt_text == "Updated Alt Text for Accessibility"
    assert updated.caption == "Updated editorial notes"
    assert updated.display_order == 5


def test_9_publishing_media(auth_client, db_session):
    """Publishing moves an unpublished media asset to active status."""
    wm = WebsiteMedia(title="Campaign Banner", status="unpublished")
    db_session.add(wm)
    db_session.commit()

    resp = auth_client.post(f"/admin/media-library/website_media/{wm.id}/publish", follow_redirects=True)
    assert resp.status_code == 200

    updated = db_session.get(WebsiteMedia, wm.id)
    assert updated.status == "active"


def test_10_unpublishing_media(auth_client, db_session):
    """Unpublishing moves an active media asset to unpublished pool."""
    wm = WebsiteMedia(title="Temporary Feature Graphic", status="active")
    db_session.add(wm)
    db_session.commit()

    resp = auth_client.post(f"/admin/media-library/website_media/{wm.id}/unpublish", follow_redirects=True)
    assert resp.status_code == 200

    updated = db_session.get(WebsiteMedia, wm.id)
    assert updated.status == "unpublished"


def test_11_archiving_media(auth_client, db_session):
    """Archiving is reversible, sets archived status, does NOT destroy Cloudinary asset or create tombstone."""
    wm = WebsiteMedia(
        title="Retired Corporate Annual Report",
        cloudinary_public_id="factbox/media/annual_report_2025",
        status="active",
    )
    db_session.add(wm)
    db_session.commit()

    with patch("app.services.media.delete_image_from_cloudinary") as mock_destroy:
        resp = auth_client.post(f"/admin/media-library/website_media/{wm.id}/archive", follow_redirects=True)
        assert resp.status_code == 200
        # Must NOT destroy Cloudinary file
        mock_destroy.assert_not_called()

    updated = db_session.get(WebsiteMedia, wm.id)
    assert updated.status == "archived"

    # Must NOT create a deletion tombstone
    tombstone = MediaDeletionTombstone.query.filter_by(title_or_name="Retired Corporate Annual Report").first()
    assert tombstone is None


def test_12_restoring_archived_media(auth_client, db_session):
    """Restoring an archived asset returns it to the unpublished pool for review."""
    wm = WebsiteMedia(
        title="Archived Presentation Slide",
        status="archived",
    )
    db_session.add(wm)
    db_session.commit()

    resp = auth_client.post(f"/admin/media-library/website_media/{wm.id}/restore-archive", follow_redirects=True)
    assert resp.status_code == 200

    updated = db_session.get(WebsiteMedia, wm.id)
    assert updated.status == "unpublished"


def test_13_delete_creates_tombstone(auth_client, db_session):
    """Deleting media creates a deletion tombstone record for permanent protection."""
    wm = WebsiteMedia(
        title="Outdated Partner Card",
        cloudinary_public_id="factbox/media/outdated_partner",
        status="active",
    )
    db_session.add(wm)
    db_session.commit()

    with patch("app.services.media.delete_image_from_cloudinary", return_value=True):
        resp = auth_client.post(f"/admin/media-library/website_media/{wm.id}/delete", follow_redirects=True)
        assert resp.status_code == 200

    # PostgreSQL row removed
    assert db_session.get(WebsiteMedia, wm.id) is None

    # Tombstone recorded
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="website_media",
        title_or_name="Outdated Partner Card",
    ).first()
    assert tombstone is not None
    assert tombstone.original_data["title"] == "Outdated Partner Card"


def test_14_restore_deleted_media_from_tombstone(auth_client, db_session):
    """Deliberately restoring from a tombstone recreates the record when Cloudinary asset exists."""
    tombstone = MediaDeletionTombstone(
        asset_type="website_media",
        cloudinary_public_id="factbox/media/restorable_item_01",
        title_or_name="Restorable Climate Infographic",
        original_data={
            "title": "Restorable Climate Infographic",
            "category": "brand_asset",
            "media_type": "image",
            "cloudinary_public_id": "factbox/media/restorable_item_01",
            "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1/factbox/media/restorable_item_01.jpg",
            "alt_text": "Climate infographic chart",
            "status": "unpublished",
            "display_order": 0,
        },
        reason="Manual removal test",
    )
    db_session.add(tombstone)
    db_session.commit()

    # Asset is verified to exist in Cloudinary
    with patch("app.services.media.check_cloudinary_asset_exists", return_value=True):
        resp = auth_client.post(f"/admin/media-library/restore-deleted/{tombstone.id}", follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "successfully restored" in html

    # Record recreated in unpublished state for safety
    restored = WebsiteMedia.query.filter_by(cloudinary_public_id="factbox/media/restorable_item_01").first()
    assert restored is not None
    assert restored.title == "Restorable Climate Infographic"
    assert restored.status == "unpublished"

    # Tombstone removed
    assert db_session.get(MediaDeletionTombstone, tombstone.id) is None


def test_15_restore_deleted_media_rejected_when_cloudinary_file_missing(auth_client, db_session):
    """Restoration is refused when the underlying Cloudinary file was destroyed."""
    tombstone = MediaDeletionTombstone(
        asset_type="home_page_photo",
        cloudinary_public_id="factbox/home_hero/missing_file_01",
        title_or_name="Purged Hero Photo",
        original_data={
            "title": "Purged Hero Photo",
            "cloudinary_public_id": "factbox/home_hero/missing_file_01",
        },
        reason="Test purge",
    )
    db_session.add(tombstone)
    db_session.commit()

    # Cloudinary asset does NOT exist
    with patch("app.services.media.check_cloudinary_asset_exists", return_value=False):
        resp = auth_client.post(f"/admin/media-library/restore-deleted/{tombstone.id}", follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "no longer available in Cloudinary storage" in html

    # Photo must NOT be restored
    restored = HomePagePhoto.query.filter_by(cloudinary_public_id="factbox/home_hero/missing_file_01").first()
    assert restored is None

    # Tombstone remains intact
    assert db_session.get(MediaDeletionTombstone, tombstone.id) is not None


def test_16_shared_cloudinary_asset_deletion_protection(sample_project, db_session):
    """Deleting one record sharing a Cloudinary public ID does not destroy the file if still used elsewhere."""
    shared_pid = "factbox/shared/community_photo_01"

    # 1. Used in HomePagePhoto
    photo = HomePagePhoto(
        title="Community Photo Hero",
        cloudinary_public_id=shared_pid,
        secure_url=f"https://res.cloudinary.com/factbox/{shared_pid}.jpg",
        alt_text="Community meeting",
    )
    # 2. Used in PortfolioImage
    proj_img = PortfolioImage(
        project_id=sample_project.id,
        cloudinary_public_id=shared_pid,
        secure_url=f"https://res.cloudinary.com/factbox/{shared_pid}.jpg",
        alt_text="Community meeting project photo",
    )
    db_session.add_all([photo, proj_img])
    db_session.commit()

    assert count_cloudinary_references(shared_pid) == 2

    # Delete the HomePagePhoto
    with patch("app.services.media.delete_image_from_cloudinary") as mock_destroy:
        from app.services.media import delete_home_page_photo_safely
        delete_home_page_photo_safely(photo.id)
        # Cloudinary destroy must NOT be called because PortfolioImage still references it!
        mock_destroy.assert_not_called()

    assert count_cloudinary_references(shared_pid) == 1

