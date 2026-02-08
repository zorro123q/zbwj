import argparse
import json
import sys
import uuid
from datetime import datetime  # 【核心修改】引入 datetime
import mimetypes
from pathlib import Path

# 添加项目根目录到 sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.models import File
from domain.kb.ingest import IngestLogic


def main():
    ap = argparse.ArgumentParser(description="Offline KB slicing (Create File records -> Semantic Ingest)")
    ap.add_argument("--root", required=True, help="文档目录（递归扫描）")
    ap.add_argument("--pattern", default="*.docx")
    ap.add_argument("--tag", default="offline_import", help="知识库标签")
    ap.add_argument(
        "--exclude",
        action="append",
        default=["storage/kb/blocks", r"storage\kb\blocks", "instance", ".git", "__pycache__"],
        help="排除目录（相对 root 或 绝对路径部分匹配）。可多次传入：--exclude xxx",
    )
    ap.add_argument("--out", default="kb_ingest_offline.jsonl")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"root not found: {root}")

    # 规范化排除路径
    exclude_paths = [str(Path(x).resolve()) for x in (args.exclude or [])]

    app = create_app()
    out_path = Path(args.out).expanduser().resolve()

    ok = 0
    fail = 0
    results = []

    print(f"Start scanning: {root} pattern={args.pattern}")

    with app.app_context():
        # 递归查找文件
        files_to_process = list(root.rglob(args.pattern))
        total_files = len(files_to_process)
        print(f"Found {total_files} files.")

        for idx, p in enumerate(files_to_process, 1):
            rp = p.resolve()
            str_rp = str(rp)

            # 1. 排除检查
            if any(ex in str_rp for ex in exclude_paths):
                print(f"[{idx}/{total_files}] Skipped (excluded): {p.name}")
                continue

            # 忽略临时文件
            if p.name.startswith("~$"):
                continue

            try:
                print(f"[{idx}/{total_files}] Processing: {p.name} ...")

                file_id = str(uuid.uuid4())
                stat = p.stat()
                ext = p.suffix.lstrip(".").lower()

                # 【核心修复】创建 File 记录，注意 created_at 必须是 datetime 对象
                file_rec = File(
                    id=file_id,
                    filename=p.name,
                    ext=ext,
                    size=int(stat.st_size),
                    storage_path=str_rp,
                    created_at=datetime.now()  # 这里修正为 datetime 对象
                )

                db.session.add(file_rec)
                db.session.commit()

                # 3. 调用语义切分入库逻辑
                chunk_count = IngestLogic.ingest_file(file_id, tag=args.tag)

                res = {
                    "status": "ok",
                    "path": str_rp,
                    "file_id": file_id,
                    "chunks": chunk_count
                }
                results.append(res)
                ok += 1
                print(f"   -> OK. ID: {file_id}, Chunks: {chunk_count}")

            except Exception as e:
                db.session.rollback()
                err_msg = str(e)
                results.append({"status": "failed", "path": str(rp), "error": err_msg})
                fail += 1
                print(f"   -> FAILED: {err_msg}")

    # 输出结果日志
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nDone. ok={ok} fail={fail}. Log saved to -> {out_path}")


if __name__ == "__main__":
    main()