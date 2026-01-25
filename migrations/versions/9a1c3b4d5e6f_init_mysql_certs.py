"""init mysql tables for mvp + cert evidence

Revision ID: 9a1c3b4d5e6f
Revises: None
Create Date: 2026-01-11

"""
from alembic import op
import sqlalchemy as sa


revision = "9a1c3b4d5e6f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- MVP tables (files, jobs) ---
    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("ext", sa.String(length=10), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("script_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("artifact_json_path", sa.String(length=512), nullable=True),
        sa.Column("artifact_xlsx_path", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_jobs_file_id", "jobs", ["file_id"], unique=False)

    # --- T5 tables ---
    op.create_table(
        "persons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("id_number", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_persons_name", "persons", ["name"], unique=False)

    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("unified_social_credit_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    op.create_table(
        "document_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.Enum("PERSON", "COMPANY", name="doc_scope_enum"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("scope", "code", name="uniq_scope_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_doc_types_scope", "document_types", ["scope"], unique=False)

    op.create_table(
        "stored_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("ext", sa.String(length=10), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_rel_path", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("sha256", name="uniq_sha256"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_stored_files_created_at", "stored_files", ["created_at"], unique=False)

    op.create_table(
        "evidences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.Enum("PERSON", "COMPANY", name="evidence_scope_enum"), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),

        sa.Column("document_type_id", sa.Integer(), sa.ForeignKey("document_types.id"), nullable=False),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("stored_files.id"), nullable=False),

        sa.Column("cert_no", sa.String(length=128), nullable=True),
        sa.Column("issuer", sa.String(length=256), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Enum("VALID", "EXPIRED", "UNKNOWN", name="evidence_status_enum"),
                  server_default="UNKNOWN", nullable=False),
        sa.Column("tags", sa.String(length=512), nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # required indexes
    op.create_index("idx_scope_owner", "evidences", ["scope", "owner_id"], unique=False)
    op.create_index("idx_scope_doc", "evidences", ["scope", "document_type_id"], unique=False)
    op.create_index("idx_cert_no", "evidences", ["cert_no"], unique=False)
    op.create_index("idx_expires_at", "evidences", ["expires_at"], unique=False)

    # FULLTEXT indexes (MySQL InnoDB)
    # NOTE: If your MySQL version doesn't support, you can comment these lines out.
    op.create_index(
        "ft_evidences_search",
        "evidences",
        ["tags", "cert_no", "issuer"],
        unique=False,
        mysql_prefix="FULLTEXT",
    )
    op.create_index(
        "ft_document_types_name",
        "document_types",
        ["name"],
        unique=False,
        mysql_prefix="FULLTEXT",
    )


def downgrade():
    op.drop_index("ft_document_types_name", table_name="document_types")
    op.drop_index("ft_evidences_search", table_name="evidences")

    op.drop_index("idx_expires_at", table_name="evidences")
    op.drop_index("idx_cert_no", table_name="evidences")
    op.drop_index("idx_scope_doc", table_name="evidences")
    op.drop_index("idx_scope_owner", table_name="evidences")

    op.drop_table("evidences")
    op.drop_index("idx_stored_files_created_at", table_name="stored_files")
    op.drop_table("stored_files")
    op.drop_index("idx_doc_types_scope", table_name="document_types")
    op.drop_table("document_types")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
    op.drop_index("ix_persons_name", table_name="persons")
    op.drop_table("persons")

    op.drop_index("ix_jobs_file_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("files")
