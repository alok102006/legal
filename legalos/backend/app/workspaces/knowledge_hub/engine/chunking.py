"""Structure-aware, page-aware chunking.

- A chunk never crosses a page, so every citation can name its page.
- Headings / numbered sections are detected and carried as `section` on every chunk under them; the
  section title is prepended for embedding ("Leave > Unused leave up to 12 days...") so a short chunk
  keeps its meaning. The stored `text` stays verbatim for quoting.
- Table rows (from CSV/XLSX/DOCX tables rendered as "a | b | c") are kept with their header row.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from app.core.rag.parsing import ParsedDocument

TARGET_CHARS = 900
OVERLAP_CHARS = 150
MAX_CHUNKS = 1500

_HEADING = re.compile(
    r"^(?:(?:section|article|clause|chapter|part|अध्याय|धारा)\s+[\dIVXivx]+[\.\):]?\s*.{0,80}"
    r"|\d{1,2}(?:\.\d{1,2}){0,2}[\.\)]?\s+[^\d\n].{2,80}"
    r"|[A-Z][A-Z0-9 ,&/'\-():]{3,70}"
    r"|[^\n]{3,70}:)$"
)
_TABLE_ROW = re.compile(r"^[^|\n]*\|[^|\n]*(\|[^|\n]*)*$")


@dataclass
class Chunk:
    index: int
    page: Optional[int]
    text: str                       # verbatim
    section: Optional[str] = None   # nearest heading above
    kind: str = "text"              # text | table

    @property
    def embed_text(self) -> str:
        return f"{self.section}\n{self.text}" if self.section else self.text


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 90 or s.endswith((".", ";", ",")) and not s.endswith(":"):
        return False
    if _TABLE_ROW.match(s):
        return False
    return bool(_HEADING.match(s)) and len(s.split()) <= 14


def _blocks(text: str):
    """Yields (kind, text, heading_or_None) blocks: headings, table groups, paragraphs."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if _TABLE_ROW.match(line.strip()):
            rows = []
            while i < len(lines) and _TABLE_ROW.match(lines[i].strip()):
                rows.append(lines[i].strip())
                i += 1
            yield ("table", "\n".join(rows), None)
            continue
        if _is_heading(line):
            yield ("heading", line.strip().rstrip(":"), None)
            i += 1
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_heading(lines[i]) and not _TABLE_ROW.match(lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        yield ("text", " ".join(para), None)


def _split_long(text: str) -> List[str]:
    out: List[str] = []
    while len(text) > TARGET_CHARS * 1.6:
        cut = max(text.rfind(". ", 0, TARGET_CHARS), text.rfind("। ", 0, TARGET_CHARS))
        cut = cut + 1 if cut > TARGET_CHARS // 2 else TARGET_CHARS
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def chunk_document(doc: ParsedDocument) -> List[Chunk]:
    chunks: List[Chunk] = []
    section: Optional[str] = None

    def emit(buf: List[str], page: Optional[int], kind: str = "text") -> None:
        text = "\n".join(buf).strip()
        if len(text) >= 20 and (not chunks or chunks[-1].text != text):
            chunks.append(Chunk(len(chunks), page, text, section, kind))

    for page in doc.pages:
        number = page.number if doc.has_pages else None
        buf: List[str] = []
        size = 0
        for kind, body, _ in _blocks(page.text):
            if kind == "heading":
                emit(buf, number)
                buf, size = [], 0
                section = body
                continue
            if kind == "table":
                emit(buf, number)
                buf, size = [], 0
                rows = body.split("\n")
                header, data = rows[0], rows[1:] or rows
                step = max(1, (TARGET_CHARS // max(1, len(header) + 1)))
                for j in range(0, len(data), max(1, step)):
                    group = [header] + data[j:j + step] if data is not rows else data
                    emit(group, number, "table")
                continue
            for para in _split_long(body):
                if buf and size + len(para) > TARGET_CHARS:
                    emit(buf, number)
                    tail = "\n".join(buf)[-OVERLAP_CHARS:]
                    buf, size = [tail], len(tail)
                buf.append(para)
                size += len(para)
        emit(buf, number)
        if len(chunks) >= MAX_CHUNKS:
            break
    return chunks[:MAX_CHUNKS]
