from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request, send_file, current_app
from sqlalchemy import and_, func

from app.extensions import db
from app.models import Company, DocumentType, Evidence, Person, StoredFile
from app.services.cert_storage import save_cert_file, save_image

bp = Blueprint("certs_v1", __name__)


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def _resolve_cert_file(file_id: str) -> Tuple[StoredFile, Path]:
    file_id = (file_id or "").strip()
    if not file_id:
        raise ValueError("file_id is required")

    stored = db.session.get(StoredFile, file_id)
    if stored is None:
        raise FileNotFoundError("file not found")

    rel_path = (stored.storage_rel_path or "").replace("\\", "/").lstrip("/")
    abs_path = (_repo_root() / Path(rel_path)).resolve()

    expected_root = (_repo_root() / Path(current_app.config.get("CERTS_STORAGE_DIR", "storage/certs"))).resolve()
    if expected_root not in abs_path.parents and abs_path != expected_root:
        raise PermissionError("invalid cert path")

    if not abs_path.exists() or not abs_path.is_file():
        raise FileNotFoundError("file not found on disk")

    return stored, abs_path


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d")


def _evidence_owner_name(evidence: Evidence, person_name: Optional[str], company_name: Optional[str]) -> Optional[str]:
    return person_name if evidence.scope == "PERSON" else company_name


def _evidence_to_dict(evidence: Evidence, doc_type: DocumentType, stored: StoredFile, owner_name: Optional[str]) -> Dict[str, Any]:
    return {
        "evidence_id": evidence.id,
        "scope": evidence.scope,
        "owner_id": evidence.owner_id,
        "owner_name": owner_name,
        "doc_type_code": doc_type.code,
        "doc_type_name": doc_type.name,
        "cert_no": evidence.cert_no,
        "issuer": evidence.issuer,
        "issued_at": evidence.issued_at.isoformat() if evidence.issued_at else None,
        "expires_at": evidence.expires_at.isoformat() if evidence.expires_at else None,
        "status": evidence.status,
        "tags": evidence.tags,
        "file": {
            "file_id": stored.id,
            "original_name": stored.original_name,
            "mime_type": stored.mime_type,
            "size_bytes": int(stored.size_bytes),
            "storage_rel_path": stored.storage_rel_path,
            "download_url": f"/api/v1/certs/files/{stored.id}/download",
        },
    }


@bp.get("/api/v1/certs/files/<file_id>/download")
def download_cert_image(file_id: str):
    try:
        stored, abs_path = _resolve_cert_file(file_id)
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400
    except FileNotFoundError as exc:
        return jsonify(error="not_found", message=str(exc)), 404
    except PermissionError as exc:
        return jsonify(error="forbidden", message=str(exc)), 403

    download_name = stored.original_name or f"{stored.id}.{stored.ext}".strip(".")
    return send_file(
        str(abs_path),
        mimetype=stored.mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=download_name,
        conditional=True,
        max_age=0,
        etag=True,
        last_modified=abs_path.stat().st_mtime,
    )


