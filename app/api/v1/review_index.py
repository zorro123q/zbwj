import logging
from flask import Blueprint, request, jsonify, send_file
from domain.review_index.generator import generate_review_index_docx, ReviewIndexGenerator

# 注意：url_prefix 这里设为 review-index (带横杠)，与前端 ui.html 保持一致
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
        # 复用 Generator 类来加载数据
        generator = ReviewIndexGenerator(job_id)
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
    # 注意前端传过来可能是 string，安全转 int
    evidence_top_n = int(data.get("evidence_top_n", 3))
    template_docx_path = data.get("template_docx_path")

    # 兼容字段 (防止旧代码报错)
    xlsx_path = data.get("xlsx_path")

    if not job_id:
        return jsonify({"message": "job_id is required"}), 400

    try:
        # 2. 调用核心生成函数
        # 【关键修复】确保 job_id 作为第一个参数传入
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
            download_name="review_index_generated.docx"
        )

    except Exception as e:
        logger.exception("Generation failed")
        # 返回 500 让前端能捕获报错信息
        return jsonify({"message": f"Generate failed: {str(e)}"}), 500