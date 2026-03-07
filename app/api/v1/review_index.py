import logging
from flask import Blueprint, request, jsonify, send_file
# 【修改点1】这里把 ReviewIndexGenerator 改成了 BiddingDocumentGenerator
from domain.review_index.generator import generate_review_index_docx, BiddingDocumentGenerator

bp = Blueprint("review_index", __name__, url_prefix="/api/v1/review-index")

logger = logging.getLogger(__name__)


@bp.get("/preview")
def preview_requirements():
    """
    预览解析出的评审要求 (Requirements)
    前端调用: GET /api/v1/review-index/preview?job_id=...&limit=...
    """
    job_id = request.args.get("job_id")
    limit = int(request.args.get("limit", 200))

    if not job_id:
        return jsonify({"message": "job_id is required"}), 400

    try:
        # 【修改点2】复用新的 Generator 类来加载数据
        generator = BiddingDocumentGenerator(job_id)
        rows = generator.load_requirements()

        # 截取前 N 条供预览
        preview_rows = rows[:limit]
        return jsonify({
            "total": len(rows),
            "items": preview_rows
        })
    except Exception as e:
        logger.exception("Preview failed")
        return jsonify({"message": str(e)}), 500


@bp.post("/generate")
def generate_docx():
    """
    一键生成 Word 报告
    前端调用: POST /api/v1/review-index/generate
    Body: { job_id, kb_tag, evidence_top_n, template_docx_path }
    """
    data = request.get_json() or {}

    # 1. 提取参数
    job_id = data.get("job_id")
    kb_tag = data.get("kb_tag")
    evidence_top_n = int(data.get("evidence_top_n", 3))
    template_docx_path = data.get("template_docx_path")

    # 兼容字段
    xlsx_path = data.get("xlsx_path")

    if not job_id:
        return jsonify({"message": "job_id is required"}), 400

    try:
        # 2. 调用核心生成函数
        output_path = generate_review_index_docx(
            job_id=job_id,
            kb_tag=kb_tag,
            evidence_top_n=evidence_top_n,
            template_docx_path=template_docx_path,
            xlsx_path=xlsx_path
        )

        # 3. 返回文件流
        return send_file(
            output_path,
            as_attachment=True,
            download_name="投标响应文件.docx"  # 【修改点3】让下载下来的文件名更专业
        )

    except Exception as e:
        logger.exception("Generation failed")
        return jsonify({"message": f"Generate failed: {str(e)}"}), 500