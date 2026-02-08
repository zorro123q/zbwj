from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app
from sqlalchemy import and_, asc, case, desc, func, literal_column, or_
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Company, DocumentType, Evidence, Person, StoredFile


ALLOWED_SCOPES = {None, "PERSON", "COMPANY"}
ALLOWED_SORTS = {"created_at_desc", "expires_at_asc", "relevance_desc"}


@dataclass
class IndexSearchParams:
    q: str
    scope: Optional[str]
    owner_id: Optional[str]
    doc_type_code: Optional[str]
    valid_on: Optional[str]  # YYYY-MM-DD or None
    page: str
    page_size: str
    sort: str


def _parse_int(raw: str, default: int, min_v: int, max_v: int) -> int:
    try:
        v = int(raw)
    except Exception:
        v = default
    if v < min_v:
        v = min_v
    if v > max_v:
        v = max_v
    return v


def _parse_date_ymd(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except Exception:
        raise ValueError("valid_on must be YYYY-MM-DD")


def _use_fulltext() -> bool:
    try:
        dialect = db.engine.dialect.name
    except Exception:
        dialect = ""
    return bool(current_app.config.get("CERTS_ENABLE_FULLTEXT", True)) and dialect == "mysql"


def _like_contains(col, q_lower: str):
    return func.lower(func.coalesce(col, "")).like(f"%{q_lower}%")


def _build_like_relevance(q_lower: str):
    dt_name_hit = case((_like_contains(DocumentType.name, q_lower), 100), else_=0)
    dt_code_hit = case((_like_contains(DocumentType.code, q_lower), 100), else_=0)

    cert_no_hit = case((_like_contains(Evidence.cert_no, q_lower), 30), else_=0)
    issuer_hit = case((_like_contains(Evidence.issuer, q_lower), 20), else_=0)
    tags_hit = case((_like_contains(Evidence.tags, q_lower), 15), else_=0)

    return (dt_name_hit + dt_code_hit + cert_no_hit + issuer_hit + tags_hit).label("relevance")


def _build_fulltext_relevance(q: str, q_lower: str):
    dt_ft = literal_column("MATCH(document_types.name) AGAINST (:q IN NATURAL LANGUAGE MODE)")
    ev_ft = literal_column("MATCH(evidences.tags,evidences.cert_no,evidences.issuer) AGAINST (:q IN NATURAL LANGUAGE MODE)")

    dt_code_like = case((_like_contains(DocumentType.code, q_lower), 60), else_=0)
    dt_name_like = case((_like_contains(DocumentType.name, q_lower), 60), else_=0)

    return (dt_ft * 10 + ev_ft * 3 + dt_code_like + dt_name_like).label("relevance")


def _apply_sort(query, sort: str, relevance_col):
    if sort == "created_at_desc":
        return query.order_by(desc(Evidence.created_at))
    if sort == "expires_at_asc":
        nulls_last = case((Evidence.expires_at.is_(None), 1), else_=0)
        return query.order_by(asc(nulls_last), asc(Evidence.expires_at), desc(Evidence.created_at))
    return query.order_by(desc(relevance_col), desc(Evidence.created_at))


def _build_query(params: IndexSearchParams, use_ft: bool):
    scope = params.scope
    sort = params.sort or "relevance_desc"

    page = _parse_int(params.page, default=1, min_v=1, max_v=10**9)
    page_size = _parse_int(params.page_size, default=20, min_v=1, max_v=100)

    valid_on_dt = _parse_date_ymd(params.valid_on)

    q = (params.q or "").strip()
    q_lower = q.lower()

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

    # structured filters
    if scope:
        query = query.filter(Evidence.scope == scope)
    if params.owner_id:
        query = query.filter(Evidence.owner_id == params.owner_id)
    if params.doc_type_code:
        query = query.filter(DocumentType.code == params.doc_type_code)
    if valid_on_dt is not None:
        query = query.filter(or_(Evidence.expires_at.is_(None), Evidence.expires_at >= valid_on_dt))

    relevance_col = literal_column("0").label("relevance")

    if q:
        doc_like = or_(
            _like_contains(DocumentType.name, q_lower),
            _like_contains(DocumentType.code, q_lower),
        )
        ev_like = or_(
            _like_contains(Evidence.cert_no, q_lower),
            _like_contains(Evidence.issuer, q_lower),
            _like_contains(Evidence.tags, q_lower),
        )

        if use_ft:
            dt_ft = literal_column("MATCH(document_types.name) AGAINST (:q IN NATURAL LANGUAGE MODE)")
            ev_ft = literal_column("MATCH(evidences.tags,evidences.cert_no,evidences.issuer) AGAINST (:q IN NATURAL LANGUAGE MODE)")
            query = query.filter(or_(dt_ft > 0, ev_ft > 0, doc_like, ev_like))
            relevance_col = _build_fulltext_relevance(q=q, q_lower=q_lower)
            query = query.add_columns(relevance_col).params(q=q)
        else:
            query = query.filter(or_(doc_like, ev_like))
            relevance_col = _build_like_relevance(q_lower=q_lower)
            query = query.add_columns(relevance_col)
    else:
        sort = "created_at_desc"
        query = query.add_columns(relevance_col)

    return query, relevance_col, sort, page, page_size


def search_index(params: IndexSearchParams) -> Dict[str, Any]:
    if params.scope not in ALLOWED_SCOPES:
        raise ValueError("scope must be PERSON, COMPANY or empty")

    if (params.sort or "relevance_desc") not in ALLOWED_SORTS:
        raise ValueError("sort must be created_at_desc|expires_at_asc|relevance_desc")

    use_ft = _use_fulltext()

    def _exec(use_ft_flag: bool) -> Dict[str, Any]:
        query, relevance_col, sort, page, page_size = _build_query(params, use_ft_flag)

        total = query.with_entities(func.count()).order_by(None).scalar() or 0
        query = _apply_sort(query, sort, relevance_col)

        offset = (page - 1) * page_size
        rows = query.limit(page_size).offset(offset).all()

        items: List[Dict[str, Any]] = []
        for row in rows:
            ev, dt, sf, person_name, company_name, _rel = row
            owner_name = person_name if ev.scope == "PERSON" else company_name

            items.append(
                {
                    "evidence_id": ev.id,
                    "scope": ev.scope,
                    "owner_id": ev.owner_id,
                    "owner_name": owner_name,
                    "doc_type_code": dt.code,
                    "doc_type_name": dt.name,
                    "cert_no": ev.cert_no,
                    "issuer": ev.issuer,
                    "issued_at": ev.issued_at.isoformat() if ev.issued_at else None,
                    "expires_at": ev.expires_at.isoformat() if ev.expires_at else None,
                    "status": ev.status,
                    "file": {
                        "file_id": sf.id,
                        "original_name": sf.original_name,
                        "mime_type": sf.mime_type,
                        "size_bytes": int(sf.size_bytes),
                        # "storage_rel_path": sf.storage_rel_path,  <-- 已移除该字段
                    },
                }
            )

        return {"page": page, "page_size": page_size, "total": int(total), "items": items}

    # 先用 FULLTEXT（若开启 & MySQL），失败则自动降级到 LIKE（不会影响你后续再开启 FULLTEXT）
    try:
        return _exec(use_ft)
    except SQLAlchemyError as e:
        if use_ft and (params.q or "").strip():
            # FULLTEXT 失败 -> fallback 到 LIKE
            return _exec(False)
        raise