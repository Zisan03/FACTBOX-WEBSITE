"""Tests for PartnerLogo administration and global footer ribbon integration.

Validates:
- Unauthorized access is denied on all partner logo endpoints
- Authenticated admin can list, upload, edit, toggle, and delete partner logos
- Cloudinary asset cleanup and orphan prevention
- Injection into global template context processor
"""
import io
import pytest
from unittest.mock import patch
from app.models.content import PartnerLogo


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


def test_partner_logos_anonymous_access_denied(client):
    """Anonymous visitors are redirected to login when accessing partner logo admin."""
    res = client.get("/admin/partner-logos")
    assert res.status_code == 302
    assert "/admin/login" in res.headers["Location"]

    res_upload = client.get("/admin/partner-logos/upload")
    assert res_upload.status_code == 302
    assert "/admin/login" in res_upload.headers["Location"]


def test_partner_logos_list_view(client, sample_admin, db_session):
    """Authenticated admin can list registered partner logos."""
    login_admin(client, sample_admin)

    logo = PartnerLogo(
        name="Mercy Corps",
        logo_cloudinary_public_id="factbox/partner_logos/mercy_corps",
        logo_secure_url="https://res.cloudinary.com/factbox/image/upload/v1/mercy_corps.png",
        website_url="https://www.mercycorps.org",
        alt_text="Mercy Corps official emblem",
        display_order=1,
        is_published=True,
    )
    db_session.add(logo)
    db_session.commit()

    res = client.get("/admin/partner-logos")
    assert res.status_code == 200
    content = res.get_data(as_text=True)
    assert "Mercy Corps" in content
    assert "https://www.mercycorps.org" in content


def test_partner_logo_upload_success(client, sample_admin, db_session):
    """Admin can upload a new partner logo with Cloudinary mock."""
    login_admin(client, sample_admin)

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
    data = {
        "logo_file": (io.BytesIO(fake_png), "international_alert.png", "image/png"),
        "name": "International Alert",
        "website_url": "https://www.international-alert.org",
        "alt_text": "International Alert organization logo",
        "display_order": "2",
        "is_published": "y",
    }

    mock_upload = {
        "public_id": "factbox/partner_logos/intl_alert_01",
        "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1/intl_alert_01.png",
        "width": 300,
        "height": 100,
        "format": "png",
        "bytes": len(fake_png),
    }

    with patch("app.services.media.upload_image_to_cloudinary", return_value=mock_upload):
        res = client.post(
            "/admin/partner-logos/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert res.status_code == 200
    assert "uploaded successfully" in res.get_data(as_text=True)

    created = PartnerLogo.query.filter_by(name="International Alert").first()
    assert created is not None
    assert created.website_url == "https://www.international-alert.org"
    assert created.display_order == 2
    assert created.is_published is True


def test_partner_logo_edit_metadata(client, sample_admin, db_session):
    """Admin can edit name and website url of an existing logo without re-uploading file."""
    login_admin(client, sample_admin)

    logo = PartnerLogo(
        name="Malaria Consortium Draft",
        logo_cloudinary_public_id="factbox/partner_logos/malaria_draft",
        logo_secure_url="https://res.cloudinary.com/factbox/image/upload/v1/malaria_draft.png",
        alt_text="Malaria Consortium placeholder",
        display_order=5,
        is_published=False,
    )
    db_session.add(logo)
    db_session.commit()

    res = client.post(
        f"/admin/partner-logos/{logo.id}/edit",
        data={
            "name": "Malaria Consortium",
            "website_url": "https://www.malariaconsortium.org",
            "alt_text": "Malaria Consortium official emblem",
            "display_order": "1",
            "is_published": "y",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "updated successfully" in res.get_data(as_text=True)

    db_session.refresh(logo)
    assert logo.name == "Malaria Consortium"
    assert logo.website_url == "https://www.malariaconsortium.org"
    assert logo.is_published is True
    assert logo.display_order == 1


def test_partner_logo_toggle_status(client, sample_admin, db_session):
    """Admin can toggle published visibility of a partner logo."""
    login_admin(client, sample_admin)

    logo = PartnerLogo(
        name="Toggle Test Partner",
        logo_cloudinary_public_id="factbox/partner_logos/toggle_test",
        logo_secure_url="https://res.cloudinary.com/factbox/image/upload/v1/toggle_test.png",
        alt_text="Toggle test alt",
        is_published=True,
    )
    db_session.add(logo)
    db_session.commit()

    # Toggle to hidden
    res1 = client.post(f"/admin/partner-logos/{logo.id}/toggle", follow_redirects=True)
    assert res1.status_code == 200
    db_session.refresh(logo)
    assert logo.is_published is False

    # Toggle back to published
    res2 = client.post(f"/admin/partner-logos/{logo.id}/toggle", follow_redirects=True)
    assert res2.status_code == 200
    db_session.refresh(logo)
    assert logo.is_published is True


def test_partner_logo_delete_cleans_cloudinary(client, sample_admin, db_session):
    """Deleting a partner logo destroys the external Cloudinary asset and database row."""
    login_admin(client, sample_admin)

    logo = PartnerLogo(
        name="Delete Me Partner",
        logo_cloudinary_public_id="factbox/partner_logos/delete_me_01",
        logo_secure_url="https://res.cloudinary.com/factbox/image/upload/v1/delete_me_01.png",
        alt_text="Delete me alt",
        is_published=True,
    )
    db_session.add(logo)
    db_session.commit()
    logo_id = logo.id

    with patch("app.services.media.delete_image_from_cloudinary") as mock_destroy:
        mock_destroy.return_value = {"result": "ok"}
        res = client.post(f"/admin/partner-logos/{logo_id}/delete", follow_redirects=True)

    assert res.status_code == 200
    assert "deleted successfully" in res.get_data(as_text=True)
    mock_destroy.assert_called_once_with("factbox/partner_logos/delete_me_01")
    assert db_session.get(PartnerLogo, logo_id) is None


def test_partner_logos_in_public_footer(client, db_session):
    """Published partner logos appear in public footer across pages."""
    logo = PartnerLogo(
        name="Mercy Corps Public",
        logo_cloudinary_public_id="factbox/partner_logos/mercy_pub",
        logo_secure_url="https://res.cloudinary.com/factbox/image/upload/v1/mercy_pub.png",
        alt_text="Mercy Corps Public Alt",
        website_url="https://www.mercycorps.org",
        is_published=True,
    )
    db_session.add(logo)
    db_session.commit()

    # Check Homepage
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert "Mercy Corps Public" in home_res.get_data(as_text=True)

    # Check Services page
    serv_res = client.get("/services")
    assert serv_res.status_code == 200
    assert "Mercy Corps Public" in serv_res.get_data(as_text=True)

    # Check Contact page
    contact_res = client.get("/contact")
    assert contact_res.status_code == 200
    assert "Mercy Corps Public" in contact_res.get_data(as_text=True)
