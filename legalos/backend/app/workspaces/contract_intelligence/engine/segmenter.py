"""Deterministic contract segmentation.

Splits a parsed contract into numbered segments (clauses) with page references, so that
the LLM can cite `S7` and we can verify quotes and point the UI at the right page.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from app.core.rag.parsing import ParsedDocument

MAX_SEGMENT_CHARS = 6000

_ARTICLE = re.compile(r"^(?:ARTICLE|Article|SECTION|Section|CLAUSE|Clause)\s+([IVXLC]+|\d+(?:\.\d+)*)\s*[\.:\-–)]?\s*(.*)$")
_TOP_NUMBERED = re.compile(r"^(\d{1,2})\s*[\.\)]\s+(\S.{0,110})$")
_SUB_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\s*[\.\)]?\s+(\S.*)$")
_ALLCAPS = re.compile(r"^[A-Z][A-Z0-9 ,&/'\-–:()]{3,80}$")
_SCHEDULE = re.compile(r"^(?:SCHEDULE|ANNEXURE|ANNEXURE|EXHIBIT|APPENDIX)\b.*$", re.I)


@dataclass
class Segment:
    id: str                 # "S1", "S2", ...
    number: Optional[str]   # "4", "4.2", "Article III" ...
    heading: str
    text: str
    page_start: Optional[int]
    page_end: Optional[int]

    def label(self) -> str:
        parts = [p for p in (self.number, self.heading) if p]
        return " ".join(parts) if parts else "(untitled)"


def _heading_of(line: str):
    """Returns (number, heading) if the line starts a new top-level segment, else None."""
    s = line.strip()
    if not s or len(s) > 120:
        return None
    m = _ARTICLE.match(s)
    if m:
        return m.group(1), m.group(2).strip().rstrip(":")
    m = _TOP_NUMBERED.match(s)
    if m and not re.match(r"^\d{1,2}\s*[\.\)]\s+\d", s):  # "1. 5000 units" is not a heading
        title = m.group(2).strip()
        # Heading-like: short, or Title/UPPER case without sentence punctuation overload
        if len(title) <= 70 or title.isupper():
            return m.group(1), title.rstrip(":")
    if _SCHEDULE.match(s):
        return None, s
    if _ALLCAPS.match(s) and not s.endswith(".") and len(s.split()) <= 10:
        return None, s.rstrip(":")
    return None


def segment_contract(doc: ParsedDocument) -> List[Segment]:
    # Flatten to (line, page) pairs
    lines: List[tuple[str, Optional[int]]] = []
    for page in doc.pages:
        pno = page.number if doc.has_pages else None
        for ln in page.text.split("\n"):
            if ln.strip():
                lines.append((ln.strip(), pno))

    segments: List[Segment] = []
    cur_num: Optional[str] = None
    cur_head = "Preamble"
    cur_lines: List[str] = []
    cur_pages: List[int] = []

    def flush():
        nonlocal cur_lines, cur_pages
        text = "\n".join(cur_lines).strip()
        if text:
            segments.append(Segment(
                id=f"S{len(segments) + 1}", number=cur_num, heading=cur_head, text=text,
                page_start=min(cur_pages) if cur_pages else None,
                page_end=max(cur_pages) if cur_pages else None,
            ))
        cur_lines, cur_pages = [], []

    for line, pno in lines:
        h = _heading_of(line)
        # A new heading only starts a segment if it is not a sub-clause of the current one
        if h and not _SUB_NUMBERED.match(line):
            flush()
            cur_num, cur_head = h[0], h[1] or line
            cur_lines.append(line)
        else:
            cur_lines.append(line)
        if pno is not None:
            cur_pages.append(pno)
    flush()

    # Documents without recognisable structure: fall back to paragraph windows
    if len(segments) < 3 and sum(len(s.text) for s in segments) > 1500:
        segments = _fallback_paragraph_segments(doc)

    return _split_oversized(segments)


def _fallback_paragraph_segments(doc: ParsedDocument, target: int = 1800) -> List[Segment]:
    segs: List[Segment] = []
    buf: List[str] = []
    pages: List[int] = []
    size = 0

    def flush():
        nonlocal buf, pages, size
        if buf:
            segs.append(Segment(
                id=f"S{len(segs) + 1}", number=None, heading=f"Section {len(segs) + 1}",
                text="\n".join(buf), page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
            ))
        buf, pages, size = [], [], 0

    for page in doc.pages:
        for para in re.split(r"\n\s*\n|\n", page.text):
            para = para.strip()
            if not para:
                continue
            buf.append(para)
            size += len(para)
            if doc.has_pages:
                pages.append(page.number)
            if size >= target:
                flush()
    flush()
    return segs


def _split_oversized(segments: List[Segment]) -> List[Segment]:
    out: List[Segment] = []
    for seg in segments:
        if len(seg.text) <= MAX_SEGMENT_CHARS:
            out.append(seg)
            continue
        # Split at sub-clause boundaries first, then at paragraph boundaries
        parts: List[str] = []
        buf: List[str] = []
        size = 0
        for ln in seg.text.split("\n"):
            if size >= MAX_SEGMENT_CHARS * 0.6 and (_SUB_NUMBERED.match(ln) or size >= MAX_SEGMENT_CHARS):
                parts.append("\n".join(buf))
                buf, size = [], 0
            buf.append(ln)
            size += len(ln) + 1
        if buf:
            parts.append("\n".join(buf))
        for i, p in enumerate(parts, 1):
            out.append(Segment(
                id="", number=seg.number, heading=f"{seg.heading} (part {i})" if len(parts) > 1 else seg.heading,
                text=p, page_start=seg.page_start, page_end=seg.page_end,
            ))
    for i, s in enumerate(out, 1):
        s.id = f"S{i}"
    return out


def render_for_llm(segments: List[Segment]) -> str:
    """Whole document with explicit segment markers the model can cite."""
    blocks = []
    for s in segments:
        page = f" | p.{s.page_start}" + (f"-{s.page_end}" if s.page_end and s.page_end != s.page_start else "") if s.page_start else ""
        blocks.append(f"[[{s.id} | {s.label()}{page}]]\n{s.text}")
    return "\n\n".join(blocks)


@dataclass
class Coverage:
    """How much of the contract the model was shown (long documents are cut at whole-clause boundaries)."""
    reviewed_segments: int
    total_segments: int
    reviewed_pages: Optional[int] = None     # last page that was fully or partly shown
    total_pages: Optional[int] = None

    @property
    def truncated(self) -> bool:
        return self.reviewed_segments < self.total_segments


def limit_for_llm(segments: List[Segment], max_chars: int) -> tuple[List[Segment], Coverage]:
    """Keep whole segments, in order, until the character budget is used. Always keeps at least one."""
    kept: List[Segment] = []
    size = 0
    for s in segments:
        cost = len(s.text) + len(s.heading) + 40
        if kept and size + cost > max_chars:
            break
        kept.append(s)
        size += cost
    pages = [s.page_end or s.page_start for s in segments if (s.page_end or s.page_start)]
    shown = [s.page_end or s.page_start for s in kept if (s.page_end or s.page_start)]
    return kept, Coverage(
        reviewed_segments=len(kept), total_segments=len(segments),
        reviewed_pages=max(shown) if shown else None, total_pages=max(pages) if pages else None,
    )
