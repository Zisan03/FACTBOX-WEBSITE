"""MediaDeletionTombstone model.

Records administrative deletions of media assets (home page photos, partner logos)
to guarantee that routine application deployments, code updates, and safe seed commands
never recreate or restore assets that an administrator deliberately removed.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.extensions import db


class MediaDeletionTombstone(db.Model):
    """Tombstone record tracking deliberately deleted media assets.
    
    Protects against automatic re-seeding on deployment while allowing
    deliberate administrator restoration.
    """
    __tablename__ = "media_deletion_tombstone"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_type = db.Column(db.String(50), nullable=False, index=True)  # 'home_page_photo', 'partner_logo'
    cloudinary_public_id = db.Column(db.String(255), nullable=True, index=True)
    title_or_name = db.Column(db.String(255), nullable=True, index=True)
    original_data = db.Column(JSONB, nullable=True)  # Complete snapshot of metadata for safe restoration
    deleted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_by = db.Column(db.String(255), nullable=True)  # Admin email if available
    reason = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.Index("ix_tombstone_type_pid", "asset_type", "cloudinary_public_id"),
        db.Index("ix_tombstone_type_title", "asset_type", "title_or_name"),
    )

    def __repr__(self) -> str:
        return f"<MediaDeletionTombstone {self.asset_type} pid={self.cloudinary_public_id} title={self.title_or_name}>"
