import re
from typing import Any, Dict, List, Tuple


class Extractor:
    """
    MVP: rule-based extractor (no real LLM).
    Output schema:
      {
        "tables": [{
          "sheet_name": "Result",
          "columns": ["category","item","value","source"],
          "rows": [[...], ...]
        }]
      }
    """

    # 估算分页标准：假设每 45 行文本对应一页 A4 文档
    LINES_PER_PAGE = 45

    BASIC_FIELDS: List[Tuple[str, List[str]]] = [
        ("项目名称", [r"项目名称[:：]\s*(.+)"]),
        ("项目编号", [r"(项目编号|项目编号/编号)[:：]\s*([A-Za-z0-9\-—_]+)"]),
        ("采购人", [r"(采购人|招标人)[:：]\s*(.+)"]),
        ("采购代理机构", [r"(采购代理机构|代理机构)[:：]\s*(.+)"]),
        ("截止时间", [r"(截止时间|响应文件递交截止时间)[:：]\s*([0-9]{4}.+?)($|\s)"]),
        ("开启时间", [r"(开启时间|开标时间)[:：]\s*([0-9]{4}.+?)($|\s)"]),
        ("递交地点", [r"(递交地点|响应文件递交地点)[:：]\s*(.+)"]),
        ("开启地点", [r"(开启地点|开标地点)[:：]\s*(.+)"]),
        ("最高限价/预算", [r"(最高响应限价|最高限价|预算金额|项目预算)[:：]\s*(.+)"]),
        ("服务期/合同期限", [r"(服务期|合同期限|服务期限)[:：]\s*(.+)"]),
        ("联系人", [r"(联系人)[:：]\s*([^\s，,；;]+)"]),
        ("联系电话", [r"(联系电话|电话)[:：]?\s*([0-9\-（）()]{6,})"]),
        ("地址", [r"(地址)[:：]\s*(.+)"]),
    ]

    KEYWORD_CATEGORIES = [
        ("废标项", ["废标", "否决", "无效响应", "不予受理", "不通过", "资格不符", "重大偏离"]),
        ("初步评审", ["初步评审", "符合性审查", "资格审查", "响应性审查"]),
        ("评分标准", ["评分", "分值", "评审因素", "评分细则", "打分", "得分"]),
        ("注意事项", ["注意", "特别提醒", "重要", "须知", "不得", "必须", "应当"]),
    ]

    @staticmethod
    def _estimate_page(line_idx: int) -> int:
        """
        根据行号估算页码 (Line Index starts from 1)
        """
        return ((line_idx - 1) // Extractor.LINES_PER_PAGE) + 1

    @staticmethod
    def _normalize_lines(text: str) -> List[str]:
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for ln in text.split("\n"):
            s = ln.strip()
            if s:
                lines.append(s)
        return lines

    @staticmethod
    def _find_first_match(lines: List[str], patterns: List[str]) -> Tuple[str, str]:
        """
        Returns (value, source) or ("","")
        source = "Page:X (line:Y)"
        """
        for i, ln in enumerate(lines, start=1):
            for pat in patterns:
                m = re.search(pat, ln)
                if m:
                    val = ""
                    if m.lastindex:
                        val = m.group(m.lastindex).strip()
                    else:
                        val = m.group(0).strip()

                    page = Extractor._estimate_page(i)
                    src = f"Page:{page} (line:{i})"
                    return val, src
        return "", ""

    @staticmethod
    def _collect_keyword_hits(lines: List[str], keywords: List[str], limit: int = 100) -> List[Tuple[int, str]]:
        """
        Collects lines containing any keyword.
        Returns list of (line_idx_1_based, line_text)
        """
        hits = []
        for i, ln in enumerate(lines, start=1):
            if any(k in ln for k in keywords):
                hits.append((i, ln))
                if len(hits) >= limit:
                    break
        return hits

    @classmethod
    def extract(cls, text: str) -> Dict[str, Any]:
        lines = cls._normalize_lines(text)

        rows: List[List[Any]] = []

        # -------------------------------------------------------
        # 1) 基本信息 (已修改：改为聚合模式)
        # -------------------------------------------------------
        basic_info_parts = []
        for field_name, patterns in cls.BASIC_FIELDS:
            val, src = cls._find_first_match(lines, patterns)
            if val:
                # 将每个字段拼接成： "【字段名】 值 ... (来源)"
                # 例如: "【项目编号】 ZZB-24211 ... (Page:1 (line:3))"
                basic_info_parts.append(f"【{field_name}】 {val}  -- {src}")

        if basic_info_parts:
            # 聚合为一个大文本块，用换行符分隔
            full_basic_info = "\n".join(basic_info_parts)
            rows.append(["基本信息", "基本信息汇总", full_basic_info, "聚合提取"])
        else:
            # 如果什么都没提取到，展示前10行作为预览
            preview = "\n".join(lines[:10]) if lines else ""
            rows.append(["基本信息", "文本预览(无匹配)", preview, "generated"])

        # -------------------------------------------------------
        # 2) 条款抓取 (保持聚合模式)
        # -------------------------------------------------------
        for cat, kws in cls.KEYWORD_CATEGORIES:
            hits = cls._collect_keyword_hits(lines, kws, limit=50)

            if hits:
                aggregated_parts = []
                for line_idx, ln in hits:
                    page = cls._estimate_page(line_idx)
                    # 格式: "Page:4 3.1 评分标准..."
                    aggregated_parts.append(f"Page:{page} {ln}")

                full_text = "\n".join(aggregated_parts)
                rows.append([cat, f"{cat}汇总", full_text, "聚合生成"])

        # -------------------------------------------------------
        # 3) 总结行
        # -------------------------------------------------------
        rows.append(["统计", "字符数", len(text or ""), "generated"])
        rows.append(["统计", "非空行数", len(lines), "generated"])

        return {
            "tables": [
                {
                    "sheet_name": "Result",
                    "columns": ["category", "item", "value", "source"],
                    "rows": rows,
                }
            ]
        }