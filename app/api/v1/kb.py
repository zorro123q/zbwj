# app/api/v1/kb.py
from flask import Blueprint, jsonify, request, send_file

from domain.kb.ingest import KbIngestError, delete_doc, ingest_kb, list_docs
from domain.kb.retriever import KbSearchError, search_blocks
from domain.kb.export import export_search_to_docx

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


@bp.post("/api/v1/kb/search")
def search_kb_blocks_api():
    data = request.get_json(silent=True) or {}
    query = data.get("query")
    top_k = data.get("top_k")
    by_tag = data.get("by_tag")
    title_keywords = data.get("title_keywords")
    page = data.get("page") or 1
    page_size = data.get("page_size") or 20

    try:
        try:
            page_int = int(page)
            page_size_int = int(page_size)
        except (TypeError, ValueError) as exc:
            raise KbSearchError("page and page_size must be integers") from exc

        result = search_blocks(
            query=query,
            top_k=top_k,
            by_tag=by_tag,
            title_keywords=title_keywords,
            page=page_int,
            page_size=page_size_int,
        )
        return jsonify(result), 200
    except KbSearchError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception:
        return jsonify(error="internal_error", message="kb search failed"), 500


@bp.post("/api/v1/kb/export")
def export_kb_api():
    """
    前端：输入 query（比如“产品功能”）-> 返回一个 docx 下载
    """
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    top_k = data.get("top_k") or 50
    by_tag = data.get("by_tag")
    title_keywords = data.get("title_keywords")

    if not query:
        return jsonify(error="bad_request", message="query is required"), 400

    try:
        out_abs_path = export_search_to_docx(
            query=query,
            top_k=int(top_k),
            by_tag=by_tag,
            title_keywords=title_keywords,
        )
        return send_file(out_abs_path, as_attachment=True, download_name="kb_export.docx")
    except Exception as e:
        return jsonify(error="internal_error", message=str(e)), 500
