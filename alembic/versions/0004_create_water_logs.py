"""create water_logs

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "water_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["public.users.id"],
            name="water_logs_user_id_fkey",
            ondelete="CASCADE",
        ),
        schema="public",
    )
    op.create_index(
        "water_logs_user_consumed_idx",
        "water_logs",
        ["user_id", "consumed_at"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "water_logs_user_consumed_idx", table_name="water_logs", schema="public"
    )
    op.drop_table("water_logs", schema="public")
