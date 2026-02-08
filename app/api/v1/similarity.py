from flask import Blueprint, jsonify, request
import uuid
from app.extensions import db
from app.models import Job, File
from app.worker.runner import runner

bp = Blueprint("similarity_v1", __name__)


@bp.post("/api/v1/similarity/check")
def create_similarity_check():
    """
    提交两个文件进行查重
    JSON Body: { "source_file_id": "...", "target_file_id": "..." }
    """
    data = request.get_json(silent=True) or {}
    source_id = data.get("source_file_id")
    target_id = data.get("target_file_id")

    if not source_id or not target_id:
        return jsonify(error="bad_request", message="source_file_id and target_file_id required"), 400

    # 简单校验文件存在
    f1 = db.session.get(File, source_id)
    f2 = db.session.get(File, target_id)
    if not f1 or not f2:
        return jsonify(error="not_found", message="files not found"), 404

    job_id = str(uuid.uuid4())

    # 创建 Job
    # 我们复用 job 表：
    # file_id -> 源文件
    # model_id -> 目标文件 (因为 Job 表没有 target_file_id 字段，暂时借用 model_id 字段存放)
    # script_id -> "DOC_SIMILARITY_CHECK" (标记任务类型)
    job = Job(
        id=job_id,
        file_id=source_id,
        script_id="DOC_SIMILARITY_CHECK",
        model_id=target_id,  # <--- 借用字段
        status="PENDING",
        stage="QUEUED",
        progress=0
    )

    db.session.add(job)
    db.session.commit()

    # 启动任务
    runner.start(job_id)

    return jsonify({"job_id": job_id, "status": "PENDING"}), 201