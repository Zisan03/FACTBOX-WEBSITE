"""Tests for authenticated admin registration mechanism for Strategic Storytelling video.

Verifies:
1. Authenticated admin can trigger sync via POST /admin/media-library/sync-homepage-video.
2. Canonical CURATED_HOMEPAGE_VIDEO is the single source of truth for metadata.
3. Operation is idempotent and does not create duplicate records on repeated calls.
4. Inactive/unpublished existing video is reactivated to 'active'.
5. Anonymous requests are rejected (redirect to /admin/login).
6. GET requests are rejected (405 Method Not Allowed).
7. Admin CSRF protection is enforced when enabled.
8. Deletion tombstones are respected; admin sync will not resurrect deleted videos.
9. Audit logs (AdminAuditEvent) are recorded for both success and rejection.
10. Unrelated media in the database remains unaffected.
11. UI button is rendered on the Central Media Library admin index page.
"""
import pytest
from app.models.media import WebsiteMedia
from app.models.home_photo import HomePagePhoto
from app.models.tombstone import MediaDeletionTombstone
from app.models.admin import AdminAuditEvent
from app.services.media import CURATED_HOMEPAGE_VIDEO, sync_curated_homepage_video


@pytest.fixture
def auth_client(client, sample_admin):
    """Authenticate sample admin user."""
    client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=True,
    )
    return client


def test_authenticated_admin_syncs_homepage_video_successfully(auth_client, db_session):
    """Authenticated administrator can sync canonical homepage video via POST."""
    # Ensure no video exists initially
    assert WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).count() == 0

    response = auth_client.post(
        "/admin/media-library/sync-homepage-video",
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify WebsiteMedia created with canonical single-source-of-truth values
    video = WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).first()
    assert video is not None
    assert video.title == CURATED_HOMEPAGE_VIDEO["title"]
    assert video.category == CURATED_HOMEPAGE_VIDEO["category"]
    assert video.media_type == CURATED_HOMEPAGE_VIDEO["media_type"]
    assert video.secure_url == CURATED_HOMEPAGE_VIDEO["secure_url"]
    assert video.alt_text == CURATED_HOMEPAGE_VIDEO["alt_text"]
    assert video.caption == CURATED_HOMEPAGE_VIDEO["caption"]
    assert video.status == "active"
    assert video.display_order == CURATED_HOMEPAGE_VIDEO["display_order"]

    # Verify flash message in HTML
    html = response.get_data(as_text=True)
    assert "registered successfully in Central Media Library" in html

    # Verify audit log entry
    audit = AdminAuditEvent.query.filter_by(event_type="sync_homepage_video").first()
    assert audit is not None
    assert audit.entity_type == "website_media"


def test_admin_sync_homepage_video_is_idempotent(auth_client, db_session):
    """Repeated sync invocations do not duplicate the record."""
    # First sync
    res1 = auth_client.post("/admin/media-library/sync-homepage-video", follow_redirects=True)
    assert res1.status_code == 200
    assert WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).count() == 1

    # Second sync
    res2 = auth_client.post("/admin/media-library/sync-homepage-video", follow_redirects=True)
    assert res2.status_code == 200
    # Still exactly one record
    assert WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).count() == 1
    html = res2.get_data(as_text=True)
    assert "already registered and active" in html


def test_admin_sync_homepage_video_activates_inactive_record(auth_client, db_session):
    """If the curated video is currently unpublished, syncing reactivates it."""
    video = WebsiteMedia(
        title=CURATED_HOMEPAGE_VIDEO["title"],
        category=CURATED_HOMEPAGE_VIDEO["category"],
        media_type=CURATED_HOMEPAGE_VIDEO["media_type"],
        cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"],
        secure_url=CURATED_HOMEPAGE_VIDEO["secure_url"],
        alt_text=CURATED_HOMEPAGE_VIDEO["alt_text"],
        caption=CURATED_HOMEPAGE_VIDEO["caption"],
        status="unpublished",
        display_order=CURATED_HOMEPAGE_VIDEO["display_order"],
    )
    db_session.add(video)
    db_session.commit()

    assert video.status == "unpublished"

    res = auth_client.post("/admin/media-library/sync-homepage-video", follow_redirects=True)
    assert res.status_code == 200

    db_session.refresh(video)
    assert video.status == "active"


def test_anonymous_user_sync_rejected(client, db_session):
    """Anonymous visitors cannot trigger video sync and are redirected to login."""
    res = client.post("/admin/media-library/sync-homepage-video", follow_redirects=False)
    assert res.status_code == 302
    assert "/admin/login" in res.headers["Location"]

    # Verify no record created
    assert WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).first() is None


def test_get_method_not_allowed(auth_client, client):
    """GET requests to the sync endpoint return 405 Method Not Allowed."""
    # Authenticated admin GET
    res_auth = auth_client.get("/admin/media-library/sync-homepage-video")
    assert res_auth.status_code == 405

    # Anonymous GET
    res_anon = client.get("/admin/media-library/sync-homepage-video")
    assert res_anon.status_code == 405


def test_sync_homepage_video_respects_deletion_tombstone(auth_client, db_session):
    """Admin sync endpoint respects deletion tombstones and will not resurrect deleted video."""
    tombstone = MediaDeletionTombstone(
        asset_type="website_media",
        cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"],
        title_or_name=CURATED_HOMEPAGE_VIDEO["title"],
        reason="Deliberately deleted by admin",
    )
    db_session.add(tombstone)
    db_session.commit()
    tombstone_id = tombstone.id

    res = auth_client.post("/admin/media-library/sync-homepage-video", follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "protected by an administrator deletion tombstone" in html

    # Verify video was NOT recreated
    assert WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).first() is None

    # Verify tombstone remains intact
    assert db_session.get(MediaDeletionTombstone, tombstone_id) is not None

    # Verify audit log recorded rejection
    audit = AdminAuditEvent.query.filter_by(event_type="sync_homepage_video_rejected").first()
    assert audit is not None


def test_sync_homepage_video_csrf_enforced(app, sample_admin, db_session):
    """Sync endpoint enforces CSRF protection when enabled."""
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        csrf_client = app.test_client()
        # Login without CSRF checking disabled would need csrf token; test raw POST without token
        res = csrf_client.post("/admin/media-library/sync-homepage-video")
        # Must reject with 400 Bad Request
        assert res.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_sync_does_not_affect_unrelated_media(auth_client, db_session):
    """Curated video sync leaves unrelated existing media assets completely untouched."""
    photo = HomePagePhoto(
        title="Unrelated Hero Photo",
        cloudinary_public_id="factbox/home_hero/unrelated_photo",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/factbox/home_hero/unrelated_photo.jpg",
        alt_text="Unrelated Hero",
        is_active=True,
    )
    db_session.add(photo)
    db_session.commit()
    photo_id = photo.id

    res = auth_client.post("/admin/media-library/sync-homepage-video", follow_redirects=True)
    assert res.status_code == 200

    db_session.refresh(photo)
    assert photo.title == "Unrelated Hero Photo"
    assert photo.is_active is True
    assert photo.cloudinary_public_id == "factbox/home_hero/unrelated_photo"


def test_button_rendered_in_admin_media_library_page(auth_client):
    """The Register Homepage Video button is rendered in the admin media library header."""
    res = auth_client.get("/admin/media-library")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'action="/admin/media-library/sync-homepage-video"' in html
    assert 'Register Homepage Video' in html
    assert 'name="csrf_token"' in html

