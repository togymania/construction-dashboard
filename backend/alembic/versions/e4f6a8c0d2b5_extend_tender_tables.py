"""extend tender tables with hierarchy + variants + VAT + text-price

Revision ID: e4f6a8c0d2b5
Revises: d3e5f7a9c2b4
Create Date: 2026-05-13 18:00:00.000000

After auditing 50 real-world tender folders we discovered the v1 schema
couldn't represent the patterns that actually show up in supplier
quotations:

    * Hierarchical line items (1, 1.1, 1.2, 2, 2.a, ...). The v1 schema
      had a single flat `order_num` and no parent pointer.
    * Multiple variants from the same bidder (e.g. ООО АгроЦентрик
      submitting both a "Dairy Plus" and a "Terras" proposal). The v1
      unique constraint of (tender_id, company_name) blocked that.
    * Pure "Работы" (labor-only) sub-rows mixed under a package whose
      header carries the material price. The v1 schema couldn't tell the
      header apart from the line.
    * Free-text prices ("Договорная", "не включена", "по запросу"). The
      v1 schema required a numeric unit_price_total >= 0.
    * VAT (НДС) reported alongside the total. The v1 schema only kept
      one total figure and didn't say whether it was gross or net.

This migration adds the columns needed to fix all five problems and
keeps every default backfill-safe — existing rows get sensible values
without us having to write per-row update statements.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f6a8c0d2b5"
down_revision: Union[str, None] = "d3e5f7a9c2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Postgres enum types we'll create / drop in this migration
TENDER_LINE_TYPE_ENUM = sa.Enum(
    "package",
    "work",
    "material",
    "misc",
    name="tender_line_type",
)
BID_PRICE_TYPE_ENUM = sa.Enum(
    "fixed",
    "negotiable",
    "not_included",
    "on_request",
    name="bid_price_type",
)


def upgrade() -> None:
    bind = op.get_bind()

    # ----- new enum types --------------------------------------------------
    TENDER_LINE_TYPE_ENUM.create(bind, checkfirst=True)
    BID_PRICE_TYPE_ENUM.create(bind, checkfirst=True)

    # ----- tender_line_items: hierarchy + label + type --------------------
    op.add_column(
        "tender_line_items",
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("tender_line_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "tender_line_items",
        sa.Column("display_label", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "tender_line_items",
        sa.Column(
            "line_type",
            sa.Enum(
                "package",
                "work",
                "material",
                "misc",
                name="tender_line_type",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'misc'"),
        ),
    )
    op.create_index(
        "ix_tender_line_items_parent_id",
        "tender_line_items",
        ["parent_id"],
    )

    # ----- bids: VAT split + variant label --------------------------------
    op.add_column(
        "bids",
        sa.Column(
            "total_without_vat",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "bids",
        sa.Column(
            "vat_rate",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("20"),
        ),
    )
    op.add_column(
        "bids",
        sa.Column("variant_label", sa.String(length=120), nullable=True),
    )

    # Backfill: legacy rows had total_amount but no split. Treat the
    # existing total as inclusive-of-VAT and derive the net by dividing
    # by 1.20. This matches the company's standard НДС 20% expectation.
    op.execute(
        """
        UPDATE bids
           SET total_without_vat = ROUND(total_amount / 1.20, 2)
         WHERE total_without_vat = 0
           AND total_amount > 0
        """
    )

    # Replace (tender_id, company_name) with (tender_id, company_name, variant_label)
    op.drop_constraint("uq_bid_tender_company", "bids", type_="unique")
    op.create_unique_constraint(
        "uq_bid_tender_company_variant",
        "bids",
        ["tender_id", "company_name", "variant_label"],
    )

    # ----- bid_line_items: price_type + raw_text_price --------------------
    op.add_column(
        "bid_line_items",
        sa.Column(
            "price_type",
            sa.Enum(
                "fixed",
                "negotiable",
                "not_included",
                "on_request",
                name="bid_price_type",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'fixed'"),
        ),
    )
    op.add_column(
        "bid_line_items",
        sa.Column("raw_text_price", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    # ----- bid_line_items -------------------------------------------------
    op.drop_column("bid_line_items", "raw_text_price")
    op.drop_column("bid_line_items", "price_type")

    # ----- bids -----------------------------------------------------------
    op.drop_constraint(
        "uq_bid_tender_company_variant", "bids", type_="unique"
    )
    op.create_unique_constraint(
        "uq_bid_tender_company",
        "bids",
        ["tender_id", "company_name"],
    )
    op.drop_column("bids", "variant_label")
    op.drop_column("bids", "vat_rate")
    op.drop_column("bids", "total_without_vat")

    # ----- tender_line_items ---------------------------------------------
    op.drop_index(
        "ix_tender_line_items_parent_id", table_name="tender_line_items"
    )
    op.drop_column("tender_line_items", "line_type")
    op.drop_column("tender_line_items", "display_label")
    op.drop_column("tender_line_items", "parent_id")

    # ----- enum types -----------------------------------------------------
    bind = op.get_bind()
    BID_PRICE_TYPE_ENUM.drop(bind, checkfirst=True)
    TENDER_LINE_TYPE_ENUM.drop(bind, checkfirst=True)
