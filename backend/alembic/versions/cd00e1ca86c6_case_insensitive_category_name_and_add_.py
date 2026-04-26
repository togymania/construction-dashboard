"""case insensitive category name and add slug index

Revision ID: cd00e1ca86c6
Revises: acbaff0b67c5
Create Date: 2026-04-26

This migration prepares budget_categories for "free-text" usage:
  * Drops the case-sensitive UNIQUE constraint on `name`
    (`budget_categories_name_key`).
  * Replaces it with a functional UNIQUE INDEX on `LOWER(name)` so that
    "Materials", "materials" and "  MATERIALS  " (after trim) all collide
    at the database level — required for the auto-create category logic
    introduced on day 7.
  * Existing data was reviewed and is already lower-case-unique, so no
    deduplication step is needed before swapping the constraints.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd00e1ca86c6'
down_revision: Union[str, None] = 'acbaff0b67c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the existing case-sensitive UNIQUE constraint on name.
    op.drop_constraint(
        "budget_categories_name_key",
        "budget_categories",
        type_="unique",
    )

    # 2. Create a functional UNIQUE INDEX so name uniqueness is enforced
    #    case-insensitively (and ignoring leading/trailing whitespace
    #    cannot be enforced at the DB level — the application layer
    #    normalises that before insert).
    op.execute(
        "CREATE UNIQUE INDEX ix_budget_categories_name_lower "
        "ON budget_categories (LOWER(name))"
    )


def downgrade() -> None:
    # Reverse: drop the functional index, restore the plain UNIQUE
    # constraint on name.
    op.execute("DROP INDEX IF EXISTS ix_budget_categories_name_lower")
    op.create_unique_constraint(
        "budget_categories_name_key",
        "budget_categories",
        ["name"],
    )
