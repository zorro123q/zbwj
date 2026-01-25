from flask import Blueprint, jsonify

bp = Blueprint("root", __name__)


@bp.get("/")
def index():
    return jsonify(
        ok=True,
        service="flask-gpt-stack",
        endpoints=[
            "GET /api/health",
            "POST /api/v1/files/upload (multipart form-data key=file)",
        ],
    ), 200
