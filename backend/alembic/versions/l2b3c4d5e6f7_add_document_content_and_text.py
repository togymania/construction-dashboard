"""Add persistent content + extracted text columns to contract_documents.

Render's filesystem is ephemeral: files written to disk vanish on each
deploy. Storing the raw bytes (capped) and the extracted plain text in
PostgreSQL makes documents durable and lets the AI assistant answer
questions about them without re-reading the (possibly missing) file.

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
Create Date: 2026-06-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2b3c4d5e6f7"
down_revision: Union[str, None] = "k1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contract_documents",
        sa.Column("content", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "contract_documents",
        sa.Column("text_content", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contract_documents", "text_content")
    op.drop_column("contract_documents", "content")
