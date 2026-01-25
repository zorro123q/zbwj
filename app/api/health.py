from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    return jsonify(ok=True, service="flask-gpt-stack"), 200
