"""Text, Markdown, PDF and Word extractors."""
from __future__ import annotations

import re
from pathlib import Path

from . import Extracted, Piece, Plugin, register
from .media import ocr_image

CHUNK_CHARS = 1000
CHUNK_OVERLAP = 120
MAX_CHUNKS = 300

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
WIKI_LINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
FILE_NAME = re.compile(r"\b[\w][\w.\-]{0,80}\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|png|jpe?g|mp4|mov|m4a|wav|mp3)\b", re.I)


def chunk_text(text: str, locator: str = "") -> list[Piece]:
    text = text.strip()
    if not text:
        return []
    pieces, start, n = [], 0, 0
    while start < len(text) and n < MAX_CHUNKS:
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + CHUNK_CHARS // 2:
                end = cut + 1
        pieces.append(Piece("text", text[start:end].strip(), locator or f"part {n + 1}"))
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
        n += 1
    return pieces


def find_refs(text: str) -> list[tuple[str, str]]:
    """Raw references only. Whether they resolve is decided later."""
    refs: list[tuple[str, str]] = []
    for m in MD_LINK.finditer(text):
        target = m.group(1)
        if not target.startswith(("http://", "https://", "mailto:", "#")):
            refs.append(("link", target.split("#")[0]))
    refs += [("link", m.group(1).strip()) for m in WIKI_LINK.finditer(text)]
    refs += [("mention", m.group(0).strip()) for m in FILE_NAME.finditer(text)]
    return refs


def _text(path: Path) -> Extracted:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", "ignore")
    title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), "")
    return Extracted(chunk_text(text), {"title": title[:120]}, find_refs(text))


def _pdf(path: Path) -> Extracted:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    pieces, full = [], []
    for i in range(min(len(doc), 200)):
        page = doc[i]
        tp = page.get_textpage()
        text = tp.get_text_range().strip()
        tp.close()
        kind = "text"
        if len(text) < 20:  # a scanned page has no text layer
            pil = page.render(scale=2).to_pil()
            text = ocr_image(pil)
            kind = "ocr"
        for p in chunk_text(text, f"page {i + 1}"):
            p.kind = kind
            pieces.append(p)
        full.append(text)
    props = {"pages": len(doc)}
    title = doc.get_metadata_value("Title") if hasattr(doc, "get_metadata_value") else ""
    if title:
        props["title"] = title
    doc.close()
    return Extracted(pieces, props, find_refs("\n".join(full)))


def _docx(path: Path) -> Extracted:
    from docx import Document

    d = Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    text = "\n".join(parts)
    props = {"title": (d.core_properties.title or (parts[0] if parts else ""))[:120]}
    return Extracted(chunk_text(text), props, find_refs(text))


register(Plugin("text", 3, "text", (".txt", ".md", ".markdown", ".csv", ".log", ".json", ".html"), _text))
register(Plugin("pdf", 3, "text", (".pdf",), _pdf))
register(Plugin("docx", 3, "text", (".docx",), _docx))
