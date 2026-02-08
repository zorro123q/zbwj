import sys
import os
from pathlib import Path
from sqlalchemy import text

# 将项目根目录加入路径
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db


def fix_collation():
    app = create_app()
    with app.app_context():
        print("Starting Collation Fix...")

        # 目标字符集和排序规则
        # 推荐使用 utf8mb4_unicode_ci 以获得最佳兼容性
        CHARSET = "utf8mb4"
        COLLATION = "utf8mb4_unicode_ci"

        tables = ["files", "kb_blocks", "jobs"]

        for table in tables:
            print(f"Converting table '{table}' to {CHARSET} / {COLLATION} ...")
            try:
                # CONVERT TOCHARACTER SET 会同时修改表默认值和现有列
                sql = f"ALTER TABLE {table} CONVERT TO CHARACTER SET {CHARSET} COLLATE {COLLATION}"
                db.session.execute(text(sql))
                db.session.commit()
                print(f"   -> Success: {table}")
            except Exception as e:
                print(f"   -> Failed: {e}")
                db.session.rollback()

        print("\nCollation fix completed.")


if __name__ == "__main__":
    fix_collation()