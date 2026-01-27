from pathlib import Path

from flask import Blueprint, jsonify, send_file, current_app

from app.extensions import db
from app.models import StoredFile


bp = Blueprint("certs_v1", __name__)


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


@bp.get("/api/v1/certs/files/<file_id>/download")
def download_cert_file(file_id: str):
    file_id = (file_id or "").strip()
    if not file_id:
        return jsonify(error="bad_request", message="file_id is required"), 400

    stored = db.session.get(StoredFile, file_id)
    if stored is None:
        return jsonify(error="not_found", message="file not found"), 404

    rel_path = (stored.storage_rel_path or "").replace("\\", "/").lstrip("/")
    if not rel_path:
        return jsonify(error="not_found", message="file path missing"), 404

    abs_path = (_repo_root() / Path(rel_path)).resolve()
    if not abs_path.exists() or not abs_path.is_file():
        return jsonify(error="not_found", message="file not found on disk"), 404

    return send_file(
        abs_path,
        as_attachment=True,
        download_name=stored.original_name or f"{stored.id}.{stored.ext}",
        mimetype=stored.mime_type or None,
    )
