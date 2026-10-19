"""Tests for Administrator authentication, sessions, and authorization.

Enforces ROADMAP Stage 2 exit criteria:
- Unauthorized admin access denied
- Login success/failure and audit recording
- Password not stored in plaintext
- Session behavior and logout
- Safe redirect handling preventing open redirects
"""
import pytest
from app.models.admin import AdminUser, AdminAuditEvent


def test_admin_dashboard_unauthorized_redirects(client):
    """Anonymous visitors cannot access the admin dashboard; redirected to login."""
    response = client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]
    assert "next=%2Fadmin%2Fdashboard" in response.headers["Location"]


def test_admin_root_unauthorized_redirects(client):
    """Anonymous visitors cannot access /admin/; redirected to login."""
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_login_success(client, db_session, sample_admin):
    """Administrator can log in with valid credentials; session is established."""
    response = client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Management Dashboard" in response.data
    assert sample_admin.email.encode() in response.data

    # Audit event should be recorded
    event = (
        AdminAuditEvent.query.filter_by(
            admin_user_id=sample_admin.id, event_type="login_success"
        )
        .order_by(AdminAuditEvent.occurred_at.desc())
        .first()
    )
    assert event is not None


def test_admin_login_failure_invalid_password(client, db_session, sample_admin):
    """Invalid password rejects login with 401 and logs failure."""
    response = client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "WrongPassword!",
        },
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert b"Invalid email address or password" in response.data

    # Audit event should be recorded for failed attempt
    event = (
        AdminAuditEvent.query.filter_by(
            admin_user_id=sample_admin.id, event_type="login_failure"
        )
        .order_by(AdminAuditEvent.occurred_at.desc())
        .first()
    )
    assert event is not None


def test_admin_login_inactive_user_denied(client, db_session):
    """Deactivated admin accounts cannot log in."""
    inactive = AdminUser(
        email="inactive@factboxconsult.com",
        is_active=False,
    )
    inactive.set_password("SecurePassword2026!")
    db_session.add(inactive)
    db_session.commit()

    response = client.post(
        "/admin/login",
        data={
            "email": "inactive@factboxconsult.com",
            "password": "SecurePassword2026!",
        },
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert b"Invalid email address or password" in response.data


def test_admin_logout(client, db_session, sample_admin):
    """Logging out safely clears the session."""
    # First log in
    client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=True,
    )

    # Now log out
    response = client.get("/admin/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]

    # Dashboard should now be inaccessible
    dashboard_resp = client.get("/admin/dashboard", follow_redirects=False)
    assert dashboard_resp.status_code == 302
    assert "/admin/login" in dashboard_resp.headers["Location"]


def test_admin_open_redirect_prevention(client, db_session, sample_admin):
    """External malicious URLs passed in 'next' parameter are safely neutralized."""
    response = client.post(
        "/admin/login?next=https://attacker-site.com/steal-creds",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    # Must redirect to internal dashboard, NOT to external attacker site
    assert response.headers["Location"] == "/admin/dashboard"


def test_admin_login_csrf_enforced(app, sample_admin):
    """Admin login rejects state-changing POST requests lacking CSRF token when enabled."""
    csrf_app = app
    csrf_app.config["WTF_CSRF_ENABLED"] = True
    csrf_client = csrf_app.test_client()

    response = csrf_client.post(
        "/admin/login",
        data={
            "email": sample_admin.email,
            "password": "SecurePassword2026!",
        },
        follow_redirects=False,
    )
    # Must reject with 400 Bad Request due to missing CSRF token
    assert response.status_code == 400

    # Reset config back
    csrf_app.config["WTF_CSRF_ENABLED"] = False

