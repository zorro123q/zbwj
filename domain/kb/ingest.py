import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from flask import current_app

from app.extensions import db
from app.models import File, KbBlock, KbDocument


class KbIngestError(ValueError):
    pass


HEADING_NUMBER_RE = re.compile(r"^(\\d+(?:\\.\\d+)*)([\\s、.．]+)(.+)")
CN_HEADING_RE = re.compile(r"^([一二三四五六七八九十]+)[、.．](.+)")


@dataclass
class BlockDraft:
    section_title: str
    section_path: str
    content_lines: List[str]
    start_idx: int
    end_idx: int


def _load_docx(path: Path):
    try:
        from docx import Document
    except Exception as exc:
        raise KbIngestError("python-docx is required to parse docx") from exc
    try:
        return Document(str(path))
    except Exception as exc:
        raise KbIngestError("failed to parse docx file") from exc


def _detect_heading_level(paragraph) -> Optional[int]:
    style = getattr(paragraph, "style", None)
    style_name = getattr(style, "name", "") or ""
    if style_name.startswith("Heading "):
        level_str = style_name.replace("Heading ", "").strip()
        if level_str.isdigit():
            return int(level_str)

    text = (paragraph.text or "").strip()
    if not text:
        return None

    match = HEADING_NUMBER_RE.match(text)
    if match:
        segments = match.group(1).split(".")
        return max(1, min(len(segments), 6))

    match = CN_HEADING_RE.match(text)
    if match:
        return 1

    return None


def _normalize_heading_text(text: str) -> str:
    text = (text or "").strip()
    match = HEADING_NUMBER_RE.match(text)
    if match:
        return match.group(3).strip()
    match = CN_HEADING_RE.match(text)
    if match:
        return match.group(2).strip()
    return text


def _iter_blocks(doc) -> List[BlockDraft]:
    blocks: List[BlockDraft] = []
    stack: List[str] = []
    current_block: Optional[BlockDraft] = None

    for idx, paragraph in enumerate(doc.paragraphs, start=1):
        text = (paragraph.text or "").strip()
        if not text:
            continue

        level = _detect_heading_level(paragraph)
        if level is not None:
            if current_block is not None:
                blocks.append(current_block)
            stack = stack[: max(level - 1, 0)]
            heading_text = _normalize_heading_text(text)
            stack.append(heading_text or f"Section {idx}")
            section_path = " / ".join(stack)
            current_block = BlockDraft(
                section_title=heading_text or stack[-1],
                section_path=section_path,
                content_lines=[],
                start_idx=idx,
                end_idx=idx,
            )
            continue

        if current_block is None:
            current_block = BlockDraft(
                section_title="正文",
                section_path="正文",
                content_lines=[],
                start_idx=idx,
                end_idx=idx,
            )

        current_block.content_lines.append(text)
        current_block.end_idx = idx

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def _write_block_docx(block_id: str, title: str, content_lines: Iterable[str]) -> str:
    try:
        from docx import Document
    except Exception as exc:
        raise KbIngestError("python-docx is required to write docx") from exc

    doc = Document()
    doc.add_heading(title, level=1)
    for line in content_lines:
        doc.add_paragraph(line)

    rel_path = f"storage/kb/blocks/{block_id}.docx"
    repo_root = Path(current_app.root_path).parent
    abs_path = repo_root / Path(rel_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(abs_path))
    return rel_path


def ingest_kb(file_id: str, title: Optional[str]) -> Dict[str, int]:
    file_id = (file_id or "").strip()
    if not file_id:
        raise KbIngestError("file_id is required")

    stored = db.session.get(File, file_id)
    if stored is None:
        raise KbIngestError("file_id not found")

    ext = (stored.ext or "").lower().strip()
    if ext != "docx":
        raise KbIngestError("only docx is supported for now")

    repo_root = Path(current_app.root_path).parent
    abs_path = repo_root / Path(stored.storage_path)
    if not abs_path.exists():
        raise KbIngestError("source file not found on disk")

    doc = _load_docx(abs_path)
    blocks = _iter_blocks(doc)
    if not blocks:
        raise KbIngestError("no content blocks found in docx")

    doc_id = str(uuid.uuid4())
    doc_title = (title or "").strip() or stored.filename
    doc_rec = KbDocument(id=doc_id, file_id=file_id, title=doc_title)
    db.session.add(doc_rec)

    for block in blocks:
        block_id = str(uuid.uuid4())
        block_docx_path = _write_block_docx(block_id, block.section_title, block.content_lines)
        content_text = "\n".join(block.content_lines)
        block_rec = KbBlock(
            id=block_id,
            doc_id=doc_id,
            tag=None,
            section_title=block.section_title,
            section_path=block.section_path,
            content_text=content_text,
            start_idx=int(block.start_idx),
            end_idx=int(block.end_idx),
            block_docx_path=block_docx_path,
        )
        db.session.add(block_rec)

    db.session.commit()
    return {"doc_id": doc_id, "block_count": len(blocks)}


def list_docs(page: int, page_size: int) -> Dict[str, object]:
    page = max(int(page), 1)
    page_size = max(min(int(page_size), 100), 1)

    query = KbDocument.query.order_by(KbDocument.created_at.desc())
    total = query.count()
    docs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for doc in docs:
        block_count = KbBlock.query.filter_by(doc_id=doc.id).count()
        items.append(
            {
                "doc_id": doc.id,
                "file_id": doc.file_id,
                "title": doc.title,
                "block_count": block_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
        )

    return {"page": page, "page_size": page_size, "total": total, "items": items}


def delete_doc(doc_id: str) -> Dict[str, int]:
    doc_id = (doc_id or "").strip()
    if not doc_id:
        raise KbIngestError("doc_id is required")

    doc = db.session.get(KbDocument, doc_id)
    if doc is None:
        raise KbIngestError("doc not found")

    blocks = KbBlock.query.filter_by(doc_id=doc_id).all()
    repo_root = Path(current_app.root_path).parent

    for block in blocks:
        rel_path = (block.block_docx_path or "").replace("\\", "/").lstrip("/")
        abs_path = (repo_root / Path(rel_path)).resolve()
        if abs_path.exists() and abs_path.is_file():
            abs_path.unlink()
        db.session.delete(block)

    db.session.delete(doc)
    db.session.commit()

    return {"deleted_blocks": len(blocks)}
