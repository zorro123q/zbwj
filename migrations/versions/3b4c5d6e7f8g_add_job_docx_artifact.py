"""add docx artifact to jobs

Revision ID: 3b4c5d6e7f8g
Revises: 2a3b4c5d6e7f
Create Date: 2026-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "3b4c5d6e7f8g"
down_revision = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("artifact_docx_path", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("jobs", "artifact_docx_path")
