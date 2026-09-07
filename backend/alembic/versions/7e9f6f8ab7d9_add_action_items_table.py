# Alembic migration: create the action_items table.

"""add action_items table

Revision ID: 7e9f6f8ab7d9
Revises: e9e4cc5cf7c1
Create Date: 2026-09-05 00:08:55.344910

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql

from alembic import op
import sqlalchemy as sa

revision: str = '7e9f6f8ab7d9'
down_revision: Union[str, Sequence[str], None] = 'e9e4cc5cf7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_action_items_meeting_id", "action_items", ["meeting_id"])
    op.create_index("ix_action_items_workspace_id", "action_items", ["workspace_id"])

def downgrade() -> None:
    op.drop_index("ix_action_items_workspace_id", table_name="action_items")
    op.drop_index("ix_action_items_meeting_id", table_name="action_items")
    op.drop_table("action_items")
