import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, UniqueConstraint, Index, BigInteger, Enum, ForeignKey, \
    DateTime
from sqlalchemy.sql import func
from app.extensions import db


# =========================================================
# 1. 基础设施表 (用于文件上传、异步任务)
# =========================================================

class File(db.Model):
    """
    通用文件记录表
    """
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    ext = Column(String(50), nullable=True)
    size = Column(Integer, default=0)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=True)

    # 【核心修复】类型改为 DateTime，默认值为当前时间对象
    created_at = Column(DateTime, default=datetime.now)


class Job(db.Model):
    """
    异步任务表
    """
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), index=True)
    script_id = Column(String(100))
    model_id = Column(String(100))

    status = Column(String(50), default="PENDING")
    stage = Column(String(50))
    progress = Column(Integer, default=0)

    artifact_json_path = Column(String(512))
    artifact_xlsx_path = Column(String(512))
    artifact_docx_path = Column(String(512))

    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# =========================================================
# 2. 知识库 RAG 表
# =========================================================

class KbBlock(db.Model):
    """
    知识库切片表
    """
    __tablename__ = "kb_blocks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联 File 表的 ID
    file_id = Column(String(36), index=True, nullable=False)

    content_text = Column(Text)
    content_len = Column(Integer, default=0)
    tag = Column(String(50), index=True)
    meta_json = Column(Text)

    created_at = Column(DateTime, default=datetime.now)


class KbDocument(db.Model):
    """
    (保留兼容)
    """
    __tablename__ = "kb_documents"
    id = Column(String(36), primary_key=True)
    file_id = Column(String(36), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# =========================================================
# 3. 证书索引业务表 (保留原有业务模型)
# =========================================================

class Person(db.Model):
    __tablename__ = "persons"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, index=True)
    id_number = Column(String(256), nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Company(db.Model):
    __tablename__ = "companies"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(256), nullable=False, index=True)
    unified_social_credit_code = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class StoredFile(db.Model):
    __tablename__ = "stored_files"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_name = Column(String(255), nullable=False)
    ext = Column(String(10), nullable=False)
    mime_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    storage_rel_path = Column(String(512), nullable=False)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("sha256", name="uniq_sha256"),
        Index("idx_stored_files_created_at", "created_at"),
    )


class DocumentType(db.Model):
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(Enum("PERSON", "COMPANY", name="doc_scope_enum"), nullable=False)
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("scope", "code", name="uniq_scope_code"),
        Index("idx_doc_types_scope", "scope"),
        Index("idx_document_types_code", "code"),
        Index("idx_document_types_name", "name"),
    )


class Evidence(db.Model):
    __tablename__ = "evidences"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope = Column(Enum("PERSON", "COMPANY", name="evidence_scope_enum"), nullable=False)
    owner_id = Column(String(36), nullable=False)
    document_type_id = Column(Integer, ForeignKey("document_types.id"), nullable=False)
    file_id = Column(String(36), ForeignKey("stored_files.id"), nullable=False)
    cert_no = Column(String(128), nullable=True)
    issuer = Column(String(256), nullable=True)

    issued_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    status = Column(
        Enum("VALID", "EXPIRED", "UNKNOWN", name="evidence_status_enum"),
        nullable=False,
        server_default="UNKNOWN",
    )
    tags = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    document_type = db.relationship("DocumentType", lazy="joined")
    stored_file = db.relationship("StoredFile", lazy="joined")

    __table_args__ = (
        Index("idx_scope_owner", "scope", "owner_id"),
        Index("idx_scope_doc", "scope", "document_type_id"),
        Index("idx_cert_no", "cert_no"),
        Index("idx_expires_at", "expires_at"),
        Index("idx_issuer", "issuer"),
    )