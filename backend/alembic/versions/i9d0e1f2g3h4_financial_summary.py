"""add financial_summaries table

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-05-13 22:00:00.000000

Project-level OZET cash-flow summary, one row per (project, company).
Powers the two side-by-side OZET tables on the Expenses page.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9d0e1f2g3h4"
down_revision: Union[str, None] = "h8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_label", sa.String(length=50), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("isveren_tahsilatlari", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("firma_odemeleri",      sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("ucret_giderleri",      sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("vergi_odemeleri",      sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("gelir_vergisi",        sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("kdv",                  sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("faiz_gelirleri",       sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("banka_giderleri",      sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("diger_gelir_giderler", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("toplam",               sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_id", "company_label", name="uq_financial_summary_project_company"
        ),
    )
    op.create_index(
        "ix_financial_summaries_project_id",
        "financial_summaries",
        ["project_id"],
    )
    op.create_index(
        "ix_financial_summary_project_company",
        "financial_summaries",
        ["project_id", "company_label"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_summary_project_company", table_name="financial_summaries")
    op.drop_index("ix_financial_summaries_project_id", table_name="financial_summaries")
    op.drop_table("financial_summaries")
