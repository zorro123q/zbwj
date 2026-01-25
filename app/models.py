from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.sql import func

from .extensions import db


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.String(36), primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    ext = db.Column(db.String(10), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True)
    file_id = db.Column(db.String(36), nullable=False, index=True)

    script_id = db.Column(db.String(128), nullable=False)
    model_id = db.Column(db.String(128), nullable=False)

    status = db.Column(db.String(16), nullable=False)
    stage = db.Column(db.String(64), nullable=False)
    progress = db.Column(db.Integer, nullable=False)

    artifact_json_path = db.Column(db.String(512), nullable=True)
    artifact_xlsx_path = db.Column(db.String(512), nullable=True)

    error_message = db.Column(db.String(2000), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Person(db.Model):
    __tablename__ = "persons"

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    id_number = db.Column(db.String(256), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    unified_social_credit_code = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now())





class StoredFile(db.Model):
    __tablename__ = "stored_files"

    id = db.Column(db.String(36), primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    ext = db.Column(db.String(10), nullable=False)
    mime_type = db.Column(db.String(128), nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    storage_rel_path = db.Column(db.String(512), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("sha256", name="uniq_sha256"),
        Index("idx_stored_files_created_at", "created_at"),
    )


# ... 省略其它 import/模型

class DocumentType(db.Model):
    __tablename__ = "document_types"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scope = db.Column(db.Enum("PERSON", "COMPANY", name="doc_scope_enum"), nullable=False)
    code = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(32), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("scope", "code", name="uniq_scope_code"),
        Index("idx_doc_types_scope", "scope"),
        Index("idx_document_types_code", "code"),
        Index("idx_document_types_name", "name"),
        # FULLTEXT index created in migration (dialect-specific)
    )


class Evidence(db.Model):
    __tablename__ = "evidences"

    id = db.Column(db.String(36), primary_key=True)

    scope = db.Column(db.Enum("PERSON", "COMPANY", name="evidence_scope_enum"), nullable=False)
    owner_id = db.Column(db.String(36), nullable=False)

    document_type_id = db.Column(db.Integer, db.ForeignKey("document_types.id"), nullable=False)
    file_id = db.Column(db.String(36), db.ForeignKey("stored_files.id"), nullable=False)

    cert_no = db.Column(db.String(128), nullable=True)
    issuer = db.Column(db.String(256), nullable=True)
    issued_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(
        db.Enum("VALID", "EXPIRED", "UNKNOWN", name="evidence_status_enum"),
        nullable=False,
        server_default="UNKNOWN",
    )

    tags = db.Column(db.String(512), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_type = db.relationship("DocumentType", lazy="joined")
    stored_file = db.relationship("StoredFile", lazy="joined")

    __table_args__ = (
        Index("idx_scope_owner", "scope", "owner_id"),
        Index("idx_scope_doc", "scope", "document_type_id"),
        Index("idx_cert_no", "cert_no"),
        Index("idx_expires_at", "expires_at"),
        Index("idx_issuer", "issuer"),
        # FULLTEXT indexes created in migration (dialect-specific)
    )


class KbDocument(db.Model):
    __tablename__ = "kb_documents"

    id = db.Column(db.String(36), primary_key=True)
    file_id = db.Column(db.String(36), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())


class KbBlock(db.Model):
    __tablename__ = "kb_blocks"

    id = db.Column(db.String(36), primary_key=True)
    doc_id = db.Column(db.String(36), db.ForeignKey("kb_documents.id"), nullable=False, index=True)

    section_title = db.Column(db.String(255), nullable=False)
    section_path = db.Column(db.String(512), nullable=False)
    content_text = db.Column(db.Text, nullable=False)
    start_idx = db.Column(db.Integer, nullable=False)
    end_idx = db.Column(db.Integer, nullable=False)
    block_docx_path = db.Column(db.String(512), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

