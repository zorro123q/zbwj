from flask import Blueprint, jsonify, request

from domain.kb.ingest import KbIngestError, delete_doc, ingest_kb, list_docs

bp = Blueprint("kb_v1", __name__)


@bp.post("/api/v1/kb/ingest")
def ingest_kb_api():
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    title = data.get("title")

    try:
        result = ingest_kb(file_id=file_id, title=title)
        return jsonify(result), 200
    except KbIngestError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception:
        return jsonify(error="internal_error", message="kb ingest failed"), 500


@bp.get("/api/v1/kb/docs")
def list_kb_docs_api():
    args = request.args
    page = args.get("page") or "1"
    page_size = args.get("page_size") or "20"

    try:
        result = list_docs(page=int(page), page_size=int(page_size))
        return jsonify(result), 200
    except Exception:
        return jsonify(error="internal_error", message="kb docs list failed"), 500


@bp.delete("/api/v1/kb/docs/<doc_id>")
def delete_kb_doc_api(doc_id: str):
    try:
        result = delete_doc(doc_id)
        return jsonify(result), 200
    except KbIngestError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception:
        return jsonify(error="internal_error", message="kb delete failed"), 500
