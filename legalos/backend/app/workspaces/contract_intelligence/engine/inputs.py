"""Contract-specific input readers.

- DOCX: Word stores automatic clause numbering ("1.", "4.2", "(a)") outside the paragraph text, and headings as
  styles. A plain text dump loses both, so the segmenter cannot see clause boundaries and findings cannot cite
  "Clause 4.2". This reader rebuilds the visible numbers from the numbering definitions and reports which lines
  are styled headings. Tables are kept row by row.
- Photos: several phone photos of one contract are assembled, in upload order, into one image-only PDF, which
  then goes through the page-wise OCR path like any scanned PDF (one page per photo, page numbers preserved).
"""
import io
import re
from typing import Dict, List, Optional, Set, Tuple

from app.core.rag.parsing import Page, ParsedDocument
from app.shared.exceptions import BadRequestException

MAX_PHOTOS = 30
PHOTO_MAX_SIDE = 2200            # px; enough for OCR, keeps a 20-photo PDF to a few MB
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ------------------------------------------------------------------ DOCX

def _roman(n: int) -> str:
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
            (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out, n = out + s, n - v
    return out


def _letters(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(97 + r) + out
    return out


def _format(n: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return _letters(n)
    if fmt == "upperLetter":
        return _letters(n).upper()
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    return str(n)


class _Numbering:
    """Rebuilds Word's visible list numbers ("%1.%2" templates, decimal/letter/roman formats)."""

    def __init__(self, document) -> None:
        self.levels: Dict[str, Dict[int, Tuple[str, str, int]]] = {}   # numId -> ilvl -> (fmt, lvlText, start)
        self.counters: Dict[str, List[int]] = {}
        try:
            root = document.part.numbering_part.element
        except Exception:                                   # no numbering part: nothing is auto-numbered
            return
        abstract = {}
        for an in root.findall(f"{_W}abstractNum"):
            lv = {}
            for lvl in an.findall(f"{_W}lvl"):
                fmt = lvl.find(f"{_W}numFmt")
                txt = lvl.find(f"{_W}lvlText")
                start = lvl.find(f"{_W}start")
                lv[int(lvl.get(f"{_W}ilvl"))] = (
                    fmt.get(f"{_W}val") if fmt is not None else "decimal",
                    txt.get(f"{_W}val") if txt is not None else "",
                    int(start.get(f"{_W}val")) if start is not None else 1,
                )
            abstract[an.get(f"{_W}abstractNumId")] = lv
        for num in root.findall(f"{_W}num"):
            ref = num.find(f"{_W}abstractNumId")
            if ref is not None:
                self.levels[num.get(f"{_W}numId")] = abstract.get(ref.get(f"{_W}val"), {})

    def label(self, num_id: str, ilvl: int) -> str:
        levels = self.levels.get(num_id)
        if not levels or ilvl not in levels:
            return ""
        fmt, text, _ = levels[ilvl]
        if fmt in ("bullet", "none") or not text:
            return ""
        counters = self.counters.setdefault(num_id, [0] * 9)
        if counters[ilvl] == 0:
            counters[ilvl] = levels[ilvl][2] - 1
        counters[ilvl] += 1
        for deeper in range(ilvl + 1, 9):
            counters[deeper] = 0

        def sub(m: re.Match) -> str:
            lvl = int(m.group(1)) - 1
            lfmt, _, start = levels.get(lvl, ("decimal", "", 1))
            return _format(counters[lvl] or start, lfmt)

        return re.sub(r"%(\d)", sub, text).strip()


def _num_props(paragraph) -> Optional[Tuple[str, int]]:
    """(numId, ilvl) from the paragraph, or from its style (headings are often numbered through the style)."""
    for holder in (paragraph._p, getattr(paragraph.style, "element", None)):
        ppr = holder.find(f"{_W}pPr") if holder is not None else None
        num = ppr.find(f"{_W}numPr") if ppr is not None else None
        if num is None:
            continue
        nid, lvl = num.find(f"{_W}numId"), num.find(f"{_W}ilvl")
        if nid is not None and nid.get(f"{_W}val") != "0":
            return nid.get(f"{_W}val"), int(lvl.get(f"{_W}val")) if lvl is not None else 0
    return None


def read_docx(file_bytes: bytes) -> Tuple[ParsedDocument, Set[str]]:
    """-> (document, lines that are Word headings). Visible list numbers are restored in the text."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise BadRequestException(f"Failed to read DOCX: {str(e)[:200]}")
    numbering = _Numbering(document)
    lines: List[str] = []
    headings: Set[str] = set()
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, document)
            text = re.sub(r"[ \t\xa0]+", " ", p.text).strip()
            if not text:
                continue
            props = _num_props(p)
            label = numbering.label(*props) if props else ""
            line = f"{label} {text}" if label and not text.startswith(label) else text
            lines.append(line)
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style.startswith(("heading", "title")) and len(line) <= 120:
                headings.add(line)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells: List[str] = []
                for c in row.cells:
                    ct = re.sub(r"\s+", " ", c.text).strip()
                    if ct and (not cells or cells[-1] != ct):        # merged cells repeat their text
                        cells.append(ct)
                if cells:
                    lines.append(" | ".join(cells))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", "\n".join(lines).replace("\xa0", " ")).strip()
    return ParsedDocument(pages=[Page(1, text)], kind="docx", has_pages=False), headings


# ------------------------------------------------------------------ photos -> one PDF

def photos_to_pdf(photos: List[bytes]) -> bytes:
    """Several photos of a contract, in order, as one image-only PDF (one page per photo).

    Orientation from the phone's EXIF data is applied, and large photos are downscaled so the PDF stays small;
    the OCR path then reads it page by page."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not photos:
        raise BadRequestException("No images were uploaded.")
    if len(photos) > MAX_PHOTOS:
        raise BadRequestException(f"Please upload at most {MAX_PHOTOS} photos per contract.")
    pages = []
    for i, data in enumerate(photos, 1):
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        except (UnidentifiedImageError, OSError):
            raise BadRequestException(f"Photo {i} could not be read as an image.")
        img = img.convert("RGB")
        img.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
        pages.append(img)
    out = io.BytesIO()
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0, quality=85)
    return out.getvalue()
