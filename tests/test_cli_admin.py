"""Tests for administrative CLI commands.

Enforces ROADMAP Stage 2 requirement:
- First reviewed seed/CLI provisioning command for initial administrator
- No public registration and no default credentials
"""
from app.models.admin import AdminUser, AdminAuditEvent


def test_cli_create_admin_success(runner, db_session):
    """create-admin CLI command successfully provisions an administrator."""
    result = runner.invoke(
        args=["create-admin", "--email", "superadmin@factboxconsult.com"],
        input="SecretPass2026!\nSecretPass2026!\n",
    )
    assert result.exit_code == 0
    assert "Successfully provisioned administrator: superadmin@factboxconsult.com" in result.output

    user = AdminUser.query.filter_by(email="superadmin@factboxconsult.com").first()
    assert user is not None
    assert user.is_active is True
    assert user.check_password("SecretPass2026!") is True

    # Audit event should be recorded
    audit = AdminAuditEvent.query.filter_by(
        admin_user_id=user.id, event_type="admin_provisioned_cli"
    ).first()
    assert audit is not None


def test_cli_create_admin_duplicate_rejected(runner, db_session, sample_admin):
    """create-admin CLI command rejects creating an administrator with existing email."""
    result = runner.invoke(
        args=["create-admin", "--email", sample_admin.email],
        input="AnotherPassword2026!\nAnotherPassword2026!\n",
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_cli_create_admin_short_password_rejected(runner, db_session):
    """create-admin CLI command rejects passwords shorter than 8 characters."""
    result = runner.invoke(
        args=["create-admin", "--email", "newadmin@factboxconsult.com"],
        input="short\nshort\n",
    )
    assert result.exit_code != 0
    assert "at least 8 characters" in result.output


def test_cli_upload_showcase_requires_cloudinary_credentials(runner, app, monkeypatch):
    """upload-showcase-to-cloudinary rejects execution if Cloudinary credentials are missing."""
    monkeypatch.setitem(app.config, "CLOUDINARY_CLOUD_NAME", None)
    monkeypatch.setitem(app.config, "CLOUDINARY_API_KEY", None)
    monkeypatch.setitem(app.config, "CLOUDINARY_API_SECRET", None)
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_SECRET", raising=False)

    result = runner.invoke(args=["upload-showcase-to-cloudinary"])
    assert result.exit_code != 0
    assert "Cloudinary credentials" in result.output


def test_cli_upload_showcase_success(runner, app, db_session, monkeypatch, tmp_path):
    """upload-showcase-to-cloudinary uploads photos and saves records when configured."""
    from unittest.mock import patch

    monkeypatch.setitem(app.config, "CLOUDINARY_CLOUD_NAME", "factbox-cloud")
    monkeypatch.setitem(app.config, "CLOUDINARY_API_KEY", "valid_key")
    monkeypatch.setitem(app.config, "CLOUDINARY_API_SECRET", "valid_secret")

    # Create dummy photo in tmp_path
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 100
    test_photo = tmp_path / "photo_25.jpg"
    test_photo.write_bytes(valid_jpeg)

    mock_upload = {
        "public_id": "factbox/home_hero/mock_hero_25",
        "secure_url": "https://res.cloudinary.com/factbox-cloud/image/upload/mock_hero_25.jpg",
        "width": 1920,
        "height": 1080,
        "format": "jpg",
        "bytes": 50000,
    }

    with patch("cloudinary.uploader.upload", return_value=mock_upload):
        result = runner.invoke(args=[
            "upload-showcase-to-cloudinary",
            "--photos-dir", str(tmp_path),
            "--no-upload-partners",
        ])
        assert result.exit_code == 0
        assert "Completed:" in result.output
        assert "1 showcase photos" in result.output

    from app.models.home_photo import HomePagePhoto
    photo = HomePagePhoto.query.filter_by(cloudinary_public_id="factbox/home_hero/mock_hero_25").first()
    assert photo is not None
    assert photo.title == "Documentary Field Unit"


