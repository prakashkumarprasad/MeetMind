# SQLAlchemy model for meetings and their processing state.

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.action_item import ActionItem
    from app.models.transcript_chunk import TranscriptChunk

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)

    storage_key: Mapped[str] = mapped_column(String, nullable=False)

    original_filename: Mapped[str] = mapped_column(String, nullable=False)

    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    content_type: Mapped[str] = mapped_column(String, nullable=False, default="application/octet-stream")

    source_media_type: Mapped[str] = mapped_column(String, nullable=False, default="audio")

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    transcript_text: Mapped[str] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    action_items: Mapped[list["ActionItem"]] = relationship(
        "ActionItem",
        cascade="all, delete-orphan",
        order_by="ActionItem.created_at",
    )

    transcript_chunks: Mapped[list["TranscriptChunk"]] = relationship(
        "TranscriptChunk",
        cascade="all, delete-orphan",
        order_by="TranscriptChunk.created_at",
    )
