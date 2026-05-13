"""add WORKFORCE_EDITOR (uppercase) to user_role enum

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-05-13 21:00:00.000000

Önceki migration ('g7b8c9d0e1f2') enum'a 'workforce_editor' (lowercase)
ekledi. Ama SQLAlchemy `Enum(UserRole)` Python enum'un VALUE'sunu değil
NAME'ini DB'ye yazar — dolayısıyla 'WORKFORCE_EDITOR' (uppercase). Diğer
tüm değerler de uppercase olarak orijinal create_table'da yaratılmıştı
(ADMIN, PROJECT_MANAGER, ENGINEER, VIEWER). Bu migration eksik kalan
uppercase varyantı da ekler.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'WORKFORCE_EDITOR'")


def downgrade() -> None:
    pass
