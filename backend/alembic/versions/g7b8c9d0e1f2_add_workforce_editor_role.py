"""add workforce_editor user role

Revision ID: g7b8c9d0e1f2
Revises: f5a7b9c1d3e6
Create Date: 2026-05-13 20:30:00.000000

Adds a new value to the ``user_role`` Postgres enum so we can grant a
narrow access profile (workforce module only) for demo / restricted
users. Existing rows are unaffected.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f5a7b9c1d3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires ALTER TYPE ... ADD VALUE outside of a transaction.
    op.execute("COMMIT")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'workforce_editor'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type, so
    # this downgrade is a no-op. Existing rows that used the value would
    # need to be migrated manually before recreating the enum.
    pass
