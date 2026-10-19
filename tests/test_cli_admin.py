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
