from pathlib import Path

from flask import Blueprint, jsonify, request, current_app, send_file

from app.extensions import db
from app.models import StoredFile

from domain.index.service import IndexSearchParams, search_index

bp = Blueprint("index_v1", __name__)


@bp.get("/api/v1/index/search")
def index_search():
    args = request.args

    params = IndexSearchParams(
        q=(args.get("q") or "").strip(),
        scope=(args.get("scope") or "").strip().upper() or None,
        owner_id=(args.get("owner_id") or "").strip() or None,
        doc_type_code=(args.get("doc_type_code") or "").strip() or None,
        valid_on=(args.get("valid_on") or "").strip() or None,
        page=(args.get("page") or "").strip() or "1",
        page_size=(args.get("page_size") or "").strip() or "20",
        sort=(args.get("sort") or "").strip() or "relevance_desc",
    )

    try:
        result = search_index(params)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception as e:
        # 开发模式下把真实错误带出来，方便定位 FULLTEXT / SQL 等问题
        msg = str(e) if current_app.debug else "index search failed"
        return jsonify(error="internal_error", message=msg), 500


def _resolve_cert_file(file_id: str):
    repo_root = Path(current_app.root_path).parent.resolve()
    stored = db.session.get(StoredFile, file_id)
    if not stored:
        return None, None, None

    rel_path = stored.storage_rel_path
    abs_path = (repo_root / rel_path).resolve()
    try:
        abs_path.relative_to(repo_root)
    except ValueError:
        return None, None, None

    if not abs_path.exists() or not abs_path.is_file():
        return None, None, None

    return stored, abs_path, rel_path


@bp.get("/api/v1/index/files/<file_id>/preview")
def preview_cert_file(file_id: str):
    stored, abs_path, _ = _resolve_cert_file(file_id)
    if not stored:
        return jsonify(error="not_found", message="file not found"), 404

    return send_file(
        abs_path,
        mimetype=stored.mime_type,
        as_attachment=False,
        download_name=stored.original_name,
    )


@bp.get("/api/v1/index/files/<file_id>/download")
def download_cert_file(file_id: str):
    stored, abs_path, _ = _resolve_cert_file(file_id)
    if not stored:
        return jsonify(error="not_found", message="file not found"), 404

    return send_file(
        abs_path,
        mimetype=stored.mime_type,
        as_attachment=True,
        download_name=stored.original_name,
    )
