import os
import uuid
import time
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

        # 【关键修复 1】先从原始文件名提取后缀，解决中文文件名被 secure_filename 清空导致无法识别后缀的问题
        ext = _get_ext(original_name)

        # 获取允许的扩展名，默认 txt/docx
        allowed = current_app.config.get("UPLOAD_ALLOWED_EXTENSIONS", {"txt", "docx"})
        if ext not in allowed:
            # 增加更详细的错误提示
            raise ValueError(f"不支持的文件格式: .{ext} (仅支持: {', '.join(allowed)})")

        # 【关键修复 2】处理中文文件名的 safe_name
        safe_name = secure_filename(original_name)
        # 如果文件名全是中文（例如 "标书.docx" -> "docx" 或 ""），safe_name 可能会损坏
        # 如果清洗后为空，或者清洗后和后缀一样（说明前缀没了），则生成一个默认名字
        if not safe_name or safe_name == ext:
            # 使用时间戳作为文件名前缀，保留后缀
            safe_name = f"upload_{int(time.time())}.{ext}"

        file_id = str(uuid.uuid4())

        # 1. 确定存储目录
        upload_dir_conf = current_app.config.get("UPLOAD_STORAGE_DIR")
        if upload_dir_conf:
            base_dir = Path(upload_dir_conf)
        else:
            base_dir = Path(current_app.root_path).parent / "storage" / "uploads"

        target_dir = base_dir / file_id
        target_dir.mkdir(parents=True, exist_ok=True)

        # 2. 拼接目标文件路径
        filename = f"original.{ext}"
        abs_path = target_dir / filename

        # 3. 保存文件
        file_storage.save(str(abs_path))

        # 4. 检查大小
        size = abs_path.stat().st_size
        max_size = int(current_app.config.get("MAX_CONTENT_LENGTH", 0) or 0)
        if max_size > 0 and size > max_size:
            try:
                abs_path.unlink()
            except Exception:
                pass
            raise ValueError(f"文件大小 ({size / 1024 / 1024:.2f}MB) 超过限制 ({max_size / 1024 / 1024:.0f}MB)")

        # 5. 写入数据库
        rec = File(
            id=file_id,
            filename=safe_name,  # 此时 safe_name 已经修复，不会是空的
            ext=ext,
            size=int(size),
            storage_path=str(abs_path),
        )
        db.session.add(rec)
        db.session.commit()

        return rec