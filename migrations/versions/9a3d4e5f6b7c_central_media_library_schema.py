"""Add central media library schema and archival status.

Revision ID: 9a3d4e5f6b7c
Revises: 8f2c3d1e4b5a
Create Date: 2026-11-04 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9a3d4e5f6b7c'
down_revision = '8f2c3d1e4b5a'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add archival status to existing media models
    op.add_column('home_page_photo', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('partner_logo', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('portfolio_image', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('portfolio_image', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('portfolio_video', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # 2. Create website_media table for official brand assets, homepage videos, and approved website media
    op.create_table(
        'website_media',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='brand_asset'),
        sa.Column('media_type', sa.String(length=20), nullable=False, server_default='image'),
        sa.Column('cloudinary_public_id', sa.String(length=255), nullable=True),
        sa.Column('secure_url', sa.String(length=1024), nullable=True),
        sa.Column('youtube_video_id', sa.String(length=50), nullable=True),
        sa.Column('alt_text', sa.String(length=255), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='unpublished'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("status IN ('active', 'unpublished', 'archived')", name='ck_website_media_status'),
        sa.CheckConstraint("media_type IN ('image', 'video')", name='ck_website_media_type'),
        sa.CheckConstraint("display_order >= 0", name='ck_website_media_display_order_nonneg'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_website_media_category', 'website_media', ['category'], unique=False)
    op.create_index('ix_website_media_media_type', 'website_media', ['media_type'], unique=False)
    op.create_index('ix_website_media_status', 'website_media', ['status'], unique=False)
    op.create_index('ix_website_media_cloudinary_public_id', 'website_media', ['cloudinary_public_id'], unique=False)


def downgrade():
    op.drop_index('ix_website_media_cloudinary_public_id', table_name='website_media')
    op.drop_index('ix_website_media_status', table_name='website_media')
    op.drop_index('ix_website_media_media_type', table_name='website_media')
    op.drop_index('ix_website_media_category', table_name='website_media')
    op.drop_table('website_media')

    op.drop_column('portfolio_video', 'is_archived')
    op.drop_column('portfolio_image', 'is_archived')
    op.drop_column('portfolio_image', 'title')
    op.drop_column('partner_logo', 'is_archived')
    op.drop_column('home_page_photo', 'is_archived')

