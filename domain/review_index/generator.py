import os
import json
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy import func, desc
from flask import current_app

from app.extensions import db
from app.models import KbBlock, Job, File
from domain.templates.renderer import render_docx_template

logger = logging.getLogger(__name__)


class BiddingDocumentGenerator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job = db.session.get(Job, job_id)
        if not self.job:
            raise ValueError(f"Job {job_id} not found")

    def _get_project_root(self) -> str:
        return os.path.dirname(current_app.root_path)

    def load_requirements(self) -> List[Dict[str, Any]]:
        """加载解析出的招标需求"""
        if not self.job.artifact_json_path:
            return []
        json_path = os.path.join(self._get_project_root(), self.job.artifact_json_path)
        if not os.path.exists(json_path):
            return []
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_rows = []
            if isinstance(data, dict) and "tables" in data:
                for t in data["tables"]:
                    if "rows" in t: raw_rows.extend(t["rows"])
            elif isinstance(data, list):
                raw_rows = data

            final_rows = []
            default_headers = ["category", "item", "value", "source"]
            for r in raw_rows:
                if isinstance(r, dict):
                    final_rows.append(r)
                elif isinstance(r, list):
                    new_row = {}
                    for i, val in enumerate(r):
                        if i < len(default_headers): new_row[default_headers[i]] = val
                    final_rows.append(new_row)
            return final_rows
        except Exception as e:
            logger.error(f"Failed to load json: {e}")
            return []

    def search_evidence(self, query: str, tag: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """在知识库中进行语义检索"""
        if not query: return []
        q = db.session.query(KbBlock, File).join(File, KbBlock.file_id == File.id)
        if tag: q = q.filter(KbBlock.tag == tag)
        q = q.filter(KbBlock.content_text.like(f"%{query}%"))
        q = q.order_by(desc(KbBlock.content_len)).limit(top_k)

        results = []
        for block, file_rec in q.all():
            results.append({
                "content": block.content_text,
                "source_file": file_rec.filename
            })
        return results

    def generate_full_document(self, kb_tag: str, top_n: int, template_path: str = None) -> str:
        """
        组装完整的标书数据字典并触发渲染
        """
        context_data = {}

        # 1. 预先检索固定章节内容（从知识库提取科讯嘉联的核心材料）
        standard_sections = {
            "company_profile": "企业简介 综合实力 资质 CMMI5 ISO",
            "tech_solution": "智能客服 核心技术 ASR OCR 系统架构",
            "implementation": "项目实施 培训计划 交付周期",
            "after_sales": "售后服务 应急响应 故障修复"
        }

        for key, query in standard_sections.items():
            evidences = self.search_evidence(query, tag=kb_tag, top_k=2)
            if evidences:
                paragraphs = [e['content'].replace("\n", " ").strip() for e in evidences]
                context_data[key] = "\n\n".join(paragraphs)
            else:
                context_data[key] = f"（知识库中暂无关于【{query}】的详细说明，请人工补充）"

        # 2. 检索招标文件具体的点对点需求
        requirements = self.load_requirements()
        for req in requirements:
            if not isinstance(req, dict): continue
            search_term = req.get("item") or req.get("评审项") or req.get("desc") or ""
            if not search_term:
                req["response_text"] = "【系统提示：未解析到明确的招标参数要求】"
                continue

            evidences = self.search_evidence(search_term, tag=kb_tag, top_k=top_n)
            if evidences:
                # 拼接AI自动写标书的响应话术
                paragraphs = [f"我方完全响应并满足该项要求。关于【{search_term}】，我方实施方案及参数如下："]
                paragraphs.extend([e['content'].replace("\n", " ").strip() for e in evidences])
                req["response_text"] = "\n\n".join(paragraphs)
            else:
                req["response_text"] = "我方完全满足该项要求。（具体技术细节详见整体技术方案）"

        context_data["requirements"] = requirements

        # 将准备好的内容交给渲染器直接写 Word
        return render_docx_template(context_data, template_path)


# ---------------------------------------------------------
# 为了保证与现有 API 路由（api/v1/review_index.py）的兼容性，保留旧别名
# ---------------------------------------------------------
ReviewIndexGenerator = BiddingDocumentGenerator


def generate_review_index_docx(
        job_id: str,
        kb_tag: str,
        evidence_top_n: int = 3,
        template_docx_path: str = None,
        xlsx_path: str = None
) -> str:
    generator = BiddingDocumentGenerator(job_id)
    return generator.generate_full_document(
        kb_tag=kb_tag,
        top_n=evidence_top_n,
        template_path=template_docx_path
    )