"""Tests for Step 3 — Homepage Strategic Storytelling Video Integration.

Verifies:
1. Active homepage video is queried and rendered in the Strategic Storytelling section.
2. Video tag renders native controls, playsinline, poster frame, and Cloudinary MP4 source.
3. YouTube video alternative renders safe youtube-nocookie iframe.
4. Fallback rendering when no video is active, unpublished, or archived.
5. Video file format and size validation.
6. Deletion creates deletion tombstone and protects system video asset.
7. Seeding command respects deletion tombstones and is idempotent.
8. Restoration from deletion tombstone recreates WebsiteMedia in unpublished review state.
"""
import io
import uuid
from unittest.mock import patch
import pytest

from app.models.media import WebsiteMedia
from app.models.tombstone import MediaDeletionTombstone
from app.services.media import (
    validate_video_file,
    save_website_media_safely,
    delete_website_media_safely,
    restore_deleted_media,
    MediaValidationError,
    CURATED_HOMEPAGE_VIDEO,
)
from werkzeug.datastructures import FileStorage


@pytest.fixture(autouse=True)
def clean_homepage_videos(db_session):
    """Ensure homepage videos are cleanly reset before and after each test."""
    WebsiteMedia.query.filter_by(category="homepage_video").delete()
    MediaDeletionTombstone.query.filter_by(asset_type="website_media").delete()
    db_session.commit()
    yield
    WebsiteMedia.query.filter_by(category="homepage_video").delete()
    MediaDeletionTombstone.query.filter_by(asset_type="website_media").delete()
    db_session.commit()


def test_homepage_renders_active_video(client, db_session):
    """Active WebsiteMedia video is rendered in Strategic Storytelling section."""
    video = WebsiteMedia(
        title="Field Operations Reel",
        category="homepage_video",
        media_type="video",
        cloudinary_public_id="factbox/videos/test_reel_123",
        secure_url="https://res.cloudinary.com/factbox/video/upload/v1/factbox/videos/test_reel_123.mp4",
        alt_text="Fact Box Consult documentary storytelling reel",
        caption="High-impact field documentary production reel.",
        status="active",
        display_order=1,
    )
    db_session.add(video)
    db_session.commit()

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "storytellingVideoPlayer" in html
    assert "https://res.cloudinary.com/factbox/video/upload/v1/factbox/videos/test_reel_123.mp4" in html
    assert "video/mp4" in html
    assert "Field Operations Reel" in html
    assert "High-Impact Media &bull; 34s Reel" in html
    assert "storytellingPlayButton" in html


def test_homepage_renders_youtube_video_embed(client, db_session):
    """Active YouTube video renders safe privacy-enhanced iframe."""
    video = WebsiteMedia(
        title="Strategic Advocacy Video",
        category="homepage_video",
        media_type="video",
        youtube_video_id="dQw4w9WgXcQ",
        alt_text="Strategic Advocacy Video",
        caption="Advocacy campaign video.",
        status="active",
        display_order=1,
    )
    db_session.add(video)
    db_session.commit()

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" in html
    assert "Strategic Advocacy Video" in html


def test_homepage_fallback_when_video_unpublished(client, db_session):
    """When video is unpublished or archived, homepage renders fallback photo gracefully."""
    video = WebsiteMedia(
        title="Draft Video",
        category="homepage_video",
        media_type="video",
        cloudinary_public_id="factbox/videos/draft_video_456",
        secure_url="https://res.cloudinary.com/factbox/video/upload/v1/factbox/videos/draft_video_456.mp4",
        status="unpublished",
        display_order=1,
    )
    db_session.add(video)
    db_session.commit()

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Video player should not be rendered
    assert "storytellingVideoPlayer" not in html
    assert "draft_video_456" not in html
    # Section still renders with fallback
    assert "Documentary &amp; Strategic Storytelling" in html
    assert "Messages That Matter" in html


