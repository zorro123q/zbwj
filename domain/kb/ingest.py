import os
import uuid
from datetime import datetime  # 【核心修改】引入 datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from sqlalchemy import func

from app.extensions import db
from app.models import KbBlock, File
from app.worker.components.parser import Parser
from domain.kb.splitter import SemanticTextSplitter


# 定义异常类
class KbIngestError(Exception):
    pass


class IngestLogic:
    @staticmethod
    def ingest_file(file_id: str, tag: str = "general") -> int:
        """
        解析文件 -> 语义切片 -> 存入 kb_block
        返回生成的 block 数量
        """
        f = db.session.get(File, file_id)
        if not f:
            raise ValueError(f"File {file_id} not found")

        # 1. 获取文件绝对路径
        if os.path.isabs(f.storage_path):
            file_path = Path(f.storage_path)
        else:
            # 兼容处理：假设项目根目录在上两级
            from flask import current_app
            root = Path(current_app.root_path).parent
            file_path = root / f.storage_path

        if not file_path.exists():
            raise FileNotFoundError(f"Disk file missing: {file_path}")

        # 2. 解析文本
        text = Parser.parse(file_path, f.ext)
        if not text:
            return 0

        # 3. 执行语义切片
        print(f"Start semantic chunking for file: {f.filename}...")
        try:
            chunks = SemanticTextSplitter.split_text(text)
        except Exception as e:
            print(f"Semantic split failed, fallback to simple split: {e}")
            chunks = [t for t in text.split("\n\n") if t.strip()]

        print(f"Generated {len(chunks)} chunks.")

        # 4. 存入数据库
        # 先清理该文件的旧索引
        db.session.query(KbBlock).filter(KbBlock.file_id == file_id).delete()

        blocks_to_add = []
        for idx, chunk_content in enumerate(chunks):
            if not chunk_content.strip():
                continue

            block_id = str(uuid.uuid4())

            b = KbBlock(
                id=block_id,
                file_id=file_id,
                content_text=chunk_content,
                content_len=len(chunk_content),
                tag=tag,
                meta_json=f'{{"chunk_index": {idx}, "source": "{f.filename}"}}',

                # 【核心修复】使用 datetime 对象
                created_at=datetime.now()
            )
            blocks_to_add.append(b)

        db.session.add_all(blocks_to_add)
        db.session.commit()

        return len(blocks_to_add)


# 导出兼容函数 (供 API 调用)

def ingest_kb(file_id: str, tag: str = "general") -> int:
    try:
        return IngestLogic.ingest_file(file_id, tag)
    except Exception as e:
        raise KbIngestError(str(e)) from e


def delete_doc(file_id: str) -> None:
    try:
        db.session.query(KbBlock).filter(KbBlock.file_id == file_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise KbIngestError(f"Failed to delete doc {file_id}: {str(e)}")


def list_docs(page: int = 1, page_size: int = 20, tag: Optional[str] = None) -> Tuple[List[Dict], int]:
    """
    列出知识库中的文档
    """
    q = db.session.query(
        KbBlock.file_id,
        func.count(KbBlock.id).label("chunk_count"),
        func.max(KbBlock.created_at).label("last_ingest_time")
    )

    if tag:
        q = q.filter(KbBlock.tag == tag)

    q = q.group_by(KbBlock.file_id)

    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    if rows:
        file_ids = [r.file_id for r in rows]
        files = db.session.query(File).filter(File.id.in_(file_ids)).all()
        file_map = {f.id: f for f in files}

        for r in rows:
            f = file_map.get(r.file_id)
            result.append({
                "file_id": r.file_id,
                "file_name": f.filename if f else "Unknown",
                "chunk_count": r.chunk_count,
                "created_at": r.last_ingest_time,
                "tag": tag or "mixed"
            })

    return result, total