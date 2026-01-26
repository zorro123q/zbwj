# scripts/kb_export_offline.py
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from domain.kb.export import export_search_to_docx


def main():
    ap = argparse.ArgumentParser(description="Offline export KB search results to docx")
    ap.add_argument("--query", required=True)
    ap.add_argument("--top-k", type=int, default=50)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--title-keyword", action="append", default=None, help="可多次传入：--title-keyword 功能")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        out_path = export_search_to_docx(
            query=args.query,
            top_k=args.top_k,
            by_tag=args.tag,
            title_keywords=args.title_keyword,
        )
    print(f"Exported -> {out_path}")


if __name__ == "__main__":
    main()
