# scripts/kb_ingest_offline.py
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from domain.kb.ingest import ingest_kb_from_path


def main():
    ap = argparse.ArgumentParser(description="Offline KB slicing (no file_id, no server)")
    ap.add_argument("--root", required=True, help="docx目录（递归扫描）")
    ap.add_argument("--pattern", default="*.docx")
    ap.add_argument("--tag", default=None)
    ap.add_argument(
        "--exclude",
        action="append",
        default=["storage/kb/blocks", r"storage\kb\blocks", "instance/kb_storage", r"instance\kb_storage"],
        help="排除目录（相对 root）。可多次传入：--exclude xxx",
    )
    ap.add_argument("--out", default="kb_ingest_offline.jsonl")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"root not found: {root}")

    exclude_paths = [(root / x).resolve() for x in (args.exclude or [])]

    app = create_app()
    out_path = Path(args.out).expanduser().resolve()

    ok = 0
    fail = 0
    results = []

    with app.app_context():
        for p in root.rglob(args.pattern):
            rp = p.resolve()

            # ✅ 排除切片产物目录，避免递归把生成的 blocks 再次当输入
            if any(str(rp).startswith(str(ex)) for ex in exclude_paths):
                continue

            try:
                res = ingest_kb_from_path(str(rp), title=rp.stem, tag=args.tag)
                res["status"] = "ok"
                res["path"] = str(rp)
                results.append(res)
                ok += 1
            except Exception as e:
                db.session.rollback()
                results.append({"status": "failed", "path": str(rp), "error": str(e)})
                fail += 1

    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Done. ok={ok} fail={fail}. results -> {out_path}")


if __name__ == "__main__":
    main()
