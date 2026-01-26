"""create jobs table

Revision ID: 2b4c5d6e7f8h
Revises: 2a3b4c5d6e7f
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "2b4c5d6e7f8h"
down_revision = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    # 1) jobs 表不存在才创建
    if "jobs" not in insp.get_table_names():
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("file_id", sa.String(36), nullable=False),
            sa.Column("script_id", sa.String(128), nullable=False),
            sa.Column("model_id", sa.String(128), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("stage", sa.String(64), nullable=False),
            sa.Column("progress", sa.Integer(), nullable=False),
            sa.Column("artifact_json_path", sa.String(512), nullable=True),
            sa.Column("artifact_xlsx_path", sa.String(512), nullable=True),
            sa.Column("error_message", sa.String(2000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # 2) 索引不存在才创建（避免 Duplicate key name）
    idx_names = {ix["name"] for ix in insp.get_indexes("jobs")}
    if "ix_jobs_file_id" not in idx_names:
        op.create_index("ix_jobs_file_id", "jobs", ["file_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    if "jobs" not in insp.get_table_names():
        return

    idx_names = {ix["name"] for ix in insp.get_indexes("jobs")}
    if "ix_jobs_file_id" in idx_names:
        op.drop_index("ix_jobs_file_id", table_name="jobs")

    op.drop_table("jobs")
