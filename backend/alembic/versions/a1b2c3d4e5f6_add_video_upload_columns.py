# Alembic migration: add video upload columns to meetings.

"""add_video_upload_columns

Revision ID: a1b2c3d4e5f6
Revises: 0f73c59d66a2
Create Date: 2026-09-07 09:00:00.000000

Adds columns that support uploading video recordings and having them
converted to audio before transcription:
  * meetings.source_media_type — "audio" or "video"
  * meetings.error_message — human-readable failure reason
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0f73c59d66a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("meetings", sa.Column("source_media_type", sa.String(), server_default="audio", nullable=False))
    op.add_column("meetings", sa.Column("error_message", sa.Text(), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("meetings", "error_message")
    op.drop_column("meetings", "source_media_type")
