"""Deterministic contract segmentation.

Splits a parsed contract into numbered segments (clauses) with page references, so that
the LLM can cite `S7` and we can verify quotes and point the UI at the right page.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Set

from app.core.rag.parsing import ParsedDocument

MAX_SEGMENT_CHARS = 6000

# \d is Unicode-aware, so Devanagari digits (१, २, ५.२) number clauses exactly like 1, 2, 5.2.
# Hindi drafting uses धारा / खंड / खण्ड / अनुच्छेद for "clause/section/article" and may end numbers with a danda (।).
_ARTICLE = re.compile(
    r"^(?:ARTICLE|Article|SECTION|Section|CLAUSE|Clause|धारा|खंड|खण्ड|अनुच्छेद|क्लॉज़|क्लॉज)\s+"
    r"([IVXLC]+|\d+(?:\.\d+)*)(?![A-Za-z])\s*[\.:\-–)।]?\s*(.*)$")
_TOP_NUMBERED = re.compile(r"^(\d{1,2})\s*[\.\)।]\s+(\S.{0,110})$")
_SUB_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\s*[\.\)।]?\s+(\S.*)$")
_ALLCAPS = re.compile(r"^[A-Z][A-Z0-9 ,&/'\-–:()]{3,80}$")
_SCHEDULE = re.compile(r"^(?:SCHEDULE|ANNEXURE|EXHIBIT|APPENDIX|अनुसूची|परिशिष्ट|संलग्नक)(?:\b|\s|$).*$", re.I)


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
    if m and not re.match(r"^\d{1,2}\s*[\.\)।]\s+\d", s):  # "1. 5000 units" is not a heading
        title = m.group(2).strip()
        sentence = title.endswith((".", "।")) and len(title.split()) > 6 and not title.isupper()
        # Heading-like: short, or UPPER case; a numbered full sentence is a list item, not a clause heading
        if not sentence and (len(title) <= 70 or title.isupper()):
            return m.group(1), title.rstrip(":")
    if _SCHEDULE.match(s):
        return None, s
    if _ALLCAPS.match(s) and not s.endswith(".") and len(s.split()) <= 10:
        return None, s.rstrip(":")
    return None


def segment_contract(doc: ParsedDocument, heading_lines: Optional[Set[str]] = None) -> List[Segment]:
    """Split into clause segments. `heading_lines` are lines the source format marked as headings (Word
    "Heading" styles), which carry no visible numbering and would otherwise be read as body text."""
    heading_lines = heading_lines or set()
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
        h = _heading_of(line) or ((None, line) if line in heading_lines else None)
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
    parts: int = 1                           # model passes the reviewed text was split into

    @property
    def truncated(self) -> bool:
        return self.reviewed_segments < self.total_segments


def _cost(s: Segment) -> int:
    return len(s.text) + len(s.heading) + 40


def _last_page(segments: List[Segment]) -> Optional[int]:
    pages = [s.page_end or s.page_start for s in segments if (s.page_end or s.page_start)]
    return max(pages) if pages else None


def split_for_llm(segments: List[Segment], max_chars: int, max_parts: int = 2) -> tuple[List[List[Segment]], Coverage]:
    """Cut the contract into at most `max_parts` consecutive parts of whole segments, each within the budget.

    A contract that fits is one part (the normal case). A long one gets a second part reviewed by one extra call,
    so a 60-page agreement is read end to end. Only text beyond `max_parts` budgets is left unreviewed, and
    Coverage says exactly how much that is."""
    parts: List[List[Segment]] = [[]]
    size = 0
    for s in segments:
        if parts[-1] and size + _cost(s) > max_chars:
            if len(parts) == max_parts:
                break
            parts.append([])
            size = 0
        parts[-1].append(s)
        size += _cost(s)
    kept = [s for p in parts for s in p]
    return parts, Coverage(
        reviewed_segments=len(kept), total_segments=len(segments),
        reviewed_pages=_last_page(kept), total_pages=_last_page(segments), parts=len(parts),
    )


def limit_for_llm(segments: List[Segment], max_chars: int) -> tuple[List[Segment], Coverage]:
    """Keep whole segments, in order, until the character budget is used. Always keeps at least one."""
    parts, cov = split_for_llm(segments, max_chars, max_parts=1)
    return parts[0], cov
