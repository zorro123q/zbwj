from pathlib import Path
from typing import Tuple

from flask import Blueprint, jsonify, send_file, current_app

from app.extensions import db
from app.models import StoredFile

bp = Blueprint("certs_v1", __name__)


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def _resolve_cert_file(file_id: str) -> Tuple[StoredFile, Path]:
    file_id = (file_id or "").strip()
    if not file_id:
        raise ValueError("file_id is required")

    stored = db.session.get(StoredFile, file_id)
    if stored is None:
        raise FileNotFoundError("file not found")

    rel_path = (stored.storage_rel_path or "").replace("\\", "/").lstrip("/")
    abs_path = (_repo_root() / Path(rel_path)).resolve()

    expected_root = (_repo_root() / Path(current_app.config.get("CERTS_STORAGE_DIR", "storage/certs"))).resolve()
    if expected_root not in abs_path.parents and abs_path != expected_root:
        raise PermissionError("invalid cert path")

    if not abs_path.exists() or not abs_path.is_file():
        raise FileNotFoundError("file not found on disk")

    return stored, abs_path


@bp.get("/api/v1/certs/files/<file_id>/preview")
def preview_cert_image(file_id: str):
    try:
        stored, abs_path = _resolve_cert_file(file_id)
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400
    except FileNotFoundError as exc:
        return jsonify(error="not_found", message=str(exc)), 404
    except PermissionError as exc:
        return jsonify(error="forbidden", message=str(exc)), 403

    return send_file(
        str(abs_path),
        mimetype=stored.mime_type or "application/octet-stream",
        as_attachment=False,
        conditional=True,
        max_age=0,
        etag=True,
        last_modified=abs_path.stat().st_mtime,
    )


@bp.get("/api/v1/certs/files/<file_id>/download")
def download_cert_image(file_id: str):
    try:
        stored, abs_path = _resolve_cert_file(file_id)
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400
    except FileNotFoundError as exc:
        return jsonify(error="not_found", message=str(exc)), 404
    except PermissionError as exc:
        return jsonify(error="forbidden", message=str(exc)), 403

    download_name = stored.original_name or f"{stored.id}.{stored.ext}".strip(".")
    return send_file(
        str(abs_path),
        mimetype=stored.mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=download_name,
        conditional=True,
        max_age=0,
        etag=True,
        last_modified=abs_path.stat().st_mtime,
    )
