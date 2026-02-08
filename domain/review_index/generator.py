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


class ReviewIndexGenerator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job = db.session.get(Job, job_id)
        if not self.job:
            raise ValueError(f"Job {job_id} not found")

    def _get_project_root(self) -> str:
        """获取项目根目录"""
        return os.path.dirname(current_app.root_path)

    def load_requirements(self) -> List[Dict[str, Any]]:
        """
        加载任务生成的 JSON 结果，并确保返回的是 List[Dict]
        兼容处理：如果 row 是 list，尝试根据位置转换为 dict
        """
        if not self.job.artifact_json_path:
            logger.warning(f"Job {self.job_id} has no artifact_json_path")
            return []

        project_root = self._get_project_root()
        json_path = os.path.join(project_root, self.job.artifact_json_path)

        if not os.path.exists(json_path):
            logger.warning(f"Result JSON file not found: {json_path}")
            return []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            final_rows = []
            raw_rows = []

            # 1. 提取原始 rows 数据
            if isinstance(data, dict) and "tables" in data:
                for t in data["tables"]:
                    if "rows" in t:
                        raw_rows.extend(t["rows"])
            elif isinstance(data, list):
                raw_rows = data

            # 2. 规范化：确保每一行都是 Dict
            # 默认字段映射，如果遇到 list 类型的 row，按此顺序映射
            default_headers = ["category", "item", "value", "source"]

            for r in raw_rows:
                if isinstance(r, dict):
                    final_rows.append(r)
                elif isinstance(r, list):
                    # 如果是 list，转为 dict
                    # 例如 ["技术", "人员", "要求本科"] -> {"category": "技术", "item": "人员", "value": "要求本科"}
                    new_row = {}
                    for i, val in enumerate(r):
                        if i < len(default_headers):
                            key = default_headers[i]
                            new_row[key] = val
                        else:
                            new_row[f"col_{i}"] = val
                    final_rows.append(new_row)
                else:
                    # 既不是 dict 也不是 list，跳过
                    continue

            return final_rows

        except Exception as e:
            logger.error(f"Failed to load result json: {e}")
            return []

    def search_evidence(self, query: str, tag: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        搜索证据
        """
        if not query:
            return []

        # 1. 构造查询
        q = db.session.query(KbBlock, File).join(File, KbBlock.file_id == File.id)

        # 2. 过滤 Tag
        if tag:
            q = q.filter(KbBlock.tag == tag)

        # 3. 模糊匹配
        q = q.filter(KbBlock.content_text.like(f"%{query}%"))

        # 4. 排序与限制
        q = q.order_by(desc(KbBlock.content_len)).limit(top_k)

        rows = q.all()
        results = []
        for block, file_rec in rows:
            results.append({
                "block_id": block.id,
                "content": block.content_text,
                "source_file": file_rec.filename,
                "page_num": self._extract_page_num(block.meta_json)
            })
        return results

    def _extract_page_num(self, meta_json: Optional[str]) -> str:
        if not meta_json:
            return ""
        try:
            m = json.loads(meta_json)
            if "page" in m: return str(m["page"])
            if "chunk_index" in m: return f"Chunk-{m['chunk_index']}"
            return ""
        except:
            return ""

    def generate(self, kb_tag: str, top_n: int, template_path: str = None) -> str:
        """
        生成逻辑
        """
        requirements = self.load_requirements()

        if not requirements:
            logger.warning("No requirements found (empty list).")

        for req in requirements:
            # 双重保险：再次检查 req 是否为 dict
            if not isinstance(req, dict):
                continue

            # 尝试多种 key 获取搜索词
            search_term = (
                    req.get("item") or
                    req.get("评审项") or
                    req.get("desc") or
                    req.get("description") or
                    req.get("content") or
                    ""
            )

            if not search_term:
                req["evidence"] = ""
                continue

            evidences = self.search_evidence(search_term, tag=kb_tag, top_k=top_n)

            lines = []
            for e in evidences:
                src = e['source_file']
                pg = f"(P{e['page_num']})" if e['page_num'] else ""
                txt = e['content'].replace("\n", " ").strip()[:100] + "..."
                lines.append(f"• [{src}{pg}] {txt}")

            req["evidence"] = "\n".join(lines)

        return render_docx_template(requirements, template_path)


# ==========================================
# API 调用入口
# ==========================================
def generate_review_index_docx(
        job_id: str,
        kb_tag: str,
        evidence_top_n: int = 3,
        template_docx_path: str = None,
        xlsx_path: str = None
) -> str:
    generator = ReviewIndexGenerator(job_id)
    return generator.generate(
        kb_tag=kb_tag,
        top_n=evidence_top_n,
        template_path=template_docx_path
    )