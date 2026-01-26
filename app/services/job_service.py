import uuid
from typing import Dict, Optional

from app.extensions import db
from app.models import File, Job
from app.services.prompt_registry import PromptRegistry


ALLOWED_STATUS = {"PENDING", "RUNNING", "SUCCEEDED", "FAILED"}


def _clamp_progress(p: int) -> int:
    if p < 0:
        return 0
    if p > 100:
        return 100
    return int(p)


def create_job(file_id: str, script_id: str, model_id: str) -> str:
    file_id = (file_id or "").strip()
    script_id = (script_id or "").strip()
    model_id = (model_id or "").strip()

    if not file_id:
        raise ValueError("file_id is required")
    if not script_id:
        raise ValueError("script_id is required")
    if not model_id:
        raise ValueError("model_id is required")

    # Ensure file exists (MVP)
    f = db.session.get(File, file_id)
    if f is None:
        raise ValueError("file_id not found")

    if script_id != "EXPORT_TEMPLATE_DOCX":
        # Ensure script exists in registry (by script_id only; version ignored in MVP)
        scripts = PromptRegistry.load_all()
        if not any(s.get("script_id") == script_id for s in scripts):
            raise ValueError("script_id not found")

    job_id = str(uuid.uuid4())

    job = Job(
        id=job_id,
        file_id=file_id,
        script_id=script_id,
        model_id=model_id,
        status="PENDING",
        stage="PENDING",
        progress=0,
        artifact_json_path=None,
        artifact_xlsx_path=None,
        artifact_docx_path=None,
        error_message=None,
    )
    db.session.add(job)
    db.session.commit()

    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    job_id = (job_id or "").strip()
    if not job_id:
        return None

    job = db.session.get(Job, job_id)
    if job is None:
        return None

    status = (job.status or "").upper()
    if status not in ALLOWED_STATUS:
        status = "FAILED"

    progress = _clamp_progress(int(job.progress or 0))

    return {
        "job_id": job.id,
        "status": status,
        "stage": job.stage or "",
        "progress": progress,
        "error": job.error_message,
    }
