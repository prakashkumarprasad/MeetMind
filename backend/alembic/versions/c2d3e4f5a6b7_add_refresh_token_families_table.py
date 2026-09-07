# Alembic migration: create the refresh_token_families table.

"""add refresh_token_families table

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 00:00:00.000000

Adds server-side tracking of refresh-token families so a stolen refresh
token can be detected and revoked (see app/models/refresh_token_family.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "refresh_token_families",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default=sa.false(),
        ),
        sa.Column("last_jti", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_refresh_token_families_family_id",
        "refresh_token_families",
        ["family_id"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_token_families_user_id",
        "refresh_token_families",
        ["user_id"],
    )

def downgrade() -> None:
    op.drop_index("ix_refresh_token_families_user_id", table_name="refresh_token_families")
    op.drop_index("ix_refresh_token_families_family_id", table_name="refresh_token_families")
    op.drop_table("refresh_token_families")
