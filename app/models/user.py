from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
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
    onboarding_step: Mapped[str | None] = mapped_column(String, nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Onboarding inputs (kept so the user can re-edit in a profile screen later).
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date(), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float(), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float(), nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Float(), nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pace: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Resolved daily targets the home screen reads.
    target_calories_kcal: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    target_protein_g: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    target_carbs_g: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    target_fat_g: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    target_water_ml: Mapped[int | None] = mapped_column(Integer(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
