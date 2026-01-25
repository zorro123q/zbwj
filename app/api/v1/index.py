from flask import Blueprint, jsonify, request, current_app

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
