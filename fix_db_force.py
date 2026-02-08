import sys
import os
from sqlalchemy import text

# 确保能导入 app
from app import create_app
from app.extensions import db


def force_fix_collation():
    app = create_app()
    with app.app_context():
        print("Starting FORCE Collation Fix...")

        # 1. 先删除 kb_blocks 上的所有外键约束 (这是导致转换失败的元凶)
        # 查询外键名称
        sql_get_fk = """
        SELECT CONSTRAINT_NAME 
        FROM information_schema.KEY_COLUMN_USAGE 
        WHERE TABLE_NAME = 'kb_blocks' 
        AND TABLE_SCHEMA = DATABASE() 
        AND REFERENCED_TABLE_NAME IS NOT NULL;
        """

        try:
            results = db.session.execute(text(sql_get_fk)).fetchall()
            for row in results:
                fk_name = row[0]
                print(f"Detected Foreign Key: {fk_name}, Dropping it...")
                try:
                    db.session.execute(text(f"ALTER TABLE kb_blocks DROP FOREIGN KEY {fk_name}"))
                    db.session.commit()
                    print(f"   -> Dropped FK: {fk_name}")
                except Exception as e:
                    print(f"   -> Failed to drop FK {fk_name}: {e}")
        except Exception as e:
            print(f"Error querying FK: {e}")

        # 2. 再次尝试转换 kb_blocks 表字符集
        print("Converting 'kb_blocks' to utf8mb4_unicode_ci ...")
        try:
            # CONVERT TO 也会同时修正列的 Collation
            db.session.execute(
                text("ALTER TABLE kb_blocks CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            db.session.commit()
            print("   -> Success: kb_blocks converted.")
        except Exception as e:
            print(f"   -> Failed to convert kb_blocks: {e}")

        # 3. 双重保险：单独确保 file_id 列也是 unicode_ci
        print("Ensuring 'kb_blocks.file_id' collation...")
        try:
            # 注意：VARCHAR(36) 需要和 files.id 一致
            db.session.execute(text(
                "ALTER TABLE kb_blocks MODIFY file_id VARCHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"))
            db.session.commit()
            print("   -> Success: file_id column fixed.")
        except Exception as e:
            print(f"   -> Failed to fix file_id column: {e}")

        print("\nForce Fix Completed.")


if __name__ == "__main__":
    force_fix_collation()