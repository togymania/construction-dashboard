"""Add cost_code and committed_amount to budget_items

Revision ID: c2d4e6f8a1b3
Revises: b1c2d3e4f5a6
Create Date: 2026-05-09

Faz 2 — generic budget Excel parser support.

Adds two optional columns to ``budget_items``:

* ``cost_code``     — WBS / cost code string ("1.2.1.3" style). Indexed,
  nullable, not unique. Faz 3 (planned vs actual) will use this column to
  match expenses → budget rows when the user provides a cost code on
  expenses.
* ``committed_amount`` — money already committed via signed contracts /
  POs but not yet paid. Sits between planned and actual on the spend
  continuum. Defaults to 0 for backwards-compat with rows imported
  before this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d4e6f8a1b3"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "budget_items",
        sa.Column("cost_code", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_budget_items_cost_code",
        "budget_items",
        ["cost_code"],
        unique=False,
    )
    op.add_column(
        "budget_items",
        sa.Column(
            "committed_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("budget_items", "committed_amount")
    op.drop_index("ix_budget_items_cost_code", table_name="budget_items")
    op.drop_column("budget_items", "cost_code")
