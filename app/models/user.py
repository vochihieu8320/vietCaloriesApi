from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class User(Base):
    """Profile row in `public.users`, 1:1 with `auth.users.id` (Supabase-managed)."""

    __tablename__ = "users"
    __table_args__ = (
        Index("users_email_idx", "email"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE", use_alter=True),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
