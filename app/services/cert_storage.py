import hashlib
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from flask import current_app
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Company, DocumentType, Evidence, Person, StoredFile


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def _basename_only(filename: str) -> str:
    s = (filename or "").replace("\x00", "").strip()
    s = s.replace("\\", "/")
    s = os.path.basename(s).strip()
    if not s:
        raise ValueError("invalid original filename")
    if len(s) > 255:
        if "." in s:
            base, ext = s.rsplit(".", 1)
            ext = ext[:10]
            s = base[: (255 - 1 - len(ext))] + "." + ext
        else:
            s = s[:255]
    return s


def _get_ext_and_original_name(file: FileStorage) -> Tuple[str, str]:
    original_name = _basename_only(file.filename or "")

    ext = ""
    if "." in original_name:
        ext = original_name.rsplit(".", 1)[-1].lower().strip()

    if not ext:
        mt = file.mimetype or ""
        ext_guess = mimetypes.guess_extension(mt)
        if ext_guess:
            ext = ext_guess.lstrip(".").lower()

    if not ext:
        raise ValueError("cannot determine file extension")

    return ext, original_name


def _check_image_ext(ext: str) -> None:
    allowed = set(current_app.config.get("CERTS_ALLOWED_EXTENSIONS", set()))
    if ext.lower() not in allowed:
        raise ValueError(f"unsupported image ext: {ext}")


def _get_doc_type(scope: str, doc_type_code: str) -> DocumentType:
    dt = (
        db.session.query(DocumentType)
        .filter(DocumentType.scope == scope, DocumentType.code == doc_type_code)
        .first()
    )
    if not dt:
        raise ValueError("document type not found for this scope/code")
    return dt


def _check_owner(scope: str, owner_id: str) -> None:
    if scope == "PERSON":
        ok = db.session.get(Person, owner_id) is not None
    else:
        ok = db.session.get(Company, owner_id) is not None
    if not ok:
        raise ValueError("owner_id not found")


def _has_cjk(s: str) -> bool:
    # 判断是否包含中文（CJK）
    for ch in s or "":
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _looks_degraded_name(name: str, ext: str) -> bool:
    if not name:
        return True
    n = name.strip().lower()
    e = (ext or "").strip().lower()
    if n == e or n == f".{e}":
        return True
    if "." not in n and len(n) <= max(3, len(e) + 1):
        return True
    return False


def _should_upgrade_name(old_name: str, new_name: str, ext: str) -> bool:
    """
    决策是否用新文件名覆盖旧文件名（用于修复旧数据）
    规则：
      - 旧名退化（jpg/png/很短） -> 升级
      - 新名包含中文而旧名不包含 -> 升级
      - 新名明显更长且更信息密度 -> 升级
    """
    old = (old_name or "").strip()
    new = (new_name or "").strip()
    if not new:
        return False
    if _looks_degraded_name(old, ext):
        return True
    if _has_cjk(new) and not _has_cjk(old):
        return True
    if len(new) >= len(old) + 8:  # 新名字信息更多
        return True
    return False


def _is_dup_scope_owner_doc_file(err: Exception) -> bool:
    msg = str(err)
    return ("Duplicate entry" in msg) and ("uniq_scope_owner_doc_file" in msg)


def save_image(
    file: FileStorage,
    scope: str,
    owner_id: str,
    doc_type_code: str,
    *,
    cert_no: Optional[str] = None,
    issuer: Optional[str] = None,
    issued_at=None,
    expires_at=None,
    tags: Optional[str] = None,
) -> Dict:
    scope = (scope or "").upper().strip()
    if scope not in ("PERSON", "COMPANY"):
        raise ValueError("scope must be PERSON or COMPANY")

    owner_id = (owner_id or "").strip()
    doc_type_code = (doc_type_code or "").strip()
    if not owner_id or not doc_type_code:
        raise ValueError("owner_id and doc_type_code are required")

    _check_owner(scope, owner_id)
    dt = _get_doc_type(scope, doc_type_code)

    ext, original_name = _get_ext_and_original_name(file)
    _check_image_ext(ext)

    mime_type = file.mimetype or mimetypes.types_map.get(f".{ext}", "application/octet-stream")
    file_id_for_disk = str(uuid.uuid4())

    base = current_app.config.get("CERTS_STORAGE_DIR", "storage/certs")
    if scope == "PERSON":
        rel_dir = f"{base}/person/{owner_id}/{doc_type_code}"
    else:
        rel_dir = f"{base}/company/{owner_id}/{doc_type_code}"

    rel_path = f"{rel_dir}/{file_id_for_disk}.{ext}".replace("\\", "/")
    abs_path = (_repo_root() / Path(rel_path)).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256()
    size = 0

    file.stream.seek(0)
    with abs_path.open("wb") as out:
        while True:
            chunk = file.stream.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            hasher.update(chunk)
            size += len(chunk)

    sha = hasher.hexdigest()

    # sha256 去重
    existing = db.session.query(StoredFile).filter(StoredFile.sha256 == sha).first()
    if existing:
        try:
            if abs_path.exists():
                abs_path.unlink()
        except Exception:
            pass

        # ✅ 关键：如果这次导入拿到了更好的中文原名，就覆盖旧名
        if _should_upgrade_name(existing.original_name, original_name, existing.ext):
            existing.original_name = original_name
            db.session.commit()

        stored = existing
    else:
        stored = StoredFile(
            id=file_id_for_disk,
            original_name=original_name,
            ext=ext,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha,
            storage_rel_path=rel_path,
        )
        db.session.add(stored)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            stored = db.session.query(StoredFile).filter(StoredFile.sha256 == sha).first()
            if not stored:
                raise

            # 并发下也做一次名字升级
            if _should_upgrade_name(stored.original_name, original_name, stored.ext):
                stored.original_name = original_name
                db.session.commit()

    # evidences 插入（幂等）
    evidence_id = str(uuid.uuid4())
    ev = Evidence(
        id=evidence_id,
        scope=scope,
        owner_id=owner_id,
        document_type_id=dt.id,
        file_id=stored.id,
        cert_no=cert_no,
        issuer=issuer,
        issued_at=issued_at,
        expires_at=expires_at,
        status="UNKNOWN",
        tags=tags,
    )
    db.session.add(ev)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if _is_dup_scope_owner_doc_file(e):
            existed = (
                db.session.query(Evidence)
                .filter(
                    Evidence.scope == scope,
                    Evidence.owner_id == owner_id,
                    Evidence.document_type_id == dt.id,
                    Evidence.file_id == stored.id,
                )
                .first()
            )
            if existed:
                return {
                    "file_id": stored.id,
                    "evidence_id": existed.id,
                    "storage_rel_path": stored.storage_rel_path,
                    "mime_type": stored.mime_type,
                    "size_bytes": int(stored.size_bytes),
                    "sha256": stored.sha256,
                    "document_type_id": dt.id,
                    "document_type_code": dt.code,
                    "original_name": stored.original_name,
                    "dedup": True,
                }
        raise

    return {
        "file_id": stored.id,
        "evidence_id": evidence_id,
        "storage_rel_path": stored.storage_rel_path,
        "mime_type": stored.mime_type,
        "size_bytes": int(stored.size_bytes),
        "sha256": stored.sha256,
        "document_type_id": dt.id,
        "document_type_code": dt.code,
        "original_name": stored.original_name,
        "dedup": False,
    }
