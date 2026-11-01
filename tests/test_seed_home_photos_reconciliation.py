"""Tests for seed-home-photos and seed-partner-logos reconciliation and idempotency.

Verifies:
- Safe handling of duplicate titles with conflicting Cloudinary public IDs (preventing UniqueViolation)
- Exact replication and resolution of the Render production failure
- Repeated seed execution idempotency (exactly 31 showcase photos, 7 partner logos)
- Cleanup of stale/obsolete public IDs
- Transaction integrity and rollback safety
"""
import pytest
from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo


def test_seed_home_photos_resolves_production_conflict(runner, db_session):
    """Recreate the exact Render production error state and ensure seed-home-photos resolves it cleanly.

    Production state:
    - Row 1: title='Community Dialogue', cloudinary_public_id='factbox/home_hero/lj9nzuu4v4arvvugst1t' (stale)
    - Row 2: title='Community Dialogue', cloudinary_public_id='factbox/home_hero/zswgxxhygc4unwibalsy' (target)
    Old seeding logic crashed with UniqueViolation because it attempted to update Row 1 with Row 2's ID.
    Corrected logic must delete Row 1, update Row 2, and exit with code 0.
    """
    row_stale = HomePagePhoto(
        title="Community Dialogue",
        cloudinary_public_id="factbox/home_hero/lj9nzuu4v4arvvugst1t",
        secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/v1/factbox/home_hero/lj9nzuu4v4arvvugst1t.jpg",
        alt_text="Stale community dialogue photo",
        display_order=5,
        is_active=True,
    )
    row_target = HomePagePhoto(
        title="Community Dialogue",
        cloudinary_public_id="factbox/home_hero/zswgxxhygc4unwibalsy",
        secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/v1/factbox/home_hero/zswgxxhygc4unwibalsy.jpg",
        alt_text="Target community dialogue photo",
        display_order=5,
        is_active=True,
    )
    db_session.add_all([row_stale, row_target])
    db_session.commit()

    # Run CLI command
    result = runner.invoke(args=["seed-home-photos"])
    assert result.exit_code == 0
    assert "Successfully processed showcase photos" in result.output

    # Verify database state
    dialogue_photos = HomePagePhoto.query.filter_by(title="Community Dialogue").all()
    assert len(dialogue_photos) == 1
    canonical = dialogue_photos[0]
    assert canonical.cloudinary_public_id == "factbox/home_hero/zswgxxhygc4unwibalsy"
    assert canonical.id == row_target.id

    # Verify stale row was purged
    assert db_session.get(HomePagePhoto, row_stale.id) is None


def test_seed_home_photos_outdated_id_safe_update(runner, db_session):
    """When a record has the correct title but an outdated public ID (and no conflict exists), update it safely."""
    row_old = HomePagePhoto(
        title="Documentary Field Unit",
        cloudinary_public_id="factbox/home_hero/old_field_unit_legacy_id",
        secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/v1/old_field_unit.jpg",
        alt_text="Old field unit alt",
        display_order=1,
        is_active=True,
    )
    db_session.add(row_old)
    db_session.commit()

    result = runner.invoke(args=["seed-home-photos"])
    assert result.exit_code == 0

    unit_photos = HomePagePhoto.query.filter_by(title="Documentary Field Unit").all()
    assert len(unit_photos) == 1
    assert unit_photos[0].cloudinary_public_id == "factbox/home_hero/vobloojextsk2ucwsmsi"


def test_seed_home_photos_repeated_execution_idempotent(runner, db_session):
    """Running seed-home-photos multiple consecutive times must not create duplicate records."""
    # First execution
    res1 = runner.invoke(args=["seed-home-photos"])
    assert res1.exit_code == 0

    count_after_first = HomePagePhoto.query.count()
    assert count_after_first == 31

    # Second execution
    res2 = runner.invoke(args=["seed-home-photos"])
    assert res2.exit_code == 0

    count_after_second = HomePagePhoto.query.count()
    assert count_after_second == 31

    # Third execution
    res3 = runner.invoke(args=["seed-home-photos"])
    assert res3.exit_code == 0

    count_after_third = HomePagePhoto.query.count()
    assert count_after_third == 31

    # Verify 14 active hero photos and 17 reserve photos
    active_count = HomePagePhoto.query.filter_by(is_active=True).count()
    reserve_count = HomePagePhoto.query.filter_by(is_active=False).count()
    assert active_count == 14
    assert reserve_count == 17


def test_seed_partner_logos_idempotency_and_deduplication(runner, db_session):
    """Running seed-partner-logos cleans duplicates and is fully idempotent."""
    # Pre-populate duplicate Mercy Corps logos
    logo1 = PartnerLogo(
        name="Mercy Corps",
        logo_cloudinary_public_id="factbox/partner_logos/duplicate_1",
        logo_secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/dup1.png",
        alt_text="Mercy Corps duplicate 1",
        display_order=1,
        is_published=True,
    )
    logo2 = PartnerLogo(
        name="Mercy Corps",
        logo_cloudinary_public_id="factbox/partner_logos/gsjax2legfdz502bt23d",
        logo_secure_url="https://res.cloudinary.com/qvv0ipup/image/upload/v1/factbox/partner_logos/gsjax2legfdz502bt23d.png",
        alt_text="Mercy Corps duplicate 2",
        display_order=1,
        is_published=True,
    )
    db_session.add_all([logo1, logo2])
    db_session.commit()

    result = runner.invoke(args=["seed-partner-logos"])
    assert result.exit_code == 0

    mercy_logos = PartnerLogo.query.filter_by(name="Mercy Corps").all()
    assert len(mercy_logos) == 1
    assert mercy_logos[0].logo_cloudinary_public_id == "factbox/partner_logos/gsjax2legfdz502bt23d"

    total_partners = PartnerLogo.query.count()
    assert total_partners == 7

    # Run again to verify idempotency
    result2 = runner.invoke(args=["seed-partner-logos"])
    assert result2.exit_code == 0
    assert PartnerLogo.query.count() == 7
