"""add match_suggestions table (Faz 1 — reconciliation review queue)

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2g3h4
Create Date: 2026-06-03 06:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, None] = "i9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the match_suggestions review queue."""
    op.create_table(
        "match_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ledger_entry_id",
            sa.Integer(),
            sa.ForeignKey("ledger_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "field",
            sa.Enum("budget_code", "subcontractor_id", name="suggestion_field"),
            nullable=False,
        ),
        sa.Column("proposed_value", sa.String(length=100), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("candidate_label", sa.String(length=500), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="suggestion_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    )

    op.create_index(
        "ix_match_suggestions_ledger_entry_id",
        "match_suggestions",
        ["ledger_entry_id"],
    )
    op.create_index("ix_match_suggestions_field", "match_suggestions", ["field"])
    op.create_index("ix_match_suggestions_status", "match_suggestions", ["status"])
    op.create_index(
        "ix_match_suggestions_entry_field",
        "match_suggestions",
        ["ledger_entry_id", "field"],
    )


def downgrade() -> None:
    op.drop_index("ix_match_suggestions_entry_field", table_name="match_suggestions")
    op.drop_index("ix_match_suggestions_status", table_name="match_suggestions")
    op.drop_index("ix_match_suggestions_field", table_name="match_suggestions")
    op.drop_index(
        "ix_match_suggestions_ledger_entry_id", table_name="match_suggestions"
    )
    op.drop_table("match_suggestions")
    op.execute("DROP TYPE IF EXISTS suggestion_status")
    op.execute("DROP TYPE IF EXISTS suggestion_field")
