"""add btree indexes for index/search

Revision ID: c1d2e3f4a5b6
Revises: 9a1c3b4d5e6f
Create Date: 2026-01-11
"""
from alembic import op


revision = "c1d2e3f4a5b6"
down_revision = "9a1c3b4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("idx_document_types_code", "document_types", ["code"], unique=False)
    op.create_index("idx_document_types_name", "document_types", ["name"], unique=False)
    op.create_index("idx_issuer", "evidences", ["issuer"], unique=False)


def downgrade():
    op.drop_index("idx_issuer", table_name="evidences")
    op.drop_index("idx_document_types_name", table_name="document_types")
    op.drop_index("idx_document_types_code", table_name="document_types")
