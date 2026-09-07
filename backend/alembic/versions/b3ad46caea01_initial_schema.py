# Alembic migration: initial schema.

"""initial schema

Revision ID: b3ad46caea01
Revises: 
Create Date: 2026-08-30 00:27:22.983971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b3ad46caea01'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("hashed_password", sa.String, nullable=True),
        sa.Column("google_id", sa.String, nullable=True, unique=True),
        sa.Column("full_name", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    op.create_table(
        "meetings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("storage_key", sa.String, nullable=False),
        sa.Column("original_filename", sa.String, nullable=False),
        sa.Column("content_type", sa.String, nullable=False, server_default="audio/mpeg"),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("transcript_text", sa.Text, nullable=True),
        sa.Column("summary_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meetings_workspace_id", "meetings", ["workspace_id"])

    op.execute(
        "CREATE TABLE transcript_chunks ("
        "id UUID PRIMARY KEY, "
        "meeting_id UUID NOT NULL REFERENCES meetings(id), "
        "workspace_id UUID NOT NULL REFERENCES workspaces(id), "
        "chunk_text TEXT NOT NULL, "
        "chunk_index INTEGER NOT NULL, "
        "embedding vector(384) NOT NULL, "
        "created_at TIMESTAMPTZ NOT NULL"
        ")"
    )
    op.create_index("ix_transcript_chunks_workspace_id", "transcript_chunks", ["workspace_id"])
    op.execute(
        "CREATE INDEX ix_transcript_chunks_embedding ON transcript_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

def downgrade():
    op.drop_table("transcript_chunks")
    op.drop_table("meetings")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")
