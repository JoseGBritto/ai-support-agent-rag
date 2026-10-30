"""Loads documents (.md, .txt, .html, .pdf) and splits them into citable chunks."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}
MAX_CHUNK_CHARS = 900


@dataclass
class Chunk:
    id: int
    source: str      # file name, shown to the customer as the citation
    title: str       # heading path, e.g. "Shipping > International"
    text: str


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader  # imported lazily: optional for non-PDF users
        return "\n\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if suffix in (".html", ".htm"):
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        raw = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>",
                     lambda m: "\n" + "#" * int(m.group(1)) + " " + " ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split()) + "\n", raw)
        raw = re.sub(r"(?i)<(br|/p|/li|/div)[^>]*>", "\n", raw)
        raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return raw


def split_sections(text: str, default_title: str) -> list[tuple[str, str]]:
    """Split on markdown headings, keeping the heading path as the section title."""
    sections, path, buffer = [], [], []

    def flush():
        body = "\n".join(buffer).strip()
        if body:
            sections.append((" > ".join(path) or default_title, body))
        buffer.clear()

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)", line.strip())
        if match:
            flush()
            level = len(match.group(1))
            path[:] = path[: level - 1] + [match.group(2).strip()]
        else:
            buffer.append(line)
    flush()
    return sections


def split_long(body: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces, current = [], ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > limit:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def load_knowledge_base(directory: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(p for p in Path(directory).rglob("*") if p.suffix.lower() in SUPPORTED):
        text = read_document(path)
        for title, body in split_sections(text, path.stem.replace("_", " ").replace("-", " ").title()):
            for piece in split_long(body):
                chunks.append(Chunk(id=len(chunks), source=path.name, title=title, text=piece))
    return chunks
