from flask import Blueprint, jsonify, request

from app.services.file_service import save_uploaded_file

bp = Blueprint("files", __name__)


@bp.get("/api/v1/files/upload")
def upload_help():
    # 浏览器直接打开会发 GET，所以给一个友好的提示（同时也方便你自检）
    return jsonify(
        ok=False,
        message="Use POST multipart/form-data with key=file",
        example="curl -F \"file=@demo.txt\" http://127.0.0.1:5000/api/v1/files/upload",
    ), 200


@bp.post("/api/v1/files/upload")
def upload_file():
    if "file" not in request.files:
        return jsonify(error="missing_file", message="multipart form-data key 'file' is required"), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify(error="invalid_file", message="empty filename"), 400

    try:
        result = save_uploaded_file(f)
    except ValueError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception:
        return jsonify(error="internal_error", message="upload failed"), 500

    return jsonify(
        file_id=result["file_id"],
        filename=result["filename"],
        ext=result["ext"],
        size=result["size"],
    ), 200
