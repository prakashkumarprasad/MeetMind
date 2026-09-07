# Alembic migration: add multipart upload support to meetings.

"""add multipart_upload_id to meetings

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-07 00:00:00.000000

Adds an optional column to track the S3 multipart upload id for large files,
so the complete-upload / abort-upload endpoints can reference the in-flight
multipart upload persisted on the meeting row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("multipart_upload_id", sa.String(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("meetings", "multipart_upload_id")
