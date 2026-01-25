"""dedupe evidences and ensure unique index for (scope, owner_id, document_type_id, file_id)

Revision ID: c3d4e5f6a7b8
Revises: 9a1c3b4d5e6f
Create Date: 2026-01-11

"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "9a1c3b4d5e6f"
branch_labels = None
depends_on = None


INDEX_NAME = "uniq_scope_owner_doc_file"
TABLE_NAME = "evidences"


def _get_index_non_unique(conn):
    """
    Returns:
      None -> index not exists
      0    -> exists and UNIQUE
      1    -> exists but NON-UNIQUE
    """
    row = conn.execute(
        sa.text(
            """
            SELECT NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :t
              AND INDEX_NAME = :i
            LIMIT 1
            """
        ),
        {"t": TABLE_NAME, "i": INDEX_NAME},
    ).fetchone()
    return None if row is None else int(row[0])


def upgrade():
    conn = op.get_bind()

    # 1) 先清理历史重复行：同一挂载只保留最早 created_at 的那条
    op.execute(
        """
        DELETE e1
        FROM evidences e1
        JOIN evidences e2
          ON e1.scope = e2.scope
         AND e1.owner_id = e2.owner_id
         AND e1.document_type_id = e2.document_type_id
         AND e1.file_id = e2.file_id
         AND (
              e1.created_at > e2.created_at
              OR (e1.created_at = e2.created_at AND e1.id > e2.id)
         );
        """
    )

    # 2) 确保唯一索引/约束存在（幂等）
    non_unique = _get_index_non_unique(conn)

    if non_unique is None:
        # 不存在：创建唯一约束（MySQL 会创建同名唯一索引）
        op.create_unique_constraint(
            INDEX_NAME,
            TABLE_NAME,
            ["scope", "owner_id", "document_type_id", "file_id"],
        )
        return

    if non_unique == 1:
        # 存在但非唯一：先删索引再建唯一
        op.execute(f"ALTER TABLE {TABLE_NAME} DROP INDEX {INDEX_NAME};")
        op.create_unique_constraint(
            INDEX_NAME,
            TABLE_NAME,
            ["scope", "owner_id", "document_type_id", "file_id"],
        )
        return

    # non_unique == 0 代表已经是唯一：直接跳过
    return


def downgrade():
    conn = op.get_bind()
    non_unique = _get_index_non_unique(conn)
    if non_unique is None:
        return

    # MySQL 中 unique constraint 本质是 unique index：直接 DROP INDEX 即可
    op.execute(f"ALTER TABLE {TABLE_NAME} DROP INDEX {INDEX_NAME};")
