# Alembic migration: track when a refresh-token family last rotated.

"""add last_rotated_at to refresh_token_families

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-09-07 00:00:00.000000

Adds a timestamp for the most recent rotation within a refresh-token family.
This lets auth.py distinguish a benign concurrent refresh (multiple open tabs
the same token within a short grace window) from a genuine stolen-token replay.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "refresh_token_families",
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("refresh_token_families", "last_rotated_at")
