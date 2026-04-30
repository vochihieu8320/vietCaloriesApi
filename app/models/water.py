from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class WaterLog(Base):
    """A single water log entry — one row per drink/sip the user records."""

    __tablename__ = "water_logs"
    __table_args__ = (
        Index("water_logs_user_consumed_idx", "user_id", "consumed_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE", use_alter=True),
        nullable=False,
    )
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
