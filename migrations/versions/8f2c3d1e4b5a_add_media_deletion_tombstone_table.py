"""Add media deletion tombstone table.

Revision ID: 8f2c3d1e4b5a
Revises: 2b1b4e039058
Create Date: 2026-11-03 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8f2c3d1e4b5a'
down_revision = '2b1b4e039058'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'media_deletion_tombstone',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asset_type', sa.String(length=50), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(length=255), nullable=True),
        sa.Column('title_or_name', sa.String(length=255), nullable=True),
        sa.Column('original_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_media_deletion_tombstone_asset_type', 'media_deletion_tombstone', ['asset_type'], unique=False)
    op.create_index('ix_media_deletion_tombstone_cloudinary_public_id', 'media_deletion_tombstone', ['cloudinary_public_id'], unique=False)
    op.create_index('ix_media_deletion_tombstone_title_or_name', 'media_deletion_tombstone', ['title_or_name'], unique=False)
    op.create_index('ix_tombstone_type_pid', 'media_deletion_tombstone', ['asset_type', 'cloudinary_public_id'], unique=False)
    op.create_index('ix_tombstone_type_title', 'media_deletion_tombstone', ['asset_type', 'title_or_name'], unique=False)


def downgrade():
    op.drop_index('ix_tombstone_type_title', table_name='media_deletion_tombstone')
    op.drop_index('ix_tombstone_type_pid', table_name='media_deletion_tombstone')
    op.drop_index('ix_media_deletion_tombstone_title_or_name', table_name='media_deletion_tombstone')
    op.drop_index('ix_media_deletion_tombstone_cloudinary_public_id', table_name='media_deletion_tombstone')
    op.drop_index('ix_media_deletion_tombstone_asset_type', table_name='media_deletion_tombstone')
    op.drop_table('media_deletion_tombstone')
