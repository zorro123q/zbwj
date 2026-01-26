# domain/review_index/kb_evidence.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, case, desc, func

from app.models import KbBlock


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _strip_score_suffix(s: str) -> str:
    # 去掉 “（10分）/(10分)” 等
    s = _clean(s)
    s = re.sub(r"（\s*\d+\s*分\s*）", "", s)
    s = re.sub(r"\(\s*\d+\s*分\s*\)", "", s)
    return s.strip()


def _extract_terms(score_row: Dict[str, str]) -> List[str]:
    """
    从模板行抽取检索词（用于 KB 召回）。
    """
    major = _strip_score_suffix(score_row.get("score_major", ""))
    minor = _clean(score_row.get("score_minor", ""))
    rule = _clean(score_row.get("score_rule", ""))
    evid = _clean(score_row.get("evidence_materials", ""))

    terms: List[str] = []
    if major:
        terms.append(major)

    # 从小类/规则里抽一些通用关键字
    # ISO/CMMI/ASR/OCR/TTS/MOS 等
    terms += re.findall(r"(ISO\d{4,5}|CMMI\s*\d*|ASR|OCR|TTS|MOS)", (minor + " " + rule), flags=re.I)

    # 有效证明材料里按行拆
    for line in (evid or "").split("\n"):
        line = line.strip()
        line = re.sub(r"^\s*\d+[、.]\s*", "", line).strip()
        if len(line) >= 2:
            terms.append(line)

    # 去重 + 控制长度
    uniq: List[str] = []
    seen = set()
    for t in terms:
        tt = t.strip()
        if not tt:
            continue
        if len(tt) > 48:
            continue
        k = tt.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(tt)

    return uniq[:12]


def retrieve_evidence_blocks(
    *,
    score_row: Dict[str, str],
    tag: Optional[str],
    top_n: int = 3,
    excerpt_len: int = 800,
) -> List[Dict[str, Any]]:
    """
    从 kb_blocks 中召回证据块，并返回 excerpt（内容摘录），让生成 docx 时可直接写入内容。
    """
    top_n = max(1, min(int(top_n or 3), 10))
    excerpt_len = max(200, min(int(excerpt_len or 800), 5000))

    terms = _extract_terms(score_row)
    if not terms:
        return []

    q = KbBlock.query
    if tag:
        q = q.filter(KbBlock.tag == tag)

    like_filters = []
    score_parts = []

    for t in terms:
        pat = f"%{t.lower()}%"
        like_filters.append(func.lower(KbBlock.section_title).like(pat))
        like_filters.append(func.lower(KbBlock.content_text).like(pat))

        score_parts.append(case((func.lower(KbBlock.section_title).like(pat), 5), else_=0))
        score_parts.append(case((func.lower(KbBlock.content_text).like(pat), 1), else_=0))

    score_expr = sum(score_parts)

    rows = (
        q.filter(or_(*like_filters))
        .with_entities(KbBlock, score_expr.label("score"))
        .order_by(desc("score"), desc(KbBlock.created_at))
        .limit(top_n)
        .all()
    )

    out: List[Dict[str, Any]] = []
    for block, score in rows:
        text = (block.content_text or "").strip()
        excerpt = text[:excerpt_len] if text else ""

        out.append(
            {
                "block_id": block.id,
                "doc_id": block.doc_id,
                "section_title": block.section_title,
                "section_path": block.section_path,
                "score": int(score or 0),
                "start_idx": int(block.start_idx or 0),
                "end_idx": int(block.end_idx or 0),
                "block_docx_path": block.block_docx_path,
                # ✅ 关键：返回内容摘录
                "excerpt": excerpt,
            }
        )

    return out
