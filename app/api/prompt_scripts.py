from flask import Blueprint, jsonify

from app.services.prompt_registry import PromptRegistry

bp = Blueprint("prompt_scripts", __name__)


@bp.get("/api/v1/prompt-scripts")
def list_prompt_scripts():
    try:
        scripts = PromptRegistry.load_all()
        return jsonify(scripts), 200
    except ValueError as e:
        return jsonify(error="invalid_prompt_script", message=str(e)), 500
    except Exception:
        return jsonify(error="internal_error", message="failed to load prompt scripts"), 500