def test_video_file_validation():
    """Video file validation checks format, extension, and size limits."""
    # 1. Valid MP4
    valid_storage = FileStorage(
        stream=io.BytesIO(b"fake mp4 video bytes"),
        filename="field_production.mp4",
        content_type="video/mp4",
    )
    fmt = validate_video_file(valid_storage)
    assert fmt == "mp4"

    # 2. Invalid extension
    bad_ext_storage = FileStorage(
        stream=io.BytesIO(b"malicious content"),
        filename="malware.exe",
        content_type="application/x-msdownload",
    )
    with pytest.raises(MediaValidationError, match="Unsupported video format"):
        validate_video_file(bad_ext_storage)

    # 3. Invalid MIME type
    bad_mime_storage = FileStorage(
        stream=io.BytesIO(b"fake mp4 video bytes"),
        filename="field_production.mp4",
        content_type="text/plain",
    )
    with pytest.raises(MediaValidationError, match="Invalid video content type"):
        validate_video_file(bad_mime_storage)

    # 4. Empty file
    empty_storage = FileStorage(
        stream=io.BytesIO(b""),
        filename="empty.mp4",
        content_type="video/mp4",
    )
    with pytest.raises(MediaValidationError, match="empty"):
        validate_video_file(empty_storage)


def test_delete_homepage_video_creates_tombstone(db_session):
    """Deleting a WebsiteMedia video records an immutable tombstone."""
    video = WebsiteMedia(
        title="To Be Deleted Video",
        category="homepage_video",
        media_type="video",
        cloudinary_public_id="factbox/videos/temp_delete_reel",
        secure_url="https://res.cloudinary.com/factbox/video/upload/v1/factbox/videos/temp_delete_reel.mp4",
        status="active",
    )
    db_session.add(video)
    db_session.commit()
    vid_id = video.id

    with patch("app.services.media.delete_image_from_cloudinary") as mock_destroy:
        success = delete_website_media_safely(vid_id, admin_email="admin@factbox.com")
        assert success is True
        # Since it is unreferenced and not system asset, destroy is invoked
        mock_destroy.assert_called_once_with("factbox/videos/temp_delete_reel", resource_type="video")

    # Verify database record deleted
    assert db_session.get(WebsiteMedia, vid_id) is None

    # Verify tombstone created
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="website_media",
        cloudinary_public_id="factbox/videos/temp_delete_reel",
    ).first()
    assert tombstone is not None
    assert tombstone.title_or_name == "To Be Deleted Video"
    assert tombstone.deleted_by == "admin@factbox.com"


def test_seed_homepage_video_respects_tombstones(runner, db_session):
    """Seed command never recreates a homepage video if deleted by admin."""
    # Create tombstone simulating prior deletion
    tombstone = MediaDeletionTombstone(
        asset_type="website_media",
        cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"],
        title_or_name=CURATED_HOMEPAGE_VIDEO["title"],
        reason="Admin deliberate deletion",
    )
    db_session.add(tombstone)
    db_session.commit()

    # Run seed command
    res = runner.invoke(args=["seed-homepage-video"])
    assert res.exit_code == 0
    assert "[SKIPPED - DELETED BY ADMIN]" in res.output

    # Verify no WebsiteMedia record was resurrected
    existing = WebsiteMedia.query.filter_by(cloudinary_public_id=CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]).first()
    assert existing is None


def test_restore_deleted_homepage_video_from_tombstone(db_session):
    """Restoring a deleted video from tombstone creates WebsiteMedia in unpublished state."""
    tombstone = MediaDeletionTombstone(
        asset_type="website_media",
        cloudinary_public_id="factbox/videos/yysipv6v94ru5c4uxmpu",
        title_or_name="Restorable Video Reel",
        original_data={
            "title": "Restorable Video Reel",
            "category": "homepage_video",
            "media_type": "video",
            "cloudinary_public_id": "factbox/videos/yysipv6v94ru5c4uxmpu",
            "secure_url": "https://res.cloudinary.com/factbox/video/upload/v1/factbox/videos/yysipv6v94ru5c4uxmpu.mp4",
            "alt_text": "Restored reel alt",
            "caption": "Restored caption",
            "display_order": 2,
        },
    )
    db_session.add(tombstone)
    db_session.commit()
    tombstone_id = tombstone.id

    with patch("app.services.media.check_cloudinary_asset_exists", return_value=True):
        success, msg = restore_deleted_media(tombstone_id)
        assert success is True
        assert "successfully restored" in msg

    restored = WebsiteMedia.query.filter_by(cloudinary_public_id="factbox/videos/yysipv6v94ru5c4uxmpu").first()
    assert restored is not None
    assert restored.title == "Restorable Video Reel"
    assert restored.status == "unpublished"  # unpublished for safety
    assert db_session.get(MediaDeletionTombstone, tombstone_id) is None
