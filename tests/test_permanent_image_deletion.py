"""Comprehensive test suite for Permanent Image Deletion and Administrator Authority.

Enforces Phase 2 Requirements (Pillars 1-10):
- TEST 1 & 2: Administrator deletes homepage photograph -> Seeding command runs -> Photograph remains deleted.
- TEST 3 & 4: Administrator deletes partner logo -> Seeding command runs -> Partner logo remains deleted.
- TEST 5: Administrator unpublishes a logo -> Seeding command runs -> Remains unpublished.
- TEST 6: Administrator edits caption and ordering -> Seeding command runs -> Changes remain intact.
- TEST 7: Administrator uploads new photograph -> Saved to PostgreSQL and displays correctly.
- TEST 8: Application restarts -> No deleted images return.
- TEST 9: Simulated Render deployment (db upgrade + init-admin) -> No deleted images return.
- TEST 10: Deliberate administrator restoration -> Restores cleanly through authorized process.
"""
import io
import pytest
from unittest.mock import patch
from app import create_app
from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo
from app.models.tombstone import MediaDeletionTombstone
from app.services.media import (
    delete_home_page_photo_safely,
    delete_partner_logo_safely,
    save_home_page_photo_safely,
    restore_deleted_media,
)


def test_1_and_2_delete_home_photo_persists_across_seeding(runner, db_session, sample_admin):
    """TEST 1 & 2: Admin deletes a homepage photo; seed-home-photos does NOT recreate it."""
    # 1. Initial seed
    res = runner.invoke(args=["seed-home-photos"])
    assert res.exit_code == 0
    target_photo = HomePagePhoto.query.filter_by(title="Documentary Field Unit").first()
    assert target_photo is not None
    photo_id = target_photo.id
    target_pid = target_photo.cloudinary_public_id

    # 2. Admin deletes photo
    deleted = delete_home_page_photo_safely(photo_id, admin_email=sample_admin.email)
    assert deleted is True

    # Confirm deletion from database
    assert db_session.get(HomePagePhoto, photo_id) is None
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="home_page_photo", cloudinary_public_id=target_pid
    ).first()
    assert tombstone is not None
    assert tombstone.title_or_name == "Documentary Field Unit"

    # 3. Execute seed command again (simulating deployment or routine maintenance)
    seed_res = runner.invoke(args=["seed-home-photos"])
    assert seed_res.exit_code == 0
    assert "skipped (deleted by admin)" in seed_res.output

    # Photograph must REMAIN deleted
    assert HomePagePhoto.query.filter_by(title="Documentary Field Unit").first() is None
    assert HomePagePhoto.query.filter_by(cloudinary_public_id=target_pid).first() is None


def test_3_and_4_delete_partner_logo_persists_across_seeding(runner, db_session, sample_admin):
    """TEST 3 & 4: Admin deletes a partner logo; seed-partner-logos does NOT recreate it."""
    # 1. Initial seed
    res = runner.invoke(args=["seed-partner-logos"])
    assert res.exit_code == 0
    target_logo = PartnerLogo.query.filter_by(name="Mercy Corps").first()
    assert target_logo is not None
    logo_id = target_logo.id
    target_pid = target_logo.logo_cloudinary_public_id

    # 2. Admin deletes logo
    deleted = delete_partner_logo_safely(logo_id, admin_email=sample_admin.email)
    assert deleted is True

    # Confirm deletion from database
    assert db_session.get(PartnerLogo, logo_id) is None
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="partner_logo", cloudinary_public_id=target_pid
    ).first()
    assert tombstone is not None

    # 3. Execute seed command again
    seed_res = runner.invoke(args=["seed-partner-logos"])
    assert seed_res.exit_code == 0
    assert "skipped (deleted by admin)" in seed_res.output

    # Partner logo must REMAIN deleted
    assert PartnerLogo.query.filter_by(name="Mercy Corps").first() is None
    assert PartnerLogo.query.filter_by(logo_cloudinary_public_id=target_pid).first() is None


def test_5_unpublished_logo_remains_unpublished(runner, db_session):
    """TEST 5: Admin unpublishes a partner logo; seeding never forcibly republishes it."""
    runner.invoke(args=["seed-partner-logos"])
    logo = PartnerLogo.query.filter_by(name="GIZ").first()
    assert logo is not None
    assert logo.is_published is True

    # Admin unpublishes the logo
    logo.is_published = False
    db_session.commit()

    # Re-run seeding
    res = runner.invoke(args=["seed-partner-logos"])
    assert res.exit_code == 0

    # Verification: Must remain unpublished!
    rechecked = PartnerLogo.query.filter_by(name="GIZ").first()
    assert rechecked.is_published is False


