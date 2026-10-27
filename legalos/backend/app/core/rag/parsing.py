"""Page-aware document parsing (PDF, DOCX, TXT/MD).

PDF uses pdfplumber (MIT) - no AGPL dependency. Scanned PDFs (almost no extractable text)
are flagged via `is_scanned` so callers can route them to Gemini OCR.
"""
import io
import logging
import re
from dataclasses import dataclass, field
from typing import List

from app.shared.exceptions import BadRequestException

logger = logging.getLogger("legalos.parsing")

MAX_PAGES = 150
# Below this average, a PDF is treated as scanned / image-only.
SCANNED_CHARS_PER_PAGE = 60


@dataclass
class Page:
    number: int
    text: str


@dataclass
class ParsedDocument:
    pages: List[Page]
    kind: str  # "pdf" | "docx" | "text"
    has_pages: bool  # False for DOCX/TXT where real page numbers are unknown
    is_scanned: bool = False
    warnings: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def char_count(self) -> int:
        return sum(len(p.text) for p in self.pages)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip control characters / private-use glyphs that PDFs often contain.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f-�]", "", text)
    return text.strip()


def parse_pdf_pages(file_bytes: bytes) -> ParsedDocument:
    try:
        import pdfplumber  # lazy: heavy import
    except ImportError as e:  # pragma: no cover
        raise BadRequestException("PDF support is not installed on the server.") from e

    pages: List[Page] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise BadRequestException(f"PDF has {len(pdf.pages)} pages; the maximum supported is {MAX_PAGES}.")
            for i, page in enumerate(pdf.pages, 1):
                pages.append(Page(i, _normalize(page.extract_text() or "")))
    except BadRequestException:
        raise
    except Exception as e:
        msg = str(e)
        if "password" in msg.lower() or "encrypted" in msg.lower():
            raise BadRequestException("This PDF is password-protected. Please upload an unlocked copy.")
        raise BadRequestException(f"Failed to read PDF: {msg[:200]}")

    if not pages:
        raise BadRequestException("The PDF has no pages.")
    total = sum(len(p.text) for p in pages)
    scanned = (total / len(pages)) < SCANNED_CHARS_PER_PAGE
    doc = ParsedDocument(pages=pages, kind="pdf", has_pages=True, is_scanned=scanned)
    if scanned:
        doc.warnings.append("This looks like a scanned PDF with little selectable text; OCR is required.")
    return doc


def parse_docx_ordered(file_bytes: bytes) -> ParsedDocument:
    import docx  # python-docx

    try:
        document = docx.Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise BadRequestException(f"Failed to read DOCX: {str(e)[:200]}")

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    lines: List[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(child, document).text.strip()
            if t:
                lines.append(t)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells = []
                for c in row.cells:
                    ct = c.text.strip()
                    if ct and (not cells or cells[-1] != ct):  # merged cells repeat
                        cells.append(ct)
                if cells:
                    lines.append(" | ".join(cells))
    text = _normalize("\n".join(lines))
    return ParsedDocument(pages=[Page(1, text)], kind="docx", has_pages=False)


def parse_text_bytes(file_bytes: bytes) -> ParsedDocument:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        text = file_bytes.decode("utf-8", errors="ignore")
    return ParsedDocument(pages=[Page(1, _normalize(text))], kind="text", has_pages=False)


def parse_contract_file(file_bytes: bytes, filename: str) -> ParsedDocument:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return parse_pdf_pages(file_bytes)
    if ext in ("docx",):
        return parse_docx_ordered(file_bytes)
    if ext in ("txt", "md"):
        return parse_text_bytes(file_bytes)
    raise BadRequestException(f"Unsupported file type '.{ext}'. Supported: PDF, DOCX, TXT, MD.")
