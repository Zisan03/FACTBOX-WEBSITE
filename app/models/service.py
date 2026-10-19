"""Service data model.

Enforces DATABASE_SCHEMA.md:
- UUID primary keys
- Unique slugs
- Plain text / sanitized summary and descriptions
- Check constraints on display order
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class Service(db.Model):
    """Core consulting and audiovisual service offered by Fact Box Consult."""
    __tablename__ = "service"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon_key = db.Column(db.String(50), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
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

    __table_args__ = (
        db.CheckConstraint("display_order >= 0", name="ck_service_display_order_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<Service {self.title}>"
