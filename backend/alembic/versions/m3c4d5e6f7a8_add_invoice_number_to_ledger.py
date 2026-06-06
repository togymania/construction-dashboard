"""Add invoice_number to ledger_entries.

Lets payments be joined exactly to Cynteka invoices (invoice no + company)
for automatic budget-code assignment.

Revision ID: m3c4d5e6f7a8
Revises: l2b3c4d5e6f7
Create Date: 2026-06-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3c4d5e6f7a8"
down_revision: Union[str, None] = "l2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ledger_entries",
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_ledger_entries_invoice_number",
        "ledger_entries",
        ["invoice_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_invoice_number", table_name="ledger_entries")
    op.drop_column("ledger_entries", "invoice_number")
