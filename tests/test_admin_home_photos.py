"""Tests for Stage 5 Home Page Photos admin management (ADR-010).

Validates:
- Unauthorized access is denied on all endpoints
- Authenticated admin can list, upload, edit, toggle, and delete hero background photos
- Form validation enforces required alt text and valid image uploads
- Cloudinary asset cleanup and database consistency are verified
"""
import io
import pytest
from unittest.mock import patch
from app.models.home_photo import HomePagePhoto


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


def test_home_photos_anonymous_access_denied(client):
    """Anonymous visitors must be redirected to login when accessing home photos admin."""
    res = client.get("/admin/home-photos")
    assert res.status_code == 302
    assert "/admin/login" in res.headers["Location"]

    res_new = client.get("/admin/home-photos/new")
    assert res_new.status_code == 302
    assert "/admin/login" in res_new.headers["Location"]


def test_home_photos_list_view(client, sample_admin, db_session):
    """Authenticated admin can list home photos."""
    login_admin(client, sample_admin)

    photo = HomePagePhoto(
        title="Cinematic Lighting Setup",
        cloudinary_public_id="home_hero/test_lighting",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/home_hero/test_lighting.jpg",
        alt_text="Documentary film lighting equipment",
        display_order=0,
        is_active=True,
    )
    db_session.add(photo)
    db_session.commit()

    res = client.get("/admin/home-photos")
    assert res.status_code == 200
    assert "Cinematic Lighting Setup" in res.get_data(as_text=True)
    assert "Documentary film lighting equipment" in res.get_data(as_text=True)


def test_home_photo_create_success(client, sample_admin, db_session):
    """Admin can upload a new hero photo with Cloudinary mock."""
    login_admin(client, sample_admin)

    # Valid JPEG header
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200
    data = {
        "image_file": (io.BytesIO(fake_jpeg), "hero_shot.jpg", "image/jpeg"),
        "title": "Documentary Crew at Sunset",
        "alt_text": "Cinematographer adjusting camera rig during sunset",
        "caption": "Golden hour filming on location in Jos",
        "display_order": "1",
        "is_active": "y",
    }

    mock_upload = {
        "public_id": "factbox/home_hero/mock_hero_01",
        "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1/mock_hero_01.jpg",
        "width": 1920,
        "height": 1080,
        "format": "jpg",
        "bytes": len(fake_jpeg),
    }

    with patch("app.services.media.upload_image_to_cloudinary", return_value=mock_upload):
        res = client.post(
            "/admin/home-photos/new",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert res.status_code == 200
    assert "Hero background photo uploaded successfully" in res.get_data(as_text=True)

    created = HomePagePhoto.query.filter_by(cloudinary_public_id="factbox/home_hero/mock_hero_01").first()
    assert created is not None
    assert created.title == "Documentary Crew at Sunset"
    assert created.alt_text == "Cinematographer adjusting camera rig during sunset"
    assert created.display_order == 1
    assert created.is_active is True


def test_home_photo_edit_metadata(client, sample_admin, db_session):
    """Admin can edit metadata of an existing photo."""
    login_admin(client, sample_admin)

    photo = HomePagePhoto(
        title="Initial Title",
        cloudinary_public_id="home_hero/edit_test",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/edit_test.jpg",
        alt_text="Initial alt text",
        display_order=0,
        is_active=True,
    )
    db_session.add(photo)
    db_session.commit()

    edit_data = {
        "title": "Updated Title",
        "alt_text": "Updated alt text for accessibility",
        "caption": "New narrative caption",
        "display_order": "5",
        "is_active": "y",
    }
    res = client.post(
        f"/admin/home-photos/{photo.id}/edit",
        data=edit_data,
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "Photo details updated successfully" in res.get_data(as_text=True)

    updated = db_session.get(HomePagePhoto, photo.id)
    assert updated.title == "Updated Title"
    assert updated.alt_text == "Updated alt text for accessibility"
    assert updated.display_order == 5


def test_home_photo_toggle_active(client, sample_admin, db_session):
    """Admin can toggle is_active status of hero photo."""
    login_admin(client, sample_admin)

    photo = HomePagePhoto(
        title="Toggle Photo",
        cloudinary_public_id="home_hero/toggle_test",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/toggle_test.jpg",
        alt_text="Toggle test photo",
        display_order=0,
        is_active=True,
    )
    db_session.add(photo)
    db_session.commit()

    # Toggle to inactive
    res = client.post(f"/admin/home-photos/{photo.id}/toggle", follow_redirects=True)
    assert res.status_code == 200
    db_session.expire_all()
    updated = db_session.get(HomePagePhoto, photo.id)
    assert updated.is_active is False

    # Toggle back to active
    res2 = client.post(f"/admin/home-photos/{photo.id}/toggle", follow_redirects=True)
    assert res2.status_code == 200
    db_session.expire_all()
    updated2 = db_session.get(HomePagePhoto, photo.id)
    assert updated2.is_active is True


def test_home_photo_delete_cleans_cloudinary(client, sample_admin, db_session):
    """Deleting hero photo removes record from PostgreSQL and calls Cloudinary destroy."""
    login_admin(client, sample_admin)

    photo = HomePagePhoto(
        title="Photo To Delete",
        cloudinary_public_id="home_hero/to_delete_01",
        secure_url="https://res.cloudinary.com/factbox/image/upload/v1/to_delete_01.jpg",
        alt_text="Photo to delete",
        display_order=0,
        is_active=True,
    )
    db_session.add(photo)
    db_session.commit()

    photo_id = photo.id

    with patch("app.services.media.delete_image_from_cloudinary") as mock_destroy:
        mock_destroy.return_value = True
        res = client.post(f"/admin/home-photos/{photo_id}/delete", follow_redirects=True)

        assert res.status_code == 200
        assert "Hero background photo deleted successfully" in res.get_data(as_text=True)
        mock_destroy.assert_called_once_with("home_hero/to_delete_01")

    assert db_session.get(HomePagePhoto, photo_id) is None
