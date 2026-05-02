"""add contract_documents table

Revision ID: a8f1d2e3b4c5
Revises: eee0e6994fba
Create Date: 2026-05-01 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f1d2e3b4c5'
down_revision: str = 'eee0e6994fba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type if it doesn't exist (use raw SQL for safety)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_type') THEN
                CREATE TYPE document_type AS ENUM ('CONTRACT', 'INVOICE', 'ADDENDUM', 'REPORT');
            END IF;
        END$$;
    """)

    op.execute("""
        CREATE TABLE contract_documents (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES subcontractor_contracts(id) ON DELETE CASCADE,
            file_name VARCHAR(500) NOT NULL,
            file_path VARCHAR(1000) NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type VARCHAR(255) NOT NULL,
            file_type document_type NOT NULL DEFAULT 'CONTRACT',
            version INTEGER NOT NULL DEFAULT 1,
            extracted_data TEXT,
            uploaded_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.create_index('ix_contract_documents_id', 'contract_documents', ['id'])
    op.create_index('ix_contract_documents_contract_id', 'contract_documents', ['contract_id'])
    op.create_index('ix_contract_documents_file_type', 'contract_documents', ['file_type'])
    op.create_index('ix_contract_documents_uploaded_by', 'contract_documents', ['uploaded_by'])


def downgrade() -> None:
    op.drop_index('ix_contract_documents_uploaded_by', table_name='contract_documents')
    op.drop_index('ix_contract_documents_file_type', table_name='contract_documents')
    op.drop_index('ix_contract_documents_contract_id', table_name='contract_documents')
    op.drop_index('ix_contract_documents_id', table_name='contract_documents')
    op.drop_table('contract_documents')
