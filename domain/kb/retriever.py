from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, case, desc, func

from app.models import KbBlock


class KbSearchError(ValueError):
    pass


def _normalize_keywords(keywords: Optional[Iterable[str]]) -> List[str]:
    if not keywords:
        return []
    return [kw.strip() for kw in keywords if isinstance(kw, str) and kw.strip()]


def search_blocks(
    *,
    query: Optional[str],
    top_k: Optional[int],
    by_tag: Optional[str],
    title_keywords: Optional[Iterable[str]],
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    q = (query or "").strip()
    tag = (by_tag or "").strip()
    if title_keywords is not None and not isinstance(title_keywords, (list, tuple)):
        raise KbSearchError("title_keywords must be an array of strings")
    title_terms = _normalize_keywords(title_keywords)

    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    try:
        top_k = max(int(top_k or 0), 0)
    except (TypeError, ValueError) as exc:
        raise KbSearchError("top_k must be an integer") from exc

    filters = []
    if tag:
        filters.append(KbBlock.tag == tag)

    score_parts = []
    if title_terms:
        title_hits = []
        for term in title_terms:
            title_hits.append(
                case(
                    (func.lower(KbBlock.section_title).like(f"%{term.lower()}%"), 10),
                    else_=0,
                )
            )
        score_parts.append(sum(title_hits))

    if q:
        filters.append(func.lower(KbBlock.content_text).like(f"%{q.lower()}%"))
        score_parts.append(
            case(
                (func.lower(KbBlock.content_text).like(f"%{q.lower()}%"), 1),
                else_=0,
            )
        )

    score_expr = sum(score_parts) if score_parts else case((True, 0), else_=0)

    query_obj = KbBlock.query
    if filters:
        query_obj = query_obj.filter(and_(*filters))

    total = query_obj.count()
    if top_k:
        total = min(total, top_k)

    offset = (page - 1) * page_size
    if top_k and offset >= top_k:
        return {"page": page, "page_size": page_size, "total": total, "items": []}

    limit = page_size
    if top_k:
        limit = min(page_size, top_k - offset)

    rows = (
        query_obj.with_entities(KbBlock, score_expr.label("score"))
        .order_by(desc("score"), desc(KbBlock.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: List[Dict[str, Any]] = []
    for block, score in rows:
        items.append(
            {
                "block_id": block.id,
                "doc_id": block.doc_id,
                "section_title": block.section_title,
                "score": int(score or 0),
                "content_text": block.content_text,
                "content_docx_path": block.block_docx_path,
            }
        )

    return {"page": page, "page_size": page_size, "total": total, "items": items}
