"""WebsiteMedia model for central media library assets.

Accommodates official brand assets, homepage videos, and approved website media
not tied exclusively to portfolio projects or hero background slideshows.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class WebsiteMedia(db.Model):
    """Central media asset for brand identity, videos, and general website media."""
    __tablename__ = "website_media"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="brand_asset", index=True)
    # Categories: 'brand_asset', 'homepage_video', 'website_media'
    media_type = db.Column(db.String(20), nullable=False, default="image", index=True)
    # 'image' or 'video'
    cloudinary_public_id = db.Column(db.String(255), nullable=True, index=True)
    secure_url = db.Column(db.String(1024), nullable=True)
    youtube_video_id = db.Column(db.String(50), nullable=True)
    alt_text = db.Column(db.String(255), nullable=True)
    caption = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="unpublished", index=True)
    # 'active', 'unpublished', 'archived'
    display_order = db.Column(db.Integer, nullable=False, default=0)
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
        db.CheckConstraint("status IN ('active', 'unpublished', 'archived')", name="ck_website_media_status"),
        db.CheckConstraint("media_type IN ('image', 'video')", name="ck_website_media_type"),
        db.CheckConstraint("display_order >= 0", name="ck_website_media_display_order_nonneg"),
    )

    @property
    def embed_url(self) -> str | None:
        """Return safe privacy-enhanced YouTube embed URL if YouTube video."""
        if self.youtube_video_id:
            return f"https://www.youtube-nocookie.com/embed/{self.youtube_video_id}"
        return None

    def __repr__(self) -> str:
        return f"<WebsiteMedia {self.title} ({self.category}, {self.status})>"

