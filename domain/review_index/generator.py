# domain/review_index/generator.py
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from flask import current_app

from domain.review_index.requirements import load_requirements_xlsx
from domain.review_index.score_template import load_score_template_docx, ScoreTemplateRow
from domain.review_index.kb_evidence import retrieve_evidence_blocks


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def _resolve(p: str) -> Path:
    pp = Path(p)
    if pp.is_absolute():
        return pp
    return (_repo_root() / pp).resolve()


def _pick_template_req(tpl: ScoreTemplateRow) -> str:
    """
    模板要求兜底：
    evidence_materials 为空时，用 score_rule / score_minor 代替，避免显示 '-'
    """
    x = (tpl.evidence_materials or "").strip()
    if x:
        return x
    x = (tpl.score_rule or "").strip()
    if x:
        return x
    x = (tpl.score_minor or "").strip()
    if x:
        return x
    return "-"


def generate_review_index_docx(
    *,
    xlsx_path: str,
    template_docx_path: str,
    kb_tag: Optional[str] = None,
    evidence_top_n: int = 3,
    excerpt_len: int = 800,
) -> Path:
    """
    输出《评审办法索引目录.docx》
      - “一、招标文件要求摘要”：来自 result.xlsx（基本信息/废标项）
      - “二、评审办法索引目录表”：来自评分模板（10个评分大类） + KB召回（写入内容摘录）
      - “附录”：按评分大类输出更长摘录，便于审阅
    """
    try:
        from docx import Document
    except Exception as exc:
        raise RuntimeError("python-docx is required to write docx") from exc

    # 读数据
    reqs = load_requirements_xlsx(xlsx_path=xlsx_path)
    tpl_rows = load_score_template_docx(template_docx_path)

    # 抽项目名称
    project_name = ""
    for r in reqs:
        if (r.category == "基本信息") and (r.item == "项目名称"):
            project_name = r.value
            break

    out_rel = f"storage/kb/exports/review_index_{uuid.uuid4().hex}.docx"
    out_abs = _resolve(out_rel)
    out_abs.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.add_heading("评审办法索引目录", level=1)
    if project_name:
        doc.add_paragraph(f"项目名称：{project_name}")
    doc.add_paragraph(f"招标要求来源：{str(_resolve(xlsx_path))}")
    doc.add_paragraph(f"评分模板来源：{str(_resolve(template_docx_path))}")
    doc.add_paragraph(f"KB tag：{kb_tag or 'ALL'}")

    # =========================
    # 一、招标文件要求摘要
    # =========================
    doc.add_heading("一、招标文件要求摘要（来自 result.xlsx）", level=2)

    base = [r for r in reqs if r.category == "基本信息"]
    doc.add_heading("1. 基本信息", level=3)
    if base:
        t = doc.add_table(rows=1, cols=3)
        t.rows[0].cells[0].text = "item"
        t.rows[0].cells[1].text = "value"
        t.rows[0].cells[2].text = "source"
        for r in base:
            row = t.add_row().cells
            row[0].text = r.item
            row[1].text = r.value
            row[2].text = r.source
    else:
        doc.add_paragraph("（未发现“基本信息”类条目）")

    bad = [r for r in reqs if r.category == "废标项"]
    doc.add_heading("2. 废标项", level=3)
    if bad:
        for r in bad:
            doc.add_paragraph(f"- {r.item}：{r.value}（{r.source}）")
    else:
        doc.add_paragraph("（未发现“废标项”类条目）")

    # =========================
    # 二、评审办法索引目录表
    # =========================
    doc.add_heading("二、评审办法索引目录（评分模板 + KB证据摘录）", level=2)

    table = doc.add_table(rows=1, cols=5)
    hdr = table.rows[0].cells
    hdr[0].text = "评分大类"
    hdr[1].text = "评分小类"
    hdr[2].text = "评分类别"
    hdr[3].text = "有效证明材料（模板要求 + KB内容摘录）"
    hdr[4].text = "证明材料页码/定位（模板页码 + KB段落范围）"

    # 用于附录
    all_evidence: List[Tuple[str, List[dict]]] = []

    for tpl in tpl_rows:
        row_dict = {
            "score_major": tpl.score_major,
            "score_minor": tpl.score_minor,
            "score_rule": tpl.score_rule,
            "evidence_materials": tpl.evidence_materials,
            "pages": tpl.pages,
        }

        hits = retrieve_evidence_blocks(
            score_row=row_dict,
            tag=kb_tag,
            top_n=evidence_top_n,
            excerpt_len=excerpt_len,
        )
        all_evidence.append((tpl.score_major or "（无标题评分大类）", hits))

        # —— 证据列（展示内容而非只展示路径）
        tpl_req = _pick_template_req(tpl)

        evidence_lines: List[str] = []
        evidence_lines.append("【模板要求】")
        evidence_lines.append(tpl_req)
        evidence_lines.append("")
        evidence_lines.append("【知识库命中（内容摘录）】")

        if hits:
            for i, h in enumerate(hits, start=1):
                evidence_lines.append(
                    f"{i}) {h.get('section_title', '')}（score={h.get('score', 0)}）"
                )
                excerpt = (h.get("excerpt") or "").strip()
                if excerpt:
                    evidence_lines.append("   摘录：" + excerpt)
                else:
                    evidence_lines.append("   摘录：（空：该 block 的 content_text 为空或未写入）")
        else:
            evidence_lines.append("（未命中：请确认 KB 已离线切片入库，或调整 tag/关键词）")

        # —— 页码/定位列
        page_lines: List[str] = []
        page_lines.append(f"模板页码：{tpl.pages or '-'}")
        if hits:
            page_lines.append("KB定位：")
            for i, h in enumerate(hits, start=1):
                page_lines.append(
                    f"{i}) 段落 {h.get('start_idx', 0)}-{h.get('end_idx', 0)}"
                )

        else:
            page_lines.append("KB定位：-")

        rr = table.add_row().cells
        rr[0].text = tpl.score_major or ""
        rr[1].text = tpl.score_minor or ""
        rr[2].text = tpl.score_rule or ""
        rr[3].text = "\n".join(evidence_lines)
        rr[4].text = "\n".join(page_lines)

    # =========================
    # 附录：按评分大类输出更完整摘录
    # =========================
    doc.add_page_break()
    doc.add_heading("附录：知识库证据摘录（按评分大类）", level=2)

    for major, hits in all_evidence:
        doc.add_heading(major, level=3)
        if not hits:
            doc.add_paragraph("（无命中）")
            continue

        for i, h in enumerate(hits, start=1):
            doc.add_paragraph(f"{i}) {h.get('section_title', '')}")
            ex = (h.get("excerpt") or "").strip()
            doc.add_paragraph(ex if ex else "（空摘录）")

    doc.save(str(out_abs))
    return out_abs
