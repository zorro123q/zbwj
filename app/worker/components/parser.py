from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


class Parser:
    @staticmethod
    def parse(path: Path, ext: str) -> str:
        ext = (ext or "").lower().strip()

        if ext == "txt":
            # 【修复乱码】优先尝试 UTF-8，失败则回退到 GB18030 (支持中文 GBK)
            try:
                with path.open("r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                with path.open("r", encoding="gb18030", errors="ignore") as f:
                    return f.read()

        if ext == "docx":
            # 优先用 python-docx；如果环境里装错了 docx 包，会报 "No module named exceptions"
            try:
                from docx import Document  # python-docx 正确用法
                doc = Document(str(path))
                parts = []
                for p in doc.paragraphs:
                    if p.text:
                        parts.append(p.text)
                return "\n".join(parts)
            except Exception:
                # fallback：不依赖任何第三方库，直接解析 docx(zip) 的 document.xml
                return Parser._parse_docx_fallback(path)

        raise ValueError("unsupported file type")

    @staticmethod
    def _parse_docx_fallback(path: Path) -> str:
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with zipfile.ZipFile(str(path), "r") as z:
            xml_bytes = z.read("word/document.xml")

        root = ET.fromstring(xml_bytes)

        paragraphs = []
        for p in root.findall(".//w:p", ns):
            texts = []
            for t in p.findall(".//w:t", ns):
                if t.text:
                    texts.append(t.text)
            line = "".join(texts).strip()
            if line:
                paragraphs.append(line)

        return "\n".join(paragraphs)