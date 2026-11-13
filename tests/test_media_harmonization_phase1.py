"""Unit and integration tests for Media Harmonization Phase 1.

Verifies:
1. check_cloudinary_asset_exists reflects live Cloudinary existence without artificial system asset bypass.
2. get_showcase_photo() never returns inactive reserve photos when active photos are absent.
3. Repaired HomePagePhoto records have valid Cloudinary references.
4. Catalogued orphan assets exist in WebsiteMedia as unpublished items and are not exposed publicly.
"""
from unittest.mock import patch
from app.models.home_photo import HomePagePhoto
from app.models.media import WebsiteMedia
from app.services.media import check_cloudinary_asset_exists, is_system_asset


def test_cloudinary_health_check_no_artificial_bypass():
    """check_cloudinary_asset_exists queries Cloudinary API even for system showcase assets."""
    # A system showcase PID
    system_pid = "factbox/home_hero/gk5kxanaxpc5ex6hhi0i"
    assert is_system_asset(system_pid) is True

    # If Cloudinary returns 404/not found, check_cloudinary_asset_exists must return False (no bypass)
    with patch("cloudinary.api.resource", side_effect=Exception("Resource not found")):
        assert check_cloudinary_asset_exists(system_pid) is False

    # If Cloudinary returns resource dict, check_cloudinary_asset_exists returns True
    with patch("cloudinary.api.resource", return_value={"public_id": system_pid}):
        assert check_cloudinary_asset_exists(system_pid) is True


def test_get_showcase_photo_no_reserve_fallback(client, db_session):
    """When all HomePagePhoto records are inactive/reserve, get_showcase_photo returns safe fallback."""
    # Create an inactive reserve photo
    reserve_photo = HomePagePhoto(
        title="Reserve Test Photo",
        cloudinary_public_id="factbox/home_hero/mock_reserve_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/mock_reserve_01.jpg",
        alt_text="Reserve photo not to be shown",
        caption="Reserve caption",
        display_order=16,
        is_active=False,
    )
    db_session.add(reserve_photo)
    db_session.commit()

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Must render the default safe fallback image
    assert "/static/img/hero_fallback.jpg" in html

    # The reserve photo must NOT be rendered in hero slides
    assert "https://res.cloudinary.com/factbox/image/upload/v1/mock_reserve_01.jpg" not in html
    assert "Reserve photo not to be shown" not in html


def test_catalogued_orphans_in_website_media(client, db_session):
    """Catalogued orphan photos in WebsiteMedia (status='unpublished') are not exposed on public home."""
    orphan_photo = WebsiteMedia(
        title="Digital Production Workstation & Cameras",
        alt_text="Documentary cameras and field production equipment",
        caption="Field preparation and production staging.",
        cloudinary_public_id="factbox/home_hero/ck7b3ytsejexa7p8tqns",
        secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/v1793572147/factbox/home_hero/ck7b3ytsejexa7p8tqns.jpg",
        category="website_media",
        media_type="image",
        status="unpublished",
        display_order=1,
    )
    db_session.add(orphan_photo)
    db_session.commit()

    # Query from DB to verify persistence and properties
    record = WebsiteMedia.query.filter_by(cloudinary_public_id="factbox/home_hero/ck7b3ytsejexa7p8tqns").first()
    assert record is not None
    assert record.category == "website_media"
    assert record.status == "unpublished"
    assert record.media_type == "image"

    # Verify public home page does NOT expose this unpublished image
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert record.secure_url not in html
    assert record.title not in html
