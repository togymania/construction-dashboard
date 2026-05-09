"""add ledger_entries table

Revision ID: b1c2d3e4f5a6
Revises: a8f1d2e3b4c5
Create Date: 2026-05-03 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a8f1d2e3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ledger_entries table for HIPODROM Excel-imported income/expense ledger."""
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("kod", sa.String(length=50), nullable=True),
        sa.Column("account", sa.String(length=100), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum("income", "expense", name="ledger_entry_type"),
            nullable=False,
        ),
        sa.Column("budget_code", sa.String(length=50), nullable=True),
        sa.Column(
            "subcontractor_id",
            sa.Integer(),
            sa.ForeignKey("subcontractors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "contract_id",
            sa.Integer(),
            sa.ForeignKey("subcontractor_contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dedup_hash", sa.String(length=64), nullable=False),
        sa.Column("source_filename", sa.String(length=500), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        sa.UniqueConstraint("dedup_hash", name="uq_ledger_entries_dedup_hash"),
    )

    # Indices
    op.create_index("ix_ledger_entries_entry_date", "ledger_entries", ["entry_date"])
    op.create_index("ix_ledger_entries_company_name", "ledger_entries", ["company_name"])
    op.create_index("ix_ledger_entries_kod", "ledger_entries", ["kod"])
    op.create_index("ix_ledger_entries_entry_type", "ledger_entries", ["entry_type"])
    op.create_index("ix_ledger_entries_budget_code", "ledger_entries", ["budget_code"])
    op.create_index("ix_ledger_entries_subcontractor_id", "ledger_entries", ["subcontractor_id"])
    op.create_index("ix_ledger_entries_contract_id", "ledger_entries", ["contract_id"])
    op.create_index("ix_ledger_entries_dedup_hash", "ledger_entries", ["dedup_hash"])
    op.create_index(
        "ix_ledger_entries_company_lower",
        "ledger_entries",
        [sa.text("lower(company_name)")],
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_company_lower", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_dedup_hash", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_contract_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_subcontractor_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_budget_code", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_entry_type", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_kod", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_company_name", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_entry_date", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.execute("DROP TYPE IF EXISTS ledger_entry_type")
