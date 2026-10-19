"""Portfolio data models.

Enforces ADR-004, ADR-009, and DATABASE_SCHEMA.md:
- UUID primary keys
- Foreign keys with deliberate cascade/restrict behavior
- Validated Cloudinary identifiers and YouTube video IDs
- Check constraints on display order and publication statuses
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class PortfolioCategory(db.Model):
    """Category classification for portfolio projects."""
    __tablename__ = "portfolio_category"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
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

    projects = db.relationship(
        "PortfolioProject",
        backref="category",
        lazy="dynamic",
        passive_deletes=False,
    )

    __table_args__ = (
        db.CheckConstraint("display_order >= 0", name="ck_portfolio_category_display_order_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<PortfolioCategory {self.name}>"


class PortfolioProject(db.Model):
    """Portfolio documentary or media project."""
    __tablename__ = "portfolio_project"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("portfolio_category.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_name = db.Column(db.String(255), nullable=True)
    project_date = db.Column(db.Date, nullable=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
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

    images = db.relationship(
        "PortfolioImage",
        backref="project",
        cascade="all, delete-orphan",
        order_by="PortfolioImage.display_order",
        lazy="joined",
    )
    videos = db.relationship(
        "PortfolioVideo",
        backref="project",
        cascade="all, delete-orphan",
        order_by="PortfolioVideo.display_order",
        lazy="joined",
    )

    __table_args__ = (
        db.CheckConstraint("status IN ('draft', 'published')", name="ck_portfolio_project_status"),
        db.CheckConstraint("display_order >= 0", name="ck_portfolio_project_display_order_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<PortfolioProject {self.title} ({self.status})>"


class PortfolioImage(db.Model):
    """Cloudinary-hosted image asset associated with a portfolio project."""
    __tablename__ = "portfolio_image"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("portfolio_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cloudinary_public_id = db.Column(db.String(255), unique=True, nullable=False)
    secure_url = db.Column(db.String(1024), nullable=False)
    alt_text = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(500), nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint("display_order >= 0", name="ck_portfolio_image_display_order_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<PortfolioImage {self.cloudinary_public_id}>"


class PortfolioVideo(db.Model):
    """Embedded YouTube video associated with a portfolio project."""
    __tablename__ = "portfolio_video"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("portfolio_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    youtube_video_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint("display_order >= 0", name="ck_portfolio_video_display_order_nonneg"),
    )

    @property
    def embed_url(self) -> str:
        """Safe privacy-enhanced YouTube embed URL."""
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_video_id}"

    def __repr__(self) -> str:
        return f"<PortfolioVideo {self.youtube_video_id}>"
