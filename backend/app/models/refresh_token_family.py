# SQLAlchemy model for server-side refresh-token family tracking.

"""
Server-side tracking of refresh-token families.

Each family is created once (on login / signup / Google OAuth) and
lives until the user logs out or a stolen-token reuse is detected.

Family -> many refresh tokens (rotation).  Only one refresh token in a
family is valid at any time (identified by ``last_jti``).  When a
refresh rotates, ``last_jti`` moves to the new token; if an *older*
token in the same family is presented, we know it's a replay of a
previously-rotated token and revoke the entire family.

``last_rotated_at`` records when the current ``last_jti`` was issued.
It lets the backend tell apart a *benign concurrent rotation* (multiple
open tabs presenting the same token within a few seconds - tolerated)
from a *genuine replay* of a stolen token much later (revoked).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class RefreshTokenFamily(Base):
    __tablename__ = "refresh_token_families"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False,
        default=uuid.uuid4,
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_jti: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    last_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
