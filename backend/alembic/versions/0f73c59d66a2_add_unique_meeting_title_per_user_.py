# Alembic migration: enforce a unique meeting title per user.

"""add_unique_meeting_title_per_user_workspace

Revision ID: 0f73c59d66a2
Revises: 7e9f6f8ab7d9
Create Date: 2026-09-05 22:40:30.803757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0f73c59d66a2'
down_revision: Union[str, Sequence[str], None] = '7e9f6f8ab7d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_meeting_workspace_owner_title",
        "meetings",
        ["workspace_id", "owner_id", "title"],
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_meeting_workspace_owner_title",
        "meetings",
        type_="unique",
    )
