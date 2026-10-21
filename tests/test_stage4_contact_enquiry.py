"""Automated test suite for Stage 4 — Contact Enquiry Workflow & Email.

Enforces:
- ROADMAP.md Stage 4 exit gate:
  - No enquiry is lost due to email failure
  - Administrator can identify and retry failed notifications
- PRD FR-05 & FR-06:
  - Input validation, honeypot spam protection, rate limiting
  - Commit enquiry to PostgreSQL before email delivery is attempted (ADR-006)
  - Safe error codes without exposing credentials, secrets, or internal paths
  - Escaped admin display preventing stored XSS
  - Administrative status management and notification retry
  - Audit logging on notification retry and status changes
"""
import uuid
import socket
import smtplib
import pytest
from unittest.mock import patch, MagicMock
from app.extensions import db
from app.models.enquiry import Enquiry
from app.models.admin import AdminAuditEvent
from app.services.email import (
    build_enquiry_notification_message,
    send_enquiry_notification,
    process_enquiry_notification,
)


# ============================================================================
# Helpers
# ============================================================================

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


def create_sample_enquiry(
    db_session,
    full_name="Dr. Amina Bello",
    email="amina.bello@example.com",
    subject="Documentary Research Collaboration",
    message="We would like to discuss producing an investigative documentary on renewable energy initiatives.",
    organization="Energy Policy Institute",
    phone="+234 803 123 4567",
    status="new",
    notification_status="pending",
    notification_attempts=0,
    notification_error_code=None,
):
    """Create and persist an Enquiry record directly in PostgreSQL."""
    enquiry = Enquiry(
        full_name=full_name,
        organization=organization,
        email=email.strip().lower(),
        phone=phone,
        subject=subject,
        message=message,
        status=status,
        notification_status=notification_status,
        notification_attempts=notification_attempts,
        notification_error_code=notification_error_code,
    )
    db_session.add(enquiry)
    db_session.commit()
    return enquiry


# ============================================================================
# 1. Public Contact Form Rendering & Server Validation
# ============================================================================

def test_contact_page_renders_form(client):
    """GET /contact returns 200 with contact form and honeypot field."""
    response = client.get("/contact")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Start a Conversation" in html
    assert "full_name" in html
    assert "email" in html
    assert "subject" in html
    assert "message" in html
    assert "company_website" in html  # Honeypot field present


def test_valid_contact_submission_persists_to_postgresql(client, db_session):
    """Valid contact submission is saved to PostgreSQL with normalized lowercase email."""
    with patch("app.blueprints.contact.routes.process_enquiry_notification") as mock_notify:
        mock_notify.return_value = (True, None)

        response = client.post(
            "/contact",
            data={
                "full_name": "Chief Emeka Okafor",
                "organization": "Pan-African Media Trust",
                "email": "EMEKA.OKAFOR@Example.COM",
                "phone": "+234 802 987 6543",
                "subject": "Media Archiving Project",
                "message": "We need strategic advice on digital archiving of our historical video reels.",
                "company_website": "",  # Empty honeypot
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Thank you for reaching out" in html

        # Verify record in PostgreSQL
        enquiry = Enquiry.query.filter_by(email="emeka.okafor@example.com").first()
        assert enquiry is not None
        assert enquiry.full_name == "Chief Emeka Okafor"
        assert enquiry.organization == "Pan-African Media Trust"
        assert enquiry.subject == "Media Archiving Project"
        assert enquiry.status == "new"
        assert mock_notify.called


def test_contact_validation_rejects_missing_required_fields(client, db_session):
    """Submissions lacking required fields are rejected with 400 and no DB record is created."""
    response = client.post(
        "/contact",
        data={
            "full_name": "",
            "email": "",
            "subject": "",
            "message": "",
        },
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Please provide your full name." in html
    assert "Please provide your email address." in html
    assert "Please provide a subject" in html
    assert "Please provide your message." in html
    assert Enquiry.query.count() == 0


def test_contact_validation_rejects_invalid_email(client, db_session):
    """Submissions with malformed email addresses are rejected."""
    response = client.post(
        "/contact",
        data={
            "full_name": "Test Visitor",
            "email": "not-an-email",
            "subject": "General Query",
            "message": "This is a valid length message for checking email validation.",
        },
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Please provide a valid email address." in html
    assert Enquiry.query.count() == 0


def test_contact_validation_rejects_too_short_message(client, db_session):
    """Messages shorter than 10 characters are rejected."""
    response = client.post(
        "/contact",
        data={
            "full_name": "Test Visitor",
            "email": "visitor@example.com",
            "subject": "Short Msg",
            "message": "Hi",  # Too short
        },
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Message must be between 10 and 5,000 characters." in html
    assert Enquiry.query.count() == 0


def test_honeypot_silently_rejects_spam_bots(client, db_session):
    """When the honeypot field is filled by a bot, the submission is silently dropped without DB record."""
    with patch("app.blueprints.contact.routes.process_enquiry_notification") as mock_notify:
        response = client.post(
            "/contact",
            data={
                "full_name": "Spam Bot",
                "email": "bot@spammer.com",
                "subject": "Buy cheap watches",
                "message": "Visit our website for huge discounts on luxury replicas.",
                "company_website": "http://spammer-payload.example.com",  # Honeypot filled!
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Shows friendly confirmation to avoid alerting the bot
        html = response.get_data(as_text=True)
        assert "Thank you for reaching out" in html

        # Verify NO enquiry was created in PostgreSQL
        assert Enquiry.query.filter_by(email="bot@spammer.com").first() is None
        assert mock_notify.called is False


# ============================================================================
# 2. Durability & Email Failure Handling (ADR-005, ADR-006, PRD FR-05)
# ============================================================================

def test_database_failure_does_not_attempt_email(client, db_session):
    """If database commit fails, transaction is rolled back and email is NEVER attempted."""
    with patch("app.extensions.db.session.commit", side_effect=Exception("Database connection severed")):
        with patch("app.services.email.send_enquiry_notification") as mock_send:
            response = client.post(
                "/contact",
                data={
                    "full_name": "Grace Danjuma",
                    "email": "grace@example.com",
                    "subject": "Strategic Consultation",
                    "message": "We would like to book a strategic advisory consultation session.",
                },
            )
            assert response.status_code == 500
            assert mock_send.called is False


def test_successful_notification_delivery_updates_state(app, db_session):
    """Successful email delivery marks notification_status='sent' and sets timestamp."""
    enquiry = create_sample_enquiry(db_session)

    with patch("app.extensions.mail.send") as mock_send:
        mock_send.return_value = None

        success, error_code = process_enquiry_notification(enquiry)

        assert success is True
        assert error_code is None
        assert enquiry.notification_status == "sent"
        assert enquiry.notification_attempts == 1
        assert enquiry.notification_sent_at is not None
        assert enquiry.notification_error_code is None


def test_email_failure_preserves_enquiry_and_records_safe_error(db_session):
    """SMTP connection failure updates status to 'failed', records safe error code, and keeps DB record intact."""
    enquiry = create_sample_enquiry(db_session)
    enquiry_id = enquiry.id

    # Simulate SMTP host connection failure
    with patch("app.extensions.mail.send", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
        success, error_code = process_enquiry_notification(enquiry)

        assert success is False
        assert error_code == "SMTP_CONNECT_ERROR"

        # Check refreshed enquiry from PostgreSQL
        db_session.expire_all()
        reloaded = db_session.get(Enquiry, enquiry_id)
        assert reloaded is not None  # Record is preserved!
        assert reloaded.notification_status == "failed"
        assert reloaded.notification_attempts == 1
        assert reloaded.notification_error_code == "SMTP_CONNECT_ERROR"
        assert reloaded.notification_last_attempt_at is not None
        assert reloaded.notification_sent_at is None


def test_email_auth_failure_records_safe_auth_error_code(db_session):
    """SMTP authentication failure records safe SMTP_AUTH_ERROR code without credentials."""
    enquiry = create_sample_enquiry(db_session)

    with patch("app.extensions.mail.send", side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed")):
        success, error_code = process_enquiry_notification(enquiry)

        assert success is False
        assert error_code == "SMTP_AUTH_ERROR"
        assert enquiry.notification_error_code == "SMTP_AUTH_ERROR"
        assert enquiry.notification_status == "failed"


def test_email_timeout_records_safe_timeout_error_code(db_session):
    """Socket timeout records safe SMTP_TIMEOUT error code."""
    enquiry = create_sample_enquiry(db_session)

    with patch("app.extensions.mail.send", side_effect=socket.timeout("Socket timed out")):
        success, error_code = process_enquiry_notification(enquiry)

        assert success is False
        assert error_code == "SMTP_TIMEOUT"
        assert enquiry.notification_error_code == "SMTP_TIMEOUT"
        assert enquiry.notification_status == "failed"


def test_contact_submission_with_email_failure_still_confirms_to_visitor(client, db_session):
    """Even if email delivery fails, the visitor is informed their enquiry was received (no leak of failure)."""
    with patch("app.extensions.mail.send", side_effect=smtplib.SMTPConnectError(421, b"No route to host")):
        response = client.post(
            "/contact",
            data={
                "full_name": "Tariq Mansoor",
                "email": "tariq@example.com",
                "subject": "Documentary Feature",
                "message": "Inquiring about production services for a feature documentary.",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Thank you for reaching out" in html
        assert "SMTP" not in html  # Never leak SMTP error to visitor

        # Verify enquiry was saved in PostgreSQL with status failed
        enquiry = Enquiry.query.filter_by(email="tariq@example.com").first()
        assert enquiry is not None
        assert enquiry.notification_status == "failed"
        assert enquiry.notification_error_code == "SMTP_CONNECT_ERROR"


# ============================================================================
# 3. Admin Enquiry Management & Authorization
# ============================================================================

def test_unauthenticated_access_to_enquiries_denied(client, db_session):
    """Unauthenticated access to any admin enquiry route redirects to login."""
    fake_id = uuid.uuid4()
    assert client.get("/admin/enquiries").status_code == 302
    assert client.get(f"/admin/enquiries/{fake_id}").status_code == 302
    assert client.post(f"/admin/enquiries/{fake_id}/status").status_code == 302
    assert client.post(f"/admin/enquiries/{fake_id}/retry-notification").status_code == 302


def test_admin_can_list_enquiries_and_filter(client, db_session, sample_admin):
    """Admin can list enquiries with filter by review status and notification delivery status."""
    login_admin(client, sample_admin)

    # Create enquiries with different states
    e1 = create_sample_enquiry(db_session, email="new@example.com", status="new", notification_status="sent")
    e2 = create_sample_enquiry(db_session, email="review@example.com", status="in_review", notification_status="pending")
    e3 = create_sample_enquiry(db_session, email="failed@example.com", status="closed", notification_status="failed", notification_attempts=2)

    # List all
    res_all = client.get("/admin/enquiries")
    assert res_all.status_code == 200
    html_all = res_all.get_data(as_text=True)
    assert "new@example.com" in html_all
    assert "review@example.com" in html_all
    assert "failed@example.com" in html_all

    # Filter status=new
    res_new = client.get("/admin/enquiries?status=new")
    assert res_new.status_code == 200
    html_new = res_new.get_data(as_text=True)
    assert "new@example.com" in html_new
    assert "review@example.com" not in html_new

    # Filter notification_status=failed
    res_failed = client.get("/admin/enquiries?notification_status=failed")
    assert res_failed.status_code == 200
    html_failed = res_failed.get_data(as_text=True)
    assert "failed@example.com" in html_failed
    assert "new@example.com" not in html_failed


def test_admin_enquiry_detail_safely_escapes_user_content(client, db_session, sample_admin):
    """Admin detail page displays enquiry content with HTML escaping preventing stored XSS."""
    login_admin(client, sample_admin)

    malicious_subject = "<script>alert('pwned')</script>"
    malicious_message = '<b onmouseover="alert(1)">Dangerous Tag</b> & "special"'
    enquiry = create_sample_enquiry(
        db_session,
        subject=malicious_subject,
        message=malicious_message,
    )

    response = client.get(f"/admin/enquiries/{enquiry.id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Content must be HTML-escaped, not executed as raw unescaped HTML
    assert "&lt;script&gt;alert(&#39;pwned&#39;)&lt;/script&gt;" in html or "&lt;script&gt;" in html
    assert "<script>alert('pwned')</script>" not in html


def test_admin_can_update_enquiry_status(client, db_session, sample_admin):
    """Admin can update an enquiry's review status (new -> in_review -> closed) with audit logging."""
    login_admin(client, sample_admin)
    enquiry = create_sample_enquiry(db_session, status="new")

    response = client.post(
        f"/admin/enquiries/{enquiry.id}/status",
        data={"status": "in_review"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "status updated to &#39;in_review&#39;" in response.get_data(as_text=True)

    reloaded = db_session.get(Enquiry, enquiry.id)
    assert reloaded.status == "in_review"

    # Audit event logged
    audit = AdminAuditEvent.query.filter_by(event_type="update_enquiry_status").first()
    assert audit is not None
    assert audit.safe_metadata["new_status"] == "in_review"


def test_admin_can_retry_failed_notification(client, db_session, sample_admin):
    """Admin can retry a failed notification delivery; attempt counter increments and audit event is logged."""
    login_admin(client, sample_admin)
    enquiry = create_sample_enquiry(
        db_session,
        notification_status="failed",
        notification_attempts=1,
        notification_error_code="SMTP_CONNECT_ERROR",
    )

    with patch("app.extensions.mail.send") as mock_send:
        mock_send.return_value = None  # Simulate successful delivery on retry

        response = client.post(
            f"/admin/enquiries/{enquiry.id}/retry-notification",
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "notification delivered successfully" in html

        reloaded = db_session.get(Enquiry, enquiry.id)
        assert reloaded.notification_status == "sent"
        assert reloaded.notification_attempts == 2
        assert reloaded.notification_error_code is None
        assert reloaded.notification_sent_at is not None

        # Verify audit log
        audit = AdminAuditEvent.query.filter_by(event_type="retry_enquiry_notification").first()
        assert audit is not None
        assert audit.safe_metadata["success"] is True
        assert audit.safe_metadata["attempts"] == 2


def test_admin_retry_notification_handles_repeated_failure_cleanly(client, db_session, sample_admin):
    """When a notification retry fails again, attempt counter increments, error code updates, and admin is notified."""
    login_admin(client, sample_admin)
    enquiry = create_sample_enquiry(
        db_session,
        notification_status="failed",
        notification_attempts=1,
        notification_error_code="SMTP_CONNECT_ERROR",
    )

    with patch("app.extensions.mail.send", side_effect=smtplib.SMTPAuthenticationError(535, b"Bad credentials")):
        response = client.post(
            f"/admin/enquiries/{enquiry.id}/retry-notification",
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Notification retry failed (SMTP_AUTH_ERROR)" in html

        reloaded = db_session.get(Enquiry, enquiry.id)
        assert reloaded.notification_status == "failed"
        assert reloaded.notification_attempts == 2
        assert reloaded.notification_error_code == "SMTP_AUTH_ERROR"
