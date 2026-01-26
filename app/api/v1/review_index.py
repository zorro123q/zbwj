# app/api/v1/review_index.py
from flask import Blueprint, jsonify, request, send_file

from app.extensions import db
from app.models import Job

# 这两个函数来自我们之前给你的 domain/review_index
from domain.review_index.requirements import load_requirements_xlsx
from domain.review_index.generator import generate_review_index_docx

bp = Blueprint("review_index_v1", __name__)


@bp.get("/api/v1/review-index/preview")
def review_index_preview():
    job_id = (request.args.get("job_id") or "").strip()
    limit = int(request.args.get("limit") or 200)

    if not job_id:
        return jsonify(error="bad_request", message="job_id is required"), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify(error="not_found", message="job not found"), 404

    xlsx_path = getattr(job, "artifact_xlsx_path", None)
    if not xlsx_path:
        return jsonify(error="bad_request", message="job has no artifact_xlsx_path (result.xlsx)"), 400

    try:
        reqs = load_requirements_xlsx(xlsx_path=xlsx_path)
        items = []
        for r in reqs[: max(1, min(limit, 5000))]:
            items.append(
                {
                    "category": r.category,
                    "item": r.item,
                    "value": r.value,
                    "source": r.source,
                }
            )

        return jsonify(
            meta={
                "job_id": job_id,
                "xlsx_path": xlsx_path,
                "total": len(reqs),
            },
            requirements=items,
        ), 200
    except Exception as e:
        return jsonify(error="internal_error", message=str(e)), 500


@bp.post("/api/v1/review-index/generate")
def review_index_generate():
    data = request.get_json(silent=True) or {}
    job_id = (data.get("job_id") or "").strip()
    kb_tag = (data.get("kb_tag") or "").strip() or None
    evidence_top_n = int(data.get("evidence_top_n") or 3)
    template_docx_path = (data.get("template_docx_path") or "storage/kb/templates/评分大类.docx").strip()

    if not job_id:
        return jsonify(error="bad_request", message="job_id is required"), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify(error="not_found", message="job not found"), 404

    xlsx_path = getattr(job, "artifact_xlsx_path", None)
    if not xlsx_path:
        return jsonify(error="bad_request", message="job has no artifact_xlsx_path (result.xlsx)"), 400

    try:
        out_abs = generate_review_index_docx(
            xlsx_path=xlsx_path,
            template_docx_path=template_docx_path,
            kb_tag=kb_tag,
            evidence_top_n=evidence_top_n,
        )
        return send_file(out_abs, as_attachment=True, download_name="评审办法索引目录.docx")
    except Exception as e:
        return jsonify(error="internal_error", message=str(e)), 500
