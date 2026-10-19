"""AdminUser and AdminAuditEvent models.

Enforces ADR-001, ADR-009, and DATABASE_SCHEMA.md specifications:
- UUID primary keys
- Normalized, unique emails
- Password hashing using Werkzeug
- AdminAuditEvent tracking without sensitive credentials
"""
import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.extensions import db


class AdminUser(UserMixin, db.Model):
    """Administrator user account."""
    __tablename__ = "admin_user"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    audit_events = db.relationship(
        "AdminAuditEvent",
        backref="admin_user",
        lazy="dynamic",
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint("email = lower(email)", name="ck_admin_user_email_lower"),
    )

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the password against stored hash."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        """Flask-Login user identifier."""
        return str(self.id)

    def __repr__(self) -> str:
        return f"<AdminUser {self.email}>"


class AdminAuditEvent(db.Model):
    """Minimal security and content audit log."""
    __tablename__ = "admin_audit_event"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("admin_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(UUID(as_uuid=True), nullable=True)
    occurred_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    safe_metadata = db.Column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<AdminAuditEvent {self.event_type} at {self.occurred_at}>"
