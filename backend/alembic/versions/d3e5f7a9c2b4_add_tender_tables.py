"""add tender + bid tables

Revision ID: d3e5f7a9c2b4
Revises: c2d4e6f8a1b3
Create Date: 2026-05-13 12:00:00.000000

Adds the four tables that power the in-app tender (ihale) module:

    tenders
        Header for one work package put out to bid on a project.
    tender_line_items
        The metraj/keşif rows: description + unit + quantity.
    bids
        One row per bidding company per tender.
    bid_line_items
        The cross of (line item × bid) — each cell of the comparison grid.

The bid_line_items table carries BOTH a split unit price (labor +
material) AND a combined total. When the source document gives a single
combined price we leave the labor/material columns NULL and only fill
unit_price_total. The frontend uses the presence of labor/material to
decide whether to render a single column or the three-column split.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e5f7a9c2b4"
down_revision: Union[str, None] = "c2d4e6f8a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tenders ----
    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column("payment_terms_expected", sa.Text(), nullable=True),
        sa.Column("delivery_terms_expected", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "open",
                "evaluating",
                "awarded",
                "cancelled",
                name="tender_status",
            ),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("awarded_bid_id", sa.Integer(), nullable=True),
        sa.Column("source_filename", sa.String(length=500), nullable=True),
        sa.Column(
            "extracted_by_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
    op.create_index("ix_tenders_project_id", "tenders", ["project_id"])
    op.create_index("ix_tenders_status", "tenders", ["status"])
    op.create_index(
        "ix_tenders_project_status", "tenders", ["project_id", "status"]
    )

    # ---- tender_line_items ----
    op.create_table(
        "tender_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tender_id",
            sa.Integer(),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_num", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column(
            "quantity",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("tender_id", "order_num", name="uq_tender_line_order"),
        sa.CheckConstraint("quantity >= 0", name="ck_tender_line_qty_nonneg"),
    )
    op.create_index("ix_tender_line_items_tender_id", "tender_line_items", ["tender_id"])

    # ---- bids ----
    op.create_table(
        "bids",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tender_id",
            sa.Integer(),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subcontractor_id",
            sa.Integer(),
            sa.ForeignKey("subcontractors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("included_in_price", sa.Text(), nullable=True),
        sa.Column("not_included_in_price", sa.Text(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "total_labor",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_material",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.Enum(
                "invited",
                "received",
                "withdrawn",
                "selected",
                name="bid_status",
            ),
            nullable=False,
            server_default=sa.text("'invited'"),
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("tender_id", "company_name", name="uq_bid_tender_company"),
        sa.CheckConstraint("total_amount >= 0", name="ck_bid_total_nonneg"),
        sa.CheckConstraint(
            "delivery_days IS NULL OR delivery_days >= 0",
            name="ck_bid_delivery_nonneg",
        ),
    )
    op.create_index("ix_bids_tender_id", "bids", ["tender_id"])
    op.create_index("ix_bids_subcontractor_id", "bids", ["subcontractor_id"])
    op.create_index("ix_bids_status", "bids", ["status"])

    # Now that bids exists we can add the FK from tenders.awarded_bid_id
    op.create_foreign_key(
        "fk_tenders_awarded_bid_id",
        "tenders",
        "bids",
        ["awarded_bid_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- bid_line_items ----
    op.create_table(
        "bid_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "bid_id",
            sa.Integer(),
            sa.ForeignKey("bids.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tender_line_item_id",
            sa.Integer(),
            sa.ForeignKey("tender_line_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unit_price_labor", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price_material", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "unit_price_total",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "line_total",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "bid_id",
            "tender_line_item_id",
            name="uq_bid_line_per_tender_item",
        ),
        sa.CheckConstraint("unit_price_total >= 0", name="ck_bid_line_unit_nonneg"),
        sa.CheckConstraint("line_total >= 0", name="ck_bid_line_total_nonneg"),
    )
    op.create_index("ix_bid_line_items_bid_id", "bid_line_items", ["bid_id"])
    op.create_index(
        "ix_bid_line_items_tender_line_item_id",
        "bid_line_items",
        ["tender_line_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bid_line_items_tender_line_item_id", table_name="bid_line_items")
    op.drop_index("ix_bid_line_items_bid_id", table_name="bid_line_items")
    op.drop_table("bid_line_items")

    op.drop_constraint("fk_tenders_awarded_bid_id", "tenders", type_="foreignkey")

    op.drop_index("ix_bids_status", table_name="bids")
    op.drop_index("ix_bids_subcontractor_id", table_name="bids")
    op.drop_index("ix_bids_tender_id", table_name="bids")
    op.drop_table("bids")
    op.execute("DROP TYPE IF EXISTS bid_status")

    op.drop_index("ix_tender_line_items_tender_id", table_name="tender_line_items")
    op.drop_table("tender_line_items")

    op.drop_index("ix_tenders_project_status", table_name="tenders")
    op.drop_index("ix_tenders_status", table_name="tenders")
    op.drop_index("ix_tenders_project_id", table_name="tenders")
    op.drop_table("tenders")
    op.execute("DROP TYPE IF EXISTS tender_status")
