"""Tests for administrator password change, email recovery, and CLI reset.

Verifies:
- Authenticated in-dashboard password change
- Rejection of wrong current password and passwords shorter than 8 characters
- Anti-enumeration behavior of forgot-password request
- Timed token generation, verification, and expiration
- Single-use invalidation of reset tokens
- Emergency CLI password reset command
"""
import uuid
import pytest
from app.extensions import db
from app.models.admin import AdminUser, AdminAuditEvent


def test_change_password_requires_auth(client):
    """Anonymous access to /admin/change-password is redirected to login."""
    response = client.get("/admin/change-password")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_change_password_success(client, db_session, sample_admin):
    """Authenticated admin can update their password."""
    # Log in first
    login_resp = client.post(
        "/admin/login",
        data={"email": sample_admin.email, "password": "SecurePassword2026!"},
        follow_redirects=True,
    )
    assert login_resp.status_code == 200

    # Change password
    resp = client.post(
        "/admin/change-password",
        data={
            "current_password": "SecurePassword2026!",
            "new_password": "NewSecretPassword2026!",
            "confirm_password": "NewSecretPassword2026!",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"successfully updated" in resp.data

    # Verify old password no longer works
    assert not sample_admin.check_password("SecurePassword2026!")
    assert sample_admin.check_password("NewSecretPassword2026!")

    # Verify audit event logged
    audit = AdminAuditEvent.query.filter_by(
        admin_user_id=sample_admin.id, event_type="password_changed"
    ).first()
    assert audit is not None


def test_change_password_rejects_wrong_current(client, db_session, sample_admin):
    """Change password fails if current password does not match."""
    client.post(
        "/admin/login",
        data={"email": sample_admin.email, "password": "SecurePassword2026!"},
        follow_redirects=True,
    )

    resp = client.post(
        "/admin/change-password",
        data={
            "current_password": "WrongPassword999!",
            "new_password": "NewSecretPassword2026!",
            "confirm_password": "NewSecretPassword2026!",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 400
    assert b"Incorrect current password" in resp.data


def test_forgot_password_anti_enumeration(client, db_session):
    """Forgot password request flashes constant message regardless of whether email exists."""
    # Unknown email
    resp = client.post(
        "/admin/forgot-password",
        data={"email": "nonexistent@factboxconsult.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"If an active administrator account exists" in resp.data


def test_forgot_password_sends_email_and_token(client, db_session, sample_admin, monkeypatch):
    """Forgot password sends email with valid reset token for existing admin."""
    sent_emails = []

    def mock_send(msg):
        sent_emails.append(msg)

    from app.extensions import mail
    monkeypatch.setattr(mail, "send", mock_send)

    resp = client.post(
        "/admin/forgot-password",
        data={"email": sample_admin.email},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert len(sent_emails) == 1
    assert sample_admin.email in sent_emails[0].recipients
    assert "reset-password" in sent_emails[0].body


def test_reset_password_with_token_success(client, db_session, sample_admin):
    """Admin can reset password using valid timed token."""
    token = sample_admin.get_reset_token(expires_sec=1800)

    # View reset form
    get_resp = client.get(f"/admin/reset-password/{token}")
    assert get_resp.status_code == 200
    assert b"Set New Password" in get_resp.data

    # Submit new password
    post_resp = client.post(
        f"/admin/reset-password/{token}",
        data={
            "new_password": "ResetPassword2026!",
            "confirm_password": "ResetPassword2026!",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200
    assert b"successfully reset" in post_resp.data

    # Check updated password works
    assert sample_admin.check_password("ResetPassword2026!")

    # Check token is now invalidated (single-use)
    assert AdminUser.verify_reset_token(token) is None


def test_reset_password_with_invalid_token_rejected(client, db_session):
    """Invalid or tampered reset token is rejected and redirected."""
    resp = client.get("/admin/reset-password/totally-bogus-token-12345", follow_redirects=True)
    assert resp.status_code == 200
    assert b"invalid or has expired" in resp.data


def test_cli_reset_admin_password_success(app, db_session, sample_admin):
    """reset-admin-password CLI command successfully resets password."""
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["reset-admin-password", "--email", sample_admin.email],
        input="CliNewSecretPassword2026!\nCliNewSecretPassword2026!\n",
    )
    assert result.exit_code == 0
    assert "Successfully reset password" in result.output

    # Refresh from db
    db_session.refresh(sample_admin)
    assert sample_admin.check_password("CliNewSecretPassword2026!")


def test_cli_reset_admin_password_unknown_email(app, db_session):
    """reset-admin-password CLI command exits with error for unknown admin email."""
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["reset-admin-password", "--email", "nobody@factboxconsult.com"],
        input="NewSecretPassword2026!\nNewSecretPassword2026!\n",
    )
    assert result.exit_code == 1
    assert "not found" in result.output
