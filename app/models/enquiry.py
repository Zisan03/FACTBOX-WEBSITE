"""Contact enquiry model.

Enforces ADR-006, PRD.md (FR-05), and DATABASE_SCHEMA.md:
- Submissions are committed to PostgreSQL before email delivery is attempted
- Tracks delivery attempt counts, timestamps, and error codes for safe retry
- Never drops an enquiry on SMTP failure
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class Enquiry(db.Model):
    """Client enquiry submitted through public contact channels."""
    __tablename__ = "enquiry"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = db.Column(db.String(150), nullable=False)
    organization = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="new",
        index=True,
    )
    notification_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    notification_attempts = db.Column(db.Integer, nullable=False, default=0)
    notification_last_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notification_error_code = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('new', 'in_review', 'closed')",
            name="ck_enquiry_status",
        ),
        db.CheckConstraint(
            "notification_status IN ('pending', 'sent', 'failed')",
            name="ck_enquiry_notification_status",
        ),
        db.CheckConstraint(
            "notification_attempts >= 0",
            name="ck_enquiry_notification_attempts_nonneg",
        ),
        db.CheckConstraint("email = lower(email)", name="ck_enquiry_email_lower"),
    )

    def __repr__(self) -> str:
        return f"<Enquiry {self.email} - {self.subject} ({self.status})>"
