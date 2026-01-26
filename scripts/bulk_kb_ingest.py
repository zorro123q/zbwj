import argparse
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import requests
from tqdm import tqdm


def upload_file(
    session: requests.Session,
    upload_url: str,
    file_path: Path,
    field_name: str = "file",
    extra_form: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> str:
    """
    上传文件到服务端，返回 file_id。
    你需要把 upload_url/field_name 调成与你项目的上传接口一致。
    期望响应 JSON 里包含 {"id": "..."} 或 {"file_id": "..."} 之一。
    """
    extra_form = extra_form or {}
    with file_path.open("rb") as f:
        files = {field_name: (file_path.name, f)}
        resp = session.post(upload_url, data=extra_form, files=files, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"upload failed: {resp.status_code} {resp.text}")

    data = resp.json()
    file_id = data.get("file_id") or data.get("id")
    if not file_id:
        raise RuntimeError(f"upload response missing file_id/id: {data}")
    return file_id


def ingest_kb(
    session: requests.Session,
    kb_ingest_url: str,
    file_id: str,
    title: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    payload = {"file_id": file_id, "title": title}
    resp = session.post(kb_ingest_url, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"kb ingest failed: {resp.status_code} {resp.text}")
    return resp.json()


def guess_title(file_path: Path) -> str:
    # 默认用文件名（不含后缀）作为 title
    return file_path.stem


def main():
    ap = argparse.ArgumentParser(description="Bulk upload files and ingest into KB")
    ap.add_argument("--root", required=True, help="本地文件夹路径（递归扫描）")
    ap.add_argument("--pattern", default="*.docx", help="glob 模式，如 *.docx 或 *.pdf")
    ap.add_argument("--server", default="http://127.0.0.1:5000", help="服务地址")
    ap.add_argument("--upload-url", default="/api/v1/files/upload", help="上传接口路径（相对 server）")
    ap.add_argument("--upload-field", default="file", help="上传表单字段名（默认 file）")
    ap.add_argument("--kb-ingest-url", default="/api/v1/kb/ingest", help="KB ingest 接口路径（相对 server）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不执行")
    ap.add_argument("--out", default="bulk_kb_result.jsonl", help="输出结果（jsonl）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"root not found: {root}")

    server = args.server.rstrip("/")
    upload_url = server + args.upload_url
    kb_ingest_url = server + args.kb_ingest_url

    files = sorted(root.rglob(args.pattern))
    if not files:
        print(f"No files matched: {root} / {args.pattern}")
        return

    session = requests.Session()

    out_path = Path(args.out).resolve()
    ok = 0
    fail = 0

    with out_path.open("w", encoding="utf-8") as out_f:
        for p in tqdm(files, desc="ingesting"):
            record: Dict[str, Any] = {"path": str(p)}
            try:
                title = guess_title(p)
                record["title"] = title

                if args.dry_run:
                    record["dry_run"] = True
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ok += 1
                    continue

                file_id = upload_file(
                    session=session,
                    upload_url=upload_url,
                    file_path=p,
                    field_name=args.upload_field,
                )
                record["file_id"] = file_id

                kb_result = ingest_kb(
                    session=session,
                    kb_ingest_url=kb_ingest_url,
                    file_id=file_id,
                    title=title,
                )
                record["kb_result"] = kb_result
                record["status"] = "ok"
                ok += 1

            except Exception as e:
                record["status"] = "failed"
                record["error"] = str(e)
                fail += 1

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Done. ok={ok} fail={fail}. results -> {out_path}")


if __name__ == "__main__":
    main()
