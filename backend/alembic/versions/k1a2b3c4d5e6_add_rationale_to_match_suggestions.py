"""add rationale to match_suggestions (AI budget suggestion reasoning)

Revision ID: k1a2b3c4d5e6
Revises: j0e1f2a3b4c5
Create Date: 2026-06-03 15:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1a2b3c4d5e6"
down_revision: Union[str, None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "match_suggestions",
        sa.Column("rationale", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("match_suggestions", "rationale")
