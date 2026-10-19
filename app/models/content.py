"""Page content and partner logo models.

Enforces DATABASE_SCHEMA.md:
- Restricted editable content keys without allowing arbitrary HTML or template injection
- Partner logo metadata linked to Cloudinary assets
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class PageContent(db.Model):
    """Allowlisted editable copy for static public pages."""
    __tablename__ = "page_content"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_key = db.Column(db.String(50), nullable=False)
    content_key = db.Column(db.String(50), nullable=False)
    content_value = db.Column(db.Text, nullable=False)
    updated_by_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("admin_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("page_key", "content_key", name="uq_page_content_key"),
    )

    def __repr__(self) -> str:
        return f"<PageContent {self.page_key}.{self.content_key}>"


class PartnerLogo(db.Model):
    """Client and partner brand logos for approved page sections."""
    __tablename__ = "partner_logo"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(150), nullable=False)
    logo_cloudinary_public_id = db.Column(db.String(255), nullable=False)
    logo_secure_url = db.Column(db.String(1024), nullable=False)
    website_url = db.Column(db.String(500), nullable=True)
    alt_text = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
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
        db.CheckConstraint("display_order >= 0", name="ck_partner_logo_display_order_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<PartnerLogo {self.name}>"
