import os
import uuid
import logging
from typing import List, Dict, Any
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
except ImportError:
    raise ImportError("Please install python-docx: pip install python-docx")

logger = logging.getLogger(__name__)


def render_docx_template(requirements: List[Dict[str, Any]], template_path: str = None) -> str:
    """
    渲染评审办法索引表到 Word 文档
    """
    # 1. 创建或加载文档
    if template_path and os.path.exists(template_path):
        try:
            doc = Document(template_path)
            logger.info(f"Loaded template: {template_path}")
        except Exception as e:
            logger.warning(f"Failed to load template {template_path}, creating new doc. Error: {e}")
            doc = Document()
    else:
        doc = Document()

    # 2. 如果是新文档（或者模板里没内容），添加标题
    # 判断逻辑简单处理：如果没传模板路径，或者文档段落很少，就加个标题
    if not template_path:
        heading = doc.add_heading('评审办法索引表', 0)
        # 尝试设置中文字体支持 (防止报错，加 try)
        try:
            doc.styles['Normal'].font.name = 'Times New Roman'
            doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        except Exception:
            pass

    # 3. 创建表格 (4列: 评审大类, 评审项, 响应内容, 证明材料来源)
    table = doc.add_table(rows=1, cols=4)

    # 【核心修复】设置表格样式时增加容错处理
    try:
        table.style = 'Table Grid'
    except Exception as e:
        logger.warning(f"Style 'Table Grid' not found in template. Using default style. Error: {e}")
        # 如果报错，说明模板里没这个样式，这里什么都不做，使用 Word 默认表格样式

    # 设置表头
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '评审大类 (Category)'
    hdr_cells[1].text = '评审项 (Item)'
    hdr_cells[2].text = '响应内容 (Value)'
    hdr_cells[3].text = '证明材料来源 (Evidence)'

    # 4. 填充数据
    for req in requirements:
        row_cells = table.add_row().cells

        # 安全获取字段，防止 KeyError
        # 这里做了兼容，既支持 dict 也支持 object (如果传入的是 SQL Model)
        def get_val(item, keys):
            if isinstance(item, dict):
                for k in keys:
                    if k in item and item[k]: return str(item[k])
            else:
                for k in keys:
                    if hasattr(item, k) and getattr(item, k): return str(getattr(item, k))
            return ''

        cat = get_val(req, ['category', '评审大类', '大类'])
        item = get_val(req, ['item', '评审项', 'desc', 'description', 'content'])
        val = get_val(req, ['value', '响应内容', 'response'])
        ev = get_val(req, ['evidence', '证明材料'])

        row_cells[0].text = cat
        row_cells[1].text = item
        row_cells[2].text = val
        row_cells[3].text = ev

    # 5. 保存文件
    # 构造输出目录: storage/artifacts/review_index/
    # 使用 Flask current_app 定位路径
    try:
        from flask import current_app
        root = Path(current_app.root_path).parent
    except:
        # Fallback if not in flask context
        root = Path(os.getcwd())

    out_dir = root / "storage" / "artifacts" / "review_index"
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"review_index_{uuid.uuid4().hex[:8]}.docx"
    out_path = out_dir / filename

    doc.save(str(out_path))
    logger.info(f"Generated docx at: {out_path}")

    return str(out_path)