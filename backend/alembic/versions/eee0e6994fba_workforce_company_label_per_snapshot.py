"""workforce_company_label_per_snapshot

Revision ID: eee0e6994fba
Revises: 70b1a888e789
Create Date: 2026-04-28 17:25:28.953485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eee0e6994fba'
down_revision: Union[str, None] = '70b1a888e789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company_label column + change UNIQUE constraint to include it.

    DB has been pre-truncated (no existing rows), so we set NOT NULL with default
    'Monotekstroy' which is safe even if future deployments have data (one company).
    """
    # 1. Add column with server default so existing rows (if any) get a value
    op.add_column(
        "workforce_snapshots",
        sa.Column(
            "company_label",
            sa.String(length=100),
            nullable=False,
            server_default="Monotekstroy",
        ),
    )

    # 2. Index on company_label for filtering
    op.create_index(
        "ix_workforce_snapshots_company_label",
        "workforce_snapshots",
        ["company_label"],
    )

    # 3. Drop old UNIQUE (project_id, snapshot_date)
    op.drop_constraint(
        "uq_workforce_snapshot_project_date",
        "workforce_snapshots",
        type_="unique",
    )

    # 4. Add new UNIQUE (project_id, snapshot_date, company_label)
    op.create_unique_constraint(
        "uq_workforce_snapshot_project_date_company",
        "workforce_snapshots",
        ["project_id", "snapshot_date", "company_label"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_workforce_snapshot_project_date_company",
        "workforce_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_workforce_snapshot_project_date",
        "workforce_snapshots",
        ["project_id", "snapshot_date"],
    )
    op.drop_index(
        "ix_workforce_snapshots_company_label",
        table_name="workforce_snapshots",
    )
    op.drop_column("workforce_snapshots", "company_label")