@bp.get("/api/v1/certs")
def list_certs():
    args = request.args
    scope = (args.get("scope") or "").strip().upper() or None
    owner_id = (args.get("owner_id") or "").strip() or None
    doc_type_code = (args.get("doc_type_code") or "").strip() or None

    try:
        page = max(int(args.get("page") or 1), 1)
        page_size = max(min(int(args.get("page_size") or 5), 100), 1)
    except ValueError:
        return jsonify(error="bad_request", message="page and page_size must be integers"), 400

    query = (
        db.session.query(
            Evidence,
            DocumentType,
            StoredFile,
            Person.name.label("person_name"),
            Company.name.label("company_name"),
        )
        .join(DocumentType, Evidence.document_type_id == DocumentType.id)
        .join(StoredFile, Evidence.file_id == StoredFile.id)
        .outerjoin(Person, and_(Evidence.scope == "PERSON", Evidence.owner_id == Person.id))
        .outerjoin(Company, and_(Evidence.scope == "COMPANY", Evidence.owner_id == Company.id))
    )

    if scope:
        query = query.filter(Evidence.scope == scope)
    if owner_id:
        query = query.filter(Evidence.owner_id == owner_id)
    if doc_type_code:
        query = query.filter(DocumentType.code == doc_type_code)

    total = query.with_entities(func.count()).order_by(None).scalar() or 0
    rows = (
        query.order_by(Evidence.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for evidence, doc_type, stored, person_name, company_name in rows:
        owner_name = _evidence_owner_name(evidence, person_name, company_name)
        items.append(_evidence_to_dict(evidence, doc_type, stored, owner_name))

    return jsonify(page=page, page_size=page_size, total=int(total), items=items), 200


@bp.post("/api/v1/certs")
def create_cert():
    if "file" not in request.files:
        return jsonify(error="missing_file", message="multipart form-data key 'file' is required"), 400

    file = request.files["file"]
    data = request.form or {}
    scope = data.get("scope")
    owner_id = data.get("owner_id")
    doc_type_code = data.get("doc_type_code")

    try:
        issued_at = _parse_date(data.get("issued_at"))
        expires_at = _parse_date(data.get("expires_at"))
    except ValueError:
        return jsonify(error="bad_request", message="issued_at/expires_at must be YYYY-MM-DD"), 400

    try:
        result = save_image(
            file=file,
            scope=scope,
            owner_id=owner_id,
            doc_type_code=doc_type_code,
            cert_no=(data.get("cert_no") or "").strip() or None,
            issuer=(data.get("issuer") or "").strip() or None,
            issued_at=issued_at,
            expires_at=expires_at,
            tags=(data.get("tags") or "").strip() or None,
        )
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400
    except Exception:
        return jsonify(error="internal_error", message="failed to create cert"), 500

    return jsonify(
        evidence_id=result["evidence_id"],
        file_id=result["file_id"],
        download_url=f"/api/v1/certs/files/{result['file_id']}/download",
        dedup=result["dedup"],
    ), 200


@bp.get("/api/v1/certs/<evidence_id>")
def get_cert(evidence_id: str):
    evidence_id = (evidence_id or "").strip()
    if not evidence_id:
        return jsonify(error="bad_request", message="evidence_id is required"), 400

    row = (
        db.session.query(
            Evidence,
            DocumentType,
            StoredFile,
            Person.name.label("person_name"),
            Company.name.label("company_name"),
        )
        .join(DocumentType, Evidence.document_type_id == DocumentType.id)
        .join(StoredFile, Evidence.file_id == StoredFile.id)
        .outerjoin(Person, and_(Evidence.scope == "PERSON", Evidence.owner_id == Person.id))
        .outerjoin(Company, and_(Evidence.scope == "COMPANY", Evidence.owner_id == Company.id))
        .filter(Evidence.id == evidence_id)
        .first()
    )
    if not row:
        return jsonify(error="not_found", message="cert not found"), 404

    evidence, doc_type, stored, person_name, company_name = row
    owner_name = _evidence_owner_name(evidence, person_name, company_name)
    return jsonify(_evidence_to_dict(evidence, doc_type, stored, owner_name)), 200


@bp.put("/api/v1/certs/<evidence_id>")
def update_cert(evidence_id: str):
    evidence_id = (evidence_id or "").strip()
    if not evidence_id:
        return jsonify(error="bad_request", message="evidence_id is required"), 400

    evidence = db.session.get(Evidence, evidence_id)
    if evidence is None:
        return jsonify(error="not_found", message="cert not found"), 404

    file = request.files.get("file") if request.files else None
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form or {}

    try:
        issued_at = _parse_date(data.get("issued_at")) if "issued_at" in data else None
        expires_at = _parse_date(data.get("expires_at")) if "expires_at" in data else None
    except ValueError:
        return jsonify(error="bad_request", message="issued_at/expires_at must be YYYY-MM-DD"), 400

    if "cert_no" in data:
        evidence.cert_no = (data.get("cert_no") or "").strip() or None
    if "issuer" in data:
        evidence.issuer = (data.get("issuer") or "").strip() or None
    if "tags" in data:
        evidence.tags = (data.get("tags") or "").strip() or None
    if "status" in data:
        evidence.status = (data.get("status") or "").strip().upper() or evidence.status
    if "issued_at" in data:
        evidence.issued_at = issued_at
    if "expires_at" in data:
        evidence.expires_at = expires_at

    owner_id = (data.get("owner_id") or "").strip() if "owner_id" in data else None
    if owner_id is not None:
        if evidence.scope == "PERSON":
            if db.session.get(Person, owner_id) is None:
                return jsonify(error="bad_request", message="owner_id not found"), 400
        else:
            if db.session.get(Company, owner_id) is None:
                return jsonify(error="bad_request", message="owner_id not found"), 400
        evidence.owner_id = owner_id

    current_dt = db.session.get(DocumentType, evidence.document_type_id)
    if current_dt is None:
        return jsonify(error="bad_request", message="document type not found"), 400
    doc_type_code = (data.get("doc_type_code") or "").strip() if "doc_type_code" in data else None
    if doc_type_code is not None:
        dt = (
            db.session.query(DocumentType)
            .filter(DocumentType.scope == evidence.scope, DocumentType.code == doc_type_code)
            .first()
        )
        if not dt:
            return jsonify(error="bad_request", message="document type not found for this scope/code"), 400
        evidence.document_type_id = dt.id
        current_dt = dt

    old_file_id = evidence.file_id
    if file:
        stored, dt = save_cert_file(
            file=file,
            scope=evidence.scope,
            owner_id=evidence.owner_id,
            doc_type_code=(doc_type_code or (current_dt.code if current_dt else "")),
        )
        evidence.file_id = stored.id
        evidence.document_type_id = dt.id

    db.session.commit()

    if file and old_file_id != evidence.file_id:
        remaining = db.session.query(Evidence).filter(Evidence.file_id == old_file_id).count()
        if remaining == 0:
            old_stored = db.session.get(StoredFile, old_file_id)
            if old_stored:
                rel_path = (old_stored.storage_rel_path or "").replace("\\", "/").lstrip("/")
                abs_path = (_repo_root() / Path(rel_path)).resolve()
                try:
                    if abs_path.exists():
                        abs_path.unlink()
                except Exception:
                    pass
                db.session.delete(old_stored)
                db.session.commit()

    return jsonify(ok=True), 200


@bp.delete("/api/v1/certs/<evidence_id>")
def delete_cert(evidence_id: str):
    evidence_id = (evidence_id or "").strip()
    if not evidence_id:
        return jsonify(error="bad_request", message="evidence_id is required"), 400

    evidence = db.session.get(Evidence, evidence_id)
    if evidence is None:
        return jsonify(error="not_found", message="cert not found"), 404

    file_id = evidence.file_id
    db.session.delete(evidence)
    db.session.commit()

    remaining = db.session.query(Evidence).filter(Evidence.file_id == file_id).count()
    if remaining == 0:
        stored = db.session.get(StoredFile, file_id)
        if stored:
            rel_path = (stored.storage_rel_path or "").replace("\\", "/").lstrip("/")
            abs_path = (_repo_root() / Path(rel_path)).resolve()
            try:
                if abs_path.exists():
                    abs_path.unlink()
            except Exception:
                pass
            db.session.delete(stored)
            db.session.commit()

    return jsonify(ok=True), 200
