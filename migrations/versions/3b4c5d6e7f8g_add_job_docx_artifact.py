"""add docx artifact to jobs

Revision ID: 3b4c5d6e7f8g
Revises: 2b4c5d6e7f8h
Create Date: 2026-01-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "3b4c5d6e7f8g"
down_revision = "2b4c5d6e7f8h"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    # 确保 jobs 表存在（按你的库状态，应该由 2b... 迁移创建）
    if "jobs" not in insp.get_table_names():
        raise RuntimeError("jobs table does not exist; please run create_jobs_table migration first")

    cols = [c["name"] for c in insp.get_columns("jobs")]
    if "artifact_docx_path" not in cols:
        op.add_column("jobs", sa.Column("artifact_docx_path", sa.String(length=512), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    if "jobs" not in insp.get_table_names():
        return

    cols = [c["name"] for c in insp.get_columns("jobs")]
    if "artifact_docx_path" in cols:
        op.drop_column("jobs", "artifact_docx_path")
