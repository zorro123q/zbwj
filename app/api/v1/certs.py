from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, current_app

from app.extensions import db
from app.models import StoredFile


bp = Blueprint("certs_v1", __name__)


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def _resolve_storage_path(rel_path: str) -> Path:
    repo_root = _repo_root()
    abs_path = (repo_root / rel_path).resolve()
    if abs_path == repo_root or repo_root not in abs_path.parents:
        raise ValueError("invalid storage path")
    return abs_path


@bp.get("/api/v1/certs/files/<file_id>")
def get_cert_file(file_id: str):
    file_id = (file_id or "").strip()
    if not file_id:
        return jsonify(error="bad_request", message="file_id is required"), 400

    stored = db.session.get(StoredFile, file_id)
    if not stored:
        return jsonify(error="not_found", message="file not found"), 404

    try:
        abs_path = _resolve_storage_path(stored.storage_rel_path)
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400

    if not abs_path.exists() or not abs_path.is_file():
        return jsonify(error="not_found", message="file not found"), 404

    download = (request.args.get("download") or "").strip() in {"1", "true", "yes"}

    return send_file(
        abs_path,
        mimetype=stored.mime_type,
        as_attachment=download,
        download_name=stored.original_name,
    )
