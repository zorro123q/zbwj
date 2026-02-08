from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, case, desc, func

from app.extensions import db
from app.models import KbBlock, File  # 引入 File 模型用于关联


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

    # ==========================================
    # 核心查询构建：KbBlock JOIN File
    # ==========================================
    # 我们需要 File 表的 filename 来代替原来的 section_title
    query_base = db.session.query(KbBlock, File).join(File, KbBlock.file_id == File.id)

    filters = []

    # 1. Tag 过滤
    if tag:
        filters.append(KbBlock.tag == tag)

    # 2. 评分逻辑
    score_parts = []

    # 标题匹配 (现在匹配 File.filename)
    if title_terms:
        title_hits = []
        for term in title_terms:
            title_hits.append(
                case(
                    (func.lower(File.filename).like(f"%{term.lower()}%"), 10),
                    else_=0,
                )
            )
        score_parts.append(sum(title_hits))

    # 内容匹配
    if q:
        filters.append(func.lower(KbBlock.content_text).like(f"%{q.lower()}%"))
        score_parts.append(
            case(
                (func.lower(KbBlock.content_text).like(f"%{q.lower()}%"), 1),
                else_=0,
            )
        )

    score_expr = sum(score_parts) if score_parts else case((True, 0), else_=0)

    # 3. 应用过滤
    if filters:
        query_base = query_base.filter(and_(*filters))

    # 4. 统计总数
    total = query_base.count()
    if top_k:
        total = min(total, top_k)

    offset = (page - 1) * page_size
    if top_k and offset >= top_k:
        return {"page": page, "page_size": page_size, "total": total, "items": []}

    limit = page_size
    if top_k:
        limit = min(page_size, top_k - offset)

    # 5. 执行查询
    rows = (
        query_base.with_entities(KbBlock, File, score_expr.label("score"))
        .order_by(desc("score"), desc(KbBlock.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: List[Dict[str, Any]] = []
    for block, file_rec, score in rows:
        items.append(
            {
                "block_id": block.id,
                "file_id": block.file_id,
                "filename": file_rec.filename,  # 替代 section_title
                "score": int(score or 0),
                "content_text": block.content_text,
                "meta": block.meta_json,  # 包含 chunk_index 等信息
            }
        )

    return {"page": page, "page_size": page_size, "total": total, "items": items}