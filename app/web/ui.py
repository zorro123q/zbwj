from flask import Blueprint, render_template

bp = Blueprint("ui", __name__)


@bp.get("/ui")
def ui():
    return render_template("ui.html")
