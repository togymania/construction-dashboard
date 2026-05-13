"""bid quote_date + revision_no + parent_bid_id + superseded status

Revision ID: f5a7b9c1d3e6
Revises: e4f6a8c0d2b5
Create Date: 2026-05-13 16:00:00.000000

User feedback after the first demo: pazarlık tarihçesini koruyalım. The
same supplier often resubmits a sharpened price two weeks later — we
want both numbers in the file but only the latest one in the
comparison grid.

This migration adds three columns to ``bids``:

    * ``quote_date``    — the date the bidder wrote at the top of their
                          PDF / КП form (NOT our received_at timestamp).
    * ``revision_no``   — 1 for the first offer in a chain, N+1 for
                          each subsequent revision.
    * ``parent_bid_id`` — self-FK pointing at the predecessor in the
                          revision chain. NULL for the original offer.

And appends a new ``superseded`` value to the ``bid_status`` enum so
older revisions can be flipped out of the comparison without losing
the row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5a7b9c1d3e6"
down_revision: Union[str, None] = "e4f6a8c0d2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----- new enum value: 'superseded' on bid_status ---------------------
    # Postgres enums must be ALTER TYPE ... ADD VALUE'd; cannot be done
    # inside a wrapped transaction so we COMMIT first.
    op.execute("COMMIT")
    op.execute("ALTER TYPE bid_status ADD VALUE IF NOT EXISTS 'superseded'")

    # ----- new columns ----------------------------------------------------
    op.add_column(
        "bids",
        sa.Column("quote_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "bids",
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "bids",
        sa.Column(
            "parent_bid_id",
            sa.Integer(),
            sa.ForeignKey("bids.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_bids_parent_bid_id", "bids", ["parent_bid_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_bids_parent_bid_id", table_name="bids")
    op.drop_column("bids", "parent_bid_id")
    op.drop_column("bids", "revision_no")
    op.drop_column("bids", "quote_date")
    # NOTE: PostgreSQL does not support removing values from an enum
    # type, so 'superseded' stays in the bid_status enum even after
    # downgrade. That's a no-op for existing data (no row should still
    # carry that value because superseded bids would have been
    # promoted back to received during the downgrade workflow).
