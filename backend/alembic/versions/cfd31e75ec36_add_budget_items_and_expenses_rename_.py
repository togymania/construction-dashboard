"""add budget_items and expenses, rename budget_usd

Revision ID: cfd31e75ec36
Revises: 4471f8faa177
Create Date: 2026-04-25 10:04:54.247043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfd31e75ec36'
down_revision: Union[str, None] = '4471f8faa177'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum value lists (lowercase to match Python enum .value attribute)
BUDGET_CATEGORY_VALUES = ('labor', 'materials', 'equipment', 'subcontractor', 'permits', 'other')
EXPENSE_STATUS_VALUES = ('pending', 'approved', 'paid', 'rejected')


def upgrade() -> None:
    # --- 1. Project table: rename budget_usd -> budget_rub, drop budget_spent_usd ---
    # Rename preserves existing data in the 6 seed projects.
    op.alter_column(
        'projects',
        'budget_usd',
        new_column_name='budget_rub',
        type_=sa.Numeric(precision=18, scale=2),
        existing_type=sa.Numeric(precision=15, scale=2),
        existing_nullable=False,
    )
    op.drop_column('projects', 'budget_spent_usd')

    # --- 2. budget_items table (creates budget_category enum implicitly) ---
    op.create_table(
        'budget_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column(
            'category',
            sa.Enum(*BUDGET_CATEGORY_VALUES, name='budget_category'),
            nullable=False,
        ),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('planned_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_budget_items_category'), 'budget_items', ['category'], unique=False)
    op.create_index(op.f('ix_budget_items_id'), 'budget_items', ['id'], unique=False)
    op.create_index(op.f('ix_budget_items_project_id'), 'budget_items', ['project_id'], unique=False)

    # --- 3. expenses table (REUSE budget_category, create expense_status) ---
    op.create_table(
        'expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('budget_item_id', sa.Integer(), nullable=True),
        sa.Column(
            'category',
            sa.Enum(*BUDGET_CATEGORY_VALUES, name='budget_category', create_type=False),
            nullable=False,
        ),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('vendor', sa.String(length=255), nullable=True),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum(*EXPENSE_STATUS_VALUES, name='expense_status'),
            nullable=False,
        ),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['budget_item_id'], ['budget_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_expenses_budget_item_id'), 'expenses', ['budget_item_id'], unique=False)
    op.create_index(op.f('ix_expenses_category'), 'expenses', ['category'], unique=False)
    op.create_index(op.f('ix_expenses_created_by'), 'expenses', ['created_by'], unique=False)
    op.create_index(op.f('ix_expenses_expense_date'), 'expenses', ['expense_date'], unique=False)
    op.create_index(op.f('ix_expenses_id'), 'expenses', ['id'], unique=False)
    op.create_index(op.f('ix_expenses_project_id'), 'expenses', ['project_id'], unique=False)
    op.create_index(op.f('ix_expenses_status'), 'expenses', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_expenses_status'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_project_id'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_id'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_expense_date'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_created_by'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_category'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_budget_item_id'), table_name='expenses')
    op.drop_table('expenses')

    op.drop_index(op.f('ix_budget_items_project_id'), table_name='budget_items')
    op.drop_index(op.f('ix_budget_items_id'), table_name='budget_items')
    op.drop_index(op.f('ix_budget_items_category'), table_name='budget_items')
    op.drop_table('budget_items')

    # Drop enums explicitly (since both tables that used them are gone now)
    sa.Enum(name='expense_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='budget_category').drop(op.get_bind(), checkfirst=True)

    # Revert projects table changes
    op.add_column(
        'projects',
        sa.Column('budget_spent_usd', sa.NUMERIC(precision=15, scale=2), server_default='0', nullable=False),
    )
    op.alter_column(
        'projects',
        'budget_rub',
        new_column_name='budget_usd',
        type_=sa.Numeric(precision=15, scale=2),
        existing_type=sa.Numeric(precision=18, scale=2),
        existing_nullable=False,
    )
