import os
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file, current_app, abort

from app.extensions import db
from app.models import StoredFile
from app.services.file_service import FileService

bp = Blueprint("files", __name__)


@bp.post("/api/v1/files/upload")
def upload_file():
    """
    上传文件 (原逻辑保持不变)
    """
    file = request.files.get("file")
    if not file:
        return jsonify(error="no_file"), 400

    try:
        # 假设 FileService 处理了存储并返回了 models.File 对象的 ID
        # 注意：这里原代码使用的是 app.models.File (临时上传表)
        # 如果是证书索引，通常对应的是 app.models.StoredFile (持久化表)
        # 但此处只负责上传接口，保持原样即可。
        file_record = FileService.save(file)
        return jsonify({
            "file_id": file_record.id,
            "filename": file_record.filename,
            "size": file_record.size,
            "ext": file_record.ext
        }), 200
    except Exception as e:
        return jsonify(error="upload_failed", message=str(e)), 500


@bp.get("/api/v1/files/<file_id>/download")
def download_file_api(file_id):
    """
    【新增】文件下载/预览接口
    用于前端点击下载证书图片或查看文件
    """
    file_id = (file_id or "").strip()
    if not file_id:
        return jsonify(error="file_id_required"), 400

    # 查询 StoredFile (证书库/知识库文件通常存放在这里)
    stored = db.session.get(StoredFile, file_id)
    if not stored:
        return jsonify(error="not_found", message="File not found"), 404

    # 计算绝对路径
    # 兼容处理：优先使用 config 中的 PROJECT_ROOT，否则回退到 current_app.root_path 的父级
    project_root = current_app.config.get("PROJECT_ROOT")
    if not project_root:
        project_root = Path(current_app.root_path).parent
    else:
        project_root = Path(project_root)

    abs_path = project_root / stored.storage_rel_path

    if not abs_path.exists():
        return jsonify(error="file_missing", message="File content missing on disk"), 404

    # 发送文件 (as_attachment=True 会强制浏览器下载，False 则尝试在浏览器预览)
    # 这里根据 mime_type 判断，如果是图片可以由浏览器决定，但为了满足"下载"需求，建议如下：
    # 如果想直接下载，设为 True；如果想在浏览器打开图片，设为 False。
    # 根据需求“前端可以下载图片”，我们使用附件模式，或者由前端控制。
    # 这里默认作为附件下载。
    try:
        return send_file(
            abs_path,
            as_attachment=True,
            download_name=stored.original_name,
            mimetype=stored.mime_type
        )
    except Exception as e:
        current_app.logger.error(f"Download failed: {e}")
        return jsonify(error="internal_error"), 500