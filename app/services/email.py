"""Email notification service.

Enforces:
- ADR-005 (Gmail integration via environment credentials, graceful failure)
- ADR-006 (Enquiries committed to PostgreSQL before email attempt)
- PRD FR-05 & FR-06 (No enquiry loss on email failure; safe error classification; retryability)
"""
import logging
import socket
import smtplib
from datetime import datetime, timezone
from flask import current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models.enquiry import Enquiry

logger = logging.getLogger(__name__)


def build_enquiry_notification_message(enquiry: Enquiry) -> Message:
    """Construct internal notification email for company staff."""
    recipient = current_app.config.get("ENQUIRY_RECIPIENT") or "info@factboxconsult.com"
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@factboxconsult.com"
    subject = f"[Fact Box Consult Enquiry] {enquiry.subject} — {enquiry.full_name}"

    created_str = (
        enquiry.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        if enquiry.created_at
        else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    body = (
        "NEW CONTACT ENQUIRY RECEIVED\n"
        "========================================\n"
        f"Enquiry ID:    {enquiry.id}\n"
        f"Received At:   {created_str}\n"
        f"Full Name:     {enquiry.full_name}\n"
        f"Organization:  {enquiry.organization or 'Not provided'}\n"
        f"Email Address: {enquiry.email}\n"
        f"Phone:         {enquiry.phone or 'Not provided'}\n"
        f"Subject:       {enquiry.subject}\n"
        "----------------------------------------\n"
        "Message Body:\n"
        f"{enquiry.message}\n"
        "========================================\n"
        "Note: Review and respond to this enquiry via the administrator dashboard.\n"
    )

    msg = Message(
        subject=subject,
        recipients=[recipient],
        sender=sender,
        body=body,
    )
    return msg


def send_enquiry_notification(enquiry: Enquiry) -> tuple[bool, str | None]:
    """Deliver internal notification email via configured SMTP adapter.

    Returns:
        tuple (success: bool, error_code: str | None)
        Where error_code is a safe, enumerated code containing NO credentials,
        passwords, or server secrets.
    """
    try:
        msg = build_enquiry_notification_message(enquiry)
        mail.send(msg)
        logger.info(
            "Enquiry notification sent successfully for enquiry %s to %s",
            enquiry.id,
            current_app.config.get("ENQUIRY_RECIPIENT"),
        )
        return True, None

    except smtplib.SMTPAuthenticationError as exc:
        logger.warning(
            "SMTP authentication failed for enquiry notification %s: auth rejected",
            enquiry.id,
        )
        return False, "SMTP_AUTH_ERROR"

    except smtplib.SMTPConnectError as exc:
        logger.warning(
            "SMTP connection failed for enquiry notification %s: host unreachable",
            enquiry.id,
        )
        return False, "SMTP_CONNECT_ERROR"

    except smtplib.SMTPRecipientsRefused as exc:
        logger.warning(
            "SMTP recipient refused for enquiry notification %s",
            enquiry.id,
        )
        return False, "SMTP_RECIPIENT_REFUSED"

    except smtplib.SMTPServerDisconnected as exc:
        logger.warning(
            "SMTP server unexpectedly disconnected for enquiry notification %s",
            enquiry.id,
        )
        return False, "SMTP_SERVER_DISCONNECTED"

    except smtplib.SMTPResponseException as exc:
        logger.warning(
            "SMTP response error for enquiry notification %s (code %s)",
            enquiry.id,
            getattr(exc, "smtp_code", "unknown"),
        )
        return False, "SMTP_RESPONSE_ERROR"

    except (socket.timeout, TimeoutError) as exc:
        logger.warning(
            "SMTP timeout connecting or sending notification for enquiry %s",
            enquiry.id,
        )
        return False, "SMTP_TIMEOUT"

    except Exception as exc:
        logger.error(
            "Unexpected error sending enquiry notification %s: %s",
            enquiry.id,
            exc.__class__.__name__,
        )
        return False, "EMAIL_DELIVERY_FAILED"


def process_enquiry_notification(enquiry: Enquiry, is_retry: bool = False) -> tuple[bool, str | None]:
    """Execute notification delivery, updating database state and timestamps safely.

    Guarantees:
    - Attempt counter is incremented
    - Timestamps are updated
    - Safe error code is persisted on failure
    - Database commit is atomic for the status update
    """
    enquiry.notification_attempts += 1
    enquiry.notification_last_attempt_at = datetime.now(timezone.utc)

    success, error_code = send_enquiry_notification(enquiry)

    if success:
        enquiry.notification_status = "sent"
        enquiry.notification_sent_at = datetime.now(timezone.utc)
        enquiry.notification_error_code = None
    else:
        enquiry.notification_status = "failed"
        enquiry.notification_error_code = error_code

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(
            "Failed to persist notification status update for enquiry %s: %s",
            enquiry.id,
            exc,
        )

    return success, error_code


def send_password_reset_email(admin_user, reset_url: str) -> bool:
    """Send a secure password reset link to an administrator.

    Returns True if sent successfully, False otherwise.
    Safe: Logs only the admin ID without exposing reset token or server credentials.
    """
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@factboxconsult.com"
    subject = "[Fact Box Consult] Administrator Password Reset Request"
    body = (
        f"Hello,\n\n"
        f"A password reset request was submitted for your Fact Box Consult administrator account ({admin_user.email}).\n\n"
        f"To reset your password, visit the following secure link:\n"
        f"{reset_url}\n\n"
        f"This link will expire in 30 minutes. If you did not request a password reset, you can safely ignore this email; your account remains secure and your password unchanged.\n\n"
        f"— Fact Box Consult Security System\n"
    )

    msg = Message(
        subject=subject,
        recipients=[admin_user.email],
        sender=sender,
        body=body,
    )

    try:
        mail.send(msg)
        logger.info("Password reset email dispatched successfully to admin %s", admin_user.id)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to dispatch password reset email to admin %s: %s",
            admin_user.id,
            exc.__class__.__name__,
        )
        return False