def test_6_admin_edited_caption_and_ordering_remain_intact(runner, db_session):
    """TEST 6: Admin edits photo caption and ordering; seeding never overwrites them."""
    runner.invoke(args=["seed-home-photos"])
    photo = HomePagePhoto.query.filter_by(title="Audiovisual Storytelling").first()
    assert photo is not None

    # Admin edits caption and ordering
    photo.caption = "Custom verified admin caption 2026."
    photo.display_order = 88
    db_session.commit()

    # Re-run seeding
    res = runner.invoke(args=["seed-home-photos"])
    assert res.exit_code == 0

    # Verification: Edits are preserved!
    rechecked = HomePagePhoto.query.filter_by(title="Audiovisual Storytelling").first()
    assert rechecked.caption == "Custom verified admin caption 2026."
    assert rechecked.display_order == 88


@patch("app.services.media.upload_image_to_cloudinary")
def test_7_upload_new_photograph_persists_and_queries(mock_upload, db_session):
    """TEST 7: Admin uploads a new photograph; saved to PostgreSQL and queries properly."""
    mock_upload.return_value = {
        "public_id": "factbox/home_hero/custom_upload_2026",
        "secure_url": "https://res.cloudinary.com/factbox/custom_upload_2026.jpg",
        "width": 1920,
        "height": 1080,
    }

    dummy_file = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)
    dummy_file.name = "test.jpg"
    from werkzeug.datastructures import FileStorage
    fs = FileStorage(stream=dummy_file, filename="test.jpg", content_type="image/jpeg")

    photo = save_home_page_photo_safely(
        file_storage=fs,
        alt_text="New field photo uploaded by admin",
        title="Custom Field Photo",
        caption="High resolution fieldwork documentation",
        display_order=15,
        is_active=True,
    )
    assert photo.id is not None
    assert photo.cloudinary_public_id == "factbox/home_hero/custom_upload_2026"

    # Query from database
    found = HomePagePhoto.query.filter_by(title="Custom Field Photo").first()
    assert found is not None
    assert found.display_order == 15
    assert found.is_active is True


def test_8_application_restart_preserves_deletion(runner, db_session, sample_admin):
    """TEST 8: Deleting images and creating a fresh app context preserves deletion state."""
    runner.invoke(args=["seed-partner-logos"])
    target = PartnerLogo.query.filter_by(name="Malaria Consortium").first()
    assert target is not None

    delete_partner_logo_safely(target.id, admin_email=sample_admin.email)
    assert PartnerLogo.query.filter_by(name="Malaria Consortium").first() is None

    # Simulate application restart with fresh app instance
    new_app = create_app("testing")
    with new_app.app_context():
        # Confirm Malaria Consortium is still absent
        assert PartnerLogo.query.filter_by(name="Malaria Consortium").first() is None
        tombstone = MediaDeletionTombstone.query.filter_by(
            asset_type="partner_logo", title_or_name="Malaria Consortium"
        ).first()
        assert tombstone is not None


def test_9_simulated_render_deployment_startup(runner, db_session, sample_admin):
    """TEST 9: Render startCommand (db upgrade && init-admin) does not resurrect deleted images."""
    runner.invoke(args=["seed-home-photos"])
    photo = HomePagePhoto.query.filter_by(title="Documentary Field Unit").first()
    assert photo is not None

    # Delete photo
    delete_home_page_photo_safely(photo.id, admin_email=sample_admin.email)
    assert HomePagePhoto.query.filter_by(title="Documentary Field Unit").first() is None

    # Simulate render startCommand operations
    # 1. flask db upgrade (already applied via migrations)
    # 2. flask init-admin
    res_admin = runner.invoke(args=["init-admin"])
    assert res_admin.exit_code == 0

    # Ensure deleted photo did not return
    assert HomePagePhoto.query.filter_by(title="Documentary Field Unit").first() is None


def test_10_deliberate_administrator_restoration(runner, db_session, sample_admin):
    """TEST 10: Deleted image is deliberately restored through the authorized process."""
    runner.invoke(args=["seed-partner-logos"])
    target = PartnerLogo.query.filter_by(name="Norwegian Refugee Council (NRC)").first()
    assert target is not None
    target_pid = target.logo_cloudinary_public_id

    # Admin deletes it
    delete_partner_logo_safely(target.id, admin_email=sample_admin.email)
    assert PartnerLogo.query.filter_by(name="Norwegian Refugee Council (NRC)").first() is None

    # Tombstone is present
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="partner_logo", cloudinary_public_id=target_pid
    ).first()
    assert tombstone is not None

    # Deliberate authorized restoration via CLI or service
    restore_res = runner.invoke(
        args=["restore-media", "--type", "partner_logo", "--public-id", target_pid]
    )
    assert restore_res.exit_code == 0
    assert "Success" in restore_res.output

    # Verified restored in database
    restored = PartnerLogo.query.filter_by(name="Norwegian Refugee Council (NRC)").first()
    assert restored is not None
    assert restored.logo_cloudinary_public_id == target_pid
    # Restored safely as unpublished
    assert restored.is_published is False

    # Tombstone is now consumed and removed
    assert (
        MediaDeletionTombstone.query.filter_by(
            asset_type="partner_logo", cloudinary_public_id=target_pid
        ).first()
        is None
    )
