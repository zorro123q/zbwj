import os

from flask import Flask
from typing import Optional

from .config import get_config
from .extensions import db, migrate, cors


def create_app(env: Optional[str] = None) -> Flask:
    # instance_relative_config=True
    # instance 配置文件路径默认是：<项目根目录>/instance/config.py
    app = Flask(__name__, instance_relative_config=True)

    cfg = get_config(env)
    app.config.from_object(cfg)

    # 加载 instance/config.py（可覆盖 SQLALCHEMY_DATABASE_URI 等）
    app.config.from_pyfile("config.py", silent=True)

    # 【Fix 1】修复配置优先级 Bug
    # 原代码中使用 setdefault，但因为 BaseConfig 中已定义该 Key，导致 setdefault 永远无效。
    # 这里改为：如果环境变量存在，则强制覆盖 config 中的值。
    env_max_len = os.getenv("MAX_CONTENT_LENGTH")
    if env_max_len:
        try:
            app.config["MAX_CONTENT_LENGTH"] = int(env_max_len)
        except ValueError:
            pass  # 如果格式错误，保持 BaseConfig 的默认值

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("mysql"):
        app.config.setdefault(
            "SQLALCHEMY_ENGINE_OPTIONS",
            {"pool_pre_ping": True, "connect_args": {"charset": "utf8mb4"}}
        )

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/*": {"origins": "*"}})

    # Blueprints
    from .api.health import bp as health_bp
    from .api.files import bp as files_bp
    from .api.root import bp as root_bp
    from .api.prompt_scripts import bp as prompt_scripts_bp
    from .api.jobs import bp as jobs_bp
    from .web.ui import bp as ui_bp
    from .api.v1.index import bp as index_bp
    from .api.v1.kb import bp as kb_bp
    from .api.v1.review_index import bp as review_index_bp

    # 【新增】相似性检测模块蓝图
    from .api.v1.similarity import bp as similarity_bp

    app.register_blueprint(review_index_bp)
    app.register_blueprint(root_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(prompt_scripts_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(index_bp)
    app.register_blueprint(kb_bp)

    # 注册新蓝图
    app.register_blueprint(similarity_bp)

    # CLI: seed document types
    from .seed import seed_document_types

    @app.cli.command("seed-document-types")
    def _seed_document_types_cmd():
        seed_document_types()
        print("seed-document-types: done")

    return app