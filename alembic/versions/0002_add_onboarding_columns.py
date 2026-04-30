"""add onboarding columns to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_step", sa.String(), nullable=True),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed_at", schema="public")
    op.drop_column("users", "onboarding_step", schema="public")
