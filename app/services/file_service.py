import os
import uuid
from pathlib import Path
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import File


def _get_ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


class FileService:
    @staticmethod
    def save(file_storage: FileStorage) -> File:
        """
        保存上传文件到: storage/uploads/<file_id>/original.<ext>
        并写入数据库 files 表。
        返回: File 模型对象
        """
        original_name = file_storage.filename or ""
        safe_name = secure_filename(original_name)

        if not safe_name:
            raise ValueError("invalid filename")

        ext = _get_ext(safe_name)
        # 获取允许的扩展名，默认 txt/docx
        allowed = current_app.config.get("UPLOAD_ALLOWED_EXTENSIONS", {"txt", "docx"})
        if ext not in allowed:
            raise ValueError("only txt/docx are allowed")

        file_id = str(uuid.uuid4())

        # 1. 确定存储目录
        # 兼容处理：优先使用配置中的绝对路径 UPLOAD_STORAGE_DIR
        # 如果未配置，则回退到项目根目录下的 storage/uploads
        upload_dir_conf = current_app.config.get("UPLOAD_STORAGE_DIR")
        if upload_dir_conf:
            base_dir = Path(upload_dir_conf)
        else:
            # 这里的 root_path 通常是 app/ 目录，parent 是项目根目录
            base_dir = Path(current_app.root_path).parent / "storage" / "uploads"

        target_dir = base_dir / file_id
        target_dir.mkdir(parents=True, exist_ok=True)

        # 2. 拼接目标文件路径
        filename = f"original.{ext}"
        abs_path = target_dir / filename

        # 3. 保存文件
        file_storage.save(str(abs_path))

        # 4. 检查大小（虽然 Flask 有 MAX_CONTENT_LENGTH，但双重保险）
        size = abs_path.stat().st_size
        max_size = int(current_app.config.get("MAX_CONTENT_LENGTH", 0) or 0)
        if max_size > 0 and size > max_size:
            # 如果超限，删除已保存的文件
            try:
                abs_path.unlink()
            except Exception:
                pass
            raise ValueError(f"file too large (max {max_size} bytes)")

        # 5. 写入数据库
        # 注意：这里 storage_path 存入绝对路径或相对路径取决于配置。
        # Runner 脚本通常能处理绝对路径（Path / abs_path = abs_path）。
        # 为了展示的一致性，如果用了绝对路径配置，这里存绝对路径是安全的。
        rec = File(
            id=file_id,
            filename=safe_name,
            ext=ext,
            size=int(size),
            storage_path=str(abs_path),
        )
        db.session.add(rec)
        db.session.commit()

        return rec