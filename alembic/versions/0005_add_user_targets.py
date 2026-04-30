"""add profile + daily target columns to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Onboarding inputs we keep so the user can re-edit later, plus the resolved
# daily targets the home screen renders.
_PROFILE_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("gender", sa.String(length=20)),
    ("dob", sa.Date()),
    ("height_cm", sa.Float()),
    ("weight_kg", sa.Float()),
    ("target_weight_kg", sa.Float()),
    ("activity_level", sa.String(length=20)),
    ("goal", sa.String(length=20)),
    ("pace", sa.String(length=20)),
    ("target_calories_kcal", sa.Integer()),
    ("target_protein_g", sa.Integer()),
    ("target_carbs_g", sa.Integer()),
    ("target_fat_g", sa.Integer()),
    ("target_water_ml", sa.Integer()),
)


def upgrade() -> None:
    for name, type_ in _PROFILE_COLUMNS:
        op.add_column(
            "users",
            sa.Column(name, type_, nullable=True),
            schema="public",
        )


def downgrade() -> None:
    for name, _ in reversed(_PROFILE_COLUMNS):
        op.drop_column("users", name, schema="public")
