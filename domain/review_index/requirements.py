# domain/review_index/requirements.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from flask import current_app


@dataclass
class RequirementRow:
    category: str
    item: str
    value: str
    source: str


def _repo_root() -> Path:
    return Path(current_app.root_path).parent


def load_requirements_xlsx(xlsx_path: str, sheet_name: str = "Result") -> List[RequirementRow]:
    try:
        import openpyxl
    except Exception as exc:
        raise RuntimeError("openpyxl is required") from exc

    abs_path = Path(xlsx_path)
    if not abs_path.is_absolute():
        abs_path = (_repo_root() / abs_path).resolve()
    if not abs_path.exists():
        raise FileNotFoundError(f"xlsx not found: {abs_path}")

    wb = openpyxl.load_workbook(str(abs_path), data_only=True)
    if sheet_name not in wb.sheetnames:
        # 容错：只有一个 sheet 就用第一个
        sheet_name = wb.sheetnames[0]

    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(x or "").strip().lower() for x in rows[0]]
    col = {name: header.index(name) for name in ["category", "item", "value", "source"] if name in header}
    if len(col) < 3:
        raise ValueError(f"requirements header mismatch: {header}")

    out: List[RequirementRow] = []
    for r in rows[1:]:
        if not any(r):
            continue
        out.append(
            RequirementRow(
                category=str(r[col.get("category", 0)] or "").strip(),
                item=str(r[col.get("item", 1)] or "").strip(),
                value=str(r[col.get("value", 2)] or "").strip(),
                source=str(r[col.get("source", 3)] or "").strip(),
            )
        )
    return out


def requirements_to_kv(reqs: List[RequirementRow]) -> Dict[str, Dict[str, Any]]:
    """
    便于写文档：按 category 分组
    """
    grouped: Dict[str, List[RequirementRow]] = {}
    for r in reqs:
        grouped.setdefault(r.category or "其他", []).append(r)

    return {
        cat: [{"item": x.item, "value": x.value, "source": x.source} for x in items]
        for cat, items in grouped.items()
    }
