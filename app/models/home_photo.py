"""HomePagePhoto model for hero background showcase.

Enforces:
- DATABASE_SCHEMA.md Section 8a
- ADR-010 (Dedicated home page photo entity distinct from portfolio media)
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class HomePagePhoto(db.Model):
    """Home page hero background photo gallery asset.
    
    Isolated from portfolio project assets per ADR-010 and DATABASE_SCHEMA.md Section 8a.
    """
    __tablename__ = "home_page_photo"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=True)
    caption = db.Column(db.Text, nullable=True)
    cloudinary_public_id = db.Column(db.String(255), nullable=False, unique=True)
    secure_url = db.Column(db.String(1024), nullable=False)
    alt_text = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
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
        db.CheckConstraint("display_order >= 0", name="ck_home_page_photo_display_order_nonneg"),
        db.Index("ix_home_page_photo_active_order", "is_active", "display_order"),
    )

    def __repr__(self) -> str:
        return f"<HomePagePhoto {self.id} (order={self.display_order}, active={self.is_active})>"
