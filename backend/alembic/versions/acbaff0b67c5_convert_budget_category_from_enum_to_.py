"""convert budget category from enum to table

Revision ID: acbaff0b67c5
Revises: cfd31e75ec36
Create Date: 2026-04-25 10:46:39.754665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'acbaff0b67c5'
down_revision: Union[str, None] = 'cfd31e75ec36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default seed: 6 system categories that ship with the app.
# These have is_system=True and cannot be deleted (only deactivated).
DEFAULT_CATEGORIES = [
    {"name": "Labor",          "slug": "labor",         "display_order": 10, "is_system": True, "is_active": True},
    {"name": "Materials",      "slug": "materials",     "display_order": 20, "is_system": True, "is_active": True},
    {"name": "Equipment",      "slug": "equipment",     "display_order": 30, "is_system": True, "is_active": True},
    {"name": "Subcontractor",  "slug": "subcontractor", "display_order": 40, "is_system": True, "is_active": True},
    {"name": "Permits",        "slug": "permits",       "display_order": 50, "is_system": True, "is_active": True},
    {"name": "Other",          "slug": "other",         "display_order": 60, "is_system": True, "is_active": True},
]


def upgrade() -> None:
    # --- 1. Create budget_categories table ---
    budget_categories = op.create_table(
        'budget_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_budget_categories_id'), 'budget_categories', ['id'], unique=False)
    op.create_index(op.f('ix_budget_categories_slug'), 'budget_categories', ['slug'], unique=True)

    # --- 2. Seed 6 default system categories ---
    op.bulk_insert(budget_categories, DEFAULT_CATEGORIES)

    # --- 3. budget_items: drop old category enum column, add category_id FK ---
    op.drop_index('ix_budget_items_category', table_name='budget_items')
    op.drop_column('budget_items', 'category')
    op.add_column(
        'budget_items',
        sa.Column('category_id', sa.Integer(), nullable=False),
    )
    op.create_index(op.f('ix_budget_items_category_id'), 'budget_items', ['category_id'], unique=False)
    op.create_foreign_key(
        'fk_budget_items_category_id',
        'budget_items', 'budget_categories',
        ['category_id'], ['id'],
        ondelete='RESTRICT',
    )

    # --- 4. expenses: drop old category enum column, add category_id FK ---
    op.drop_index('ix_expenses_category', table_name='expenses')
    op.drop_column('expenses', 'category')
    op.add_column(
        'expenses',
        sa.Column('category_id', sa.Integer(), nullable=False),
    )
    op.create_index(op.f('ix_expenses_category_id'), 'expenses', ['category_id'], unique=False)
    op.create_foreign_key(
        'fk_expenses_category_id',
        'expenses', 'budget_categories',
        ['category_id'], ['id'],
        ondelete='RESTRICT',
    )

    # --- 5. Drop the orphaned budget_category enum type from PostgreSQL ---
    # Both columns that used it are gone now, so the type is unused.
    sa.Enum(name='budget_category').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # --- 1. Recreate budget_category enum ---
    budget_category_enum = postgresql.ENUM(
        'labor', 'materials', 'equipment', 'subcontractor', 'permits', 'other',
        name='budget_category',
    )
    budget_category_enum.create(op.get_bind(), checkfirst=True)

    # --- 2. expenses: drop FK + category_id, restore category enum column ---
    op.drop_constraint('fk_expenses_category_id', 'expenses', type_='foreignkey')
    op.drop_index(op.f('ix_expenses_category_id'), table_name='expenses')
    op.drop_column('expenses', 'category_id')
    op.add_column(
        'expenses',
        sa.Column('category', budget_category_enum, autoincrement=False, nullable=False),
    )
    op.create_index('ix_expenses_category', 'expenses', ['category'], unique=False)

    # --- 3. budget_items: drop FK + category_id, restore category enum column ---
    op.drop_constraint('fk_budget_items_category_id', 'budget_items', type_='foreignkey')
    op.drop_index(op.f('ix_budget_items_category_id'), table_name='budget_items')
    op.drop_column('budget_items', 'category_id')
    op.add_column(
        'budget_items',
        sa.Column('category', budget_category_enum, autoincrement=False, nullable=False),
    )
    op.create_index('ix_budget_items_category', 'budget_items', ['category'], unique=False)

    # --- 4. Drop budget_categories table ---
    op.drop_index(op.f('ix_budget_categories_slug'), table_name='budget_categories')
    op.drop_index(op.f('ix_budget_categories_id'), table_name='budget_categories')
    op.drop_table('budget_categories')
