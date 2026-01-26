"""add kb documents and blocks

Revision ID: 1f2a3b4c5d6e
Revises: ebbc15beaee0
Create Date: 2026-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "1f2a3b4c5d6e"
down_revision = "ebbc15beaee0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_kb_documents_file_id", "kb_documents", ["file_id"], unique=False)

    op.create_table(
        "kb_blocks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("section_path", sa.String(length=512), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("start_idx", sa.Integer(), nullable=False),
        sa.Column("end_idx", sa.Integer(), nullable=False),
        sa.Column("block_docx_path", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_kb_blocks_doc_id", "kb_blocks", ["doc_id"], unique=False)


def downgrade():
    op.drop_index("ix_kb_blocks_doc_id", table_name="kb_blocks")
    op.drop_table("kb_blocks")
    op.drop_index("ix_scripts/full_mysql_schema.sqlkb_documents_file_id", table_name="kb_documents")
    op.drop_table("kb_documents")
