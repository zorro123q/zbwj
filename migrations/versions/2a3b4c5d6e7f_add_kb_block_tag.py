"""add kb block tag

Revision ID: 2a3b4c5d6e7f
Revises: 1f2a3b4c5d6e
Create Date: 2026-01-20 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2a3b4c5d6e7f"
down_revision = "1f2a3b4c5d6e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("kb_blocks", sa.Column("tag", sa.String(length=64), nullable=True))
    op.create_index("ix_kb_blocks_tag", "kb_blocks", ["tag"], unique=False)


def downgrade():
    op.drop_index("ix_kb_blocks_tag", table_name="kb_blocks")
    op.drop_column("kb_blocks", "tag")
