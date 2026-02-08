import os
from pathlib import Path
from typing import Optional


def _build_mysql_uri() -> Optional[str]:
    host = os.getenv("MYSQL_HOST")
    db = os.getenv("MYSQL_DB")
    if not host or not db:
        return None

    user = os.getenv("MYSQL_USER", "root")
    pwd = os.getenv("MYSQL_PASSWORD", "")
    port = os.getenv("MYSQL_PORT", "3306")

    # mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
    auth = f"{user}:{pwd}" if pwd else f"{user}:"
    return f"mysql+pymysql://{auth}@{host}:{port}/{db}?charset=utf8mb4"


class BaseConfig:
    # 【Fix 2】定义项目根目录（更稳健的路径获取方式）
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JSON_AS_ASCII = False

    # Upload limits
    # 【修改点】将 20MB 调整为 500MB，以支持大型标书文件
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    UPLOAD_ALLOWED_EXTENSIONS = {"txt", "docx"}

    # 【Fix 2】使用 PROJECT_ROOT 拼接绝对路径
    UPLOAD_STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage/uploads")
    ARTIFACT_STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage/artifacts")
    CERTS_STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage/certs")

    CERTS_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp"}
    CERTS_ENABLE_FULLTEXT = os.getenv("CERTS_ENABLE_FULLTEXT", "1") == "1"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Prefer MySQL when env provided; fallback to DATABASE_URL; else sqlite
    _mysql_uri = _build_mysql_uri()

    # 【Fix 2】SQLite 路径
    SQLALCHEMY_DATABASE_URI = (
            _mysql_uri
            or os.getenv("DATABASE_URL")
            or f"sqlite:///{os.path.join(PROJECT_ROOT, 'instance/app.db')}"
    )


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = "development"


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = "production"


def get_config(env: Optional[str] = None):
    env = (env or os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development").lower()
    if env in ("prod", "production"):
        return ProductionConfig
    if env in ("test", "testing"):
        return TestingConfig
    return DevelopmentConfig