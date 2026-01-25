from flask import Blueprint, jsonify, request, send_file

from app.services.job_service import create_job, get_job
from app.worker.runner import runner
from app.extensions import db
from app.models import Job
from pathlib import Path

bp = Blueprint("jobs", __name__)


@bp.post("/api/v1/jobs")
def create_job_api():
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    script_id = data.get("script_id")
    model_id = data.get("model_id")

    try:
        job_id = create_job(file_id=file_id, script_id=script_id, model_id=model_id)
        runner.start(job_id)
        return jsonify(job_id=job_id), 200
    except ValueError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception:
        return jsonify(error="internal_error", message="failed to create job"), 500


@bp.get("/api/v1/jobs/<job_id>")
def get_job_api(job_id: str):
    try:
        job = get_job(job_id)
        if job is None:
            return jsonify(error="not_found", message="job not found"), 404
        return jsonify(job), 200
    except Exception:
        return jsonify(error="internal_error", message="failed to get job"), 500


@bp.get("/api/v1/jobs/<job_id>/artifact")
def download_artifact(job_id: str):
    """
    GET /api/v1/jobs/<job_id>/artifact?type=xlsx|json
    """
    artifact_type = (request.args.get("type") or "").strip().lower()
    if artifact_type not in ("xlsx", "json"):
        return jsonify(error="bad_request", message="type must be xlsx or json"), 400

    job_id = (job_id or "").strip()
    job = db.session.get(Job, job_id)
    if job is None:
        return jsonify(error="not_found", message="job not found"), 404

    status = (job.status or "").upper()
    if status != "SUCCEEDED":
        # job not finished or failed
        return jsonify(error="conflict", message="job is not SUCCEEDED yet"), 409

    rel_path = job.artifact_xlsx_path if artifact_type == "xlsx" else job.artifact_json_path
    if not rel_path:
        return jsonify(error="not_found", message="artifact path not set"), 404

    # Resolve path under repo root safely
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    repo_root = Path(__file__).resolve().parents[2]  # .../<repo>
    abs_path = (repo_root / Path(rel_path)).resolve()

    # Ensure file exists
    if not abs_path.exists() or not abs_path.is_file():
        return jsonify(error="not_found", message="artifact file not found"), 404

    # Ensure the requested file is exactly the job's artifact file (not arbitrary)
    # (already enforced by using job.artifact_*_path; additionally ensure it's under storage/artifacts/<job_id>/)
    expected_dir = (repo_root / Path("storage/artifacts") / job_id).resolve()
    if expected_dir not in abs_path.parents:
        return jsonify(error="forbidden", message="invalid artifact path"), 403

    if artifact_type == "xlsx":
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        download_name = "result.xlsx"
    else:
        mimetype = "application/json"
        download_name = "result.json"

    return send_file(
        str(abs_path),
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name,
        conditional=True,
        max_age=0,
        etag=True,
        last_modified=abs_path.stat().st_mtime,
    )
