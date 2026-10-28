"""Structure-aware, page-aware chunking for any company document.

What a chunk guarantees, and why:
- It never crosses a page, so every citation can name its page.
- It carries a `section` path built from the heading hierarchy ("4. SUM INSURED > Section II > 4.2"): numbered
  headings (1. / 1.1 / 1.1.1), markdown/DOCX headings, keyword headings (Section, Chapter, Annexure, अध्याय, धारा),
  ALL-CAPS and short isolated title lines (which also catches Hindi/Gujarati titles). Numbered clauses inside the
  chunk are appended ("> 2.3–2.5"), so "what does clause 2.4 say" can be found and cited.
- The stored `text` is verbatim (quotes are verified against it); the section path and, for tables, the
  `Header: value` reading of each row are added only to the text that is embedded.
- Lists stay with their lead-in line ("You must carry:" + its bullets); tables are cut every few rows and every
  piece repeats the header row; long paragraphs are cut at sentence ends, never inside a number or amount.
- Consecutive chunks of one section overlap by the last sentence, so an answer spanning the cut is still seen.
- Repeated page headers/footers (letterheads, "Page 3 of 12") are removed, and duplicate chunks are dropped.
"""
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

from app.core.rag.parsing import ParsedDocument

CHUNKER_VERSION = "chunks-2"   # stored with the index: documents chunked by an older version are re-chunked
TARGET_CHARS = 900
MAX_CHARS = 1400
OVERLAP_CHARS = 220
TABLE_ROWS = 6
MAX_CHUNKS = 1500
MIN_CHARS = 20

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
# "1." / "1)" / "1.1" / "1.1.1." followed by text; a bare "12 August 2026" is not a number heading
_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){1,3}\.?|\d{1,2}[.)])\s+(\S.*)$")
_KEYWORD = re.compile(
    r"^(section|article|clause|chapter|part|schedule|annexure|annex|appendix|exhibit|rule|"
    r"अध्याय|धारा|भाग|अनुसूची|परिशिष्ट|नियम|खंड|प्रकरण)\s+([\dIVXLivxl]+|[A-Za-z])\b[.:)\-–]?\s*(.*)$", re.I)
_TOP_KEYWORDS = {"chapter", "part", "schedule", "annexure", "annex", "appendix", "exhibit", "अध्याय", "भाग", "अनुसूची", "परिशिष्ट", "प्रकरण"}
_LIST_ITEM = re.compile(r"^([-•*▪●◦·➢✓]|\(?[a-zA-Z]\)|\(?[ivxIVX]{1,4}\)|\([क-ह]\)|[क-ह]\)|\d{1,2}\))\s+\S")
_CLAUSE = re.compile(r"^(?:(\d{1,2}(?:\.\d{1,3}){1,3})\.?|(\d{1,2})[.)])\s+\S|^(?:step|rule|clause|article)\s+(\d{1,3})\b", re.I)
_TERMINAL = (".", ";", ",", "।", "॥", "?", "!")
_CURRENCY = {"rs", "₹", "inr", "rupees", "usd", "$"}
_ABBREV = {"rs", "no", "nos", "mr", "mrs", "ms", "dr", "sr", "jr", "ltd", "pvt", "co", "inc", "st", "vs", "viz", "eg",
           "ie", "etc", "sec", "cl", "art", "approx", "govt", "dept", "fig", "ref", "sl", "max", "min", "qty", "amt",
           "dt", "p", "pp", "vol", "regd", "addl", "asst", "smt", "shri", "sh", "m/s", "w.e.f", "e.g", "i.e"}


@dataclass
class Chunk:
    index: int
    page: Optional[int]
    text: str                       # verbatim
    section: Optional[str] = None   # heading path ("4. Sum insured > 4.2")
    kind: str = "text"              # text | table | list
    embed: Optional[str] = None     # extra reading for embedding (tables: Header: value rows)

    @property
    def embed_text(self) -> str:
        body = self.embed or self.text
        return f"{self.section}\n{body}" if self.section else body


# ----------------------------------------------------------------- line classification

def is_table_row(line: str) -> bool:
    return line.count("|") >= 1 and len([c for c in line.split("|") if c.strip()]) >= 2


def _letters(s: str) -> List[str]:
    return [ch for ch in s if ch.isalpha()]


def heading_of(line: str) -> Optional[Tuple[Optional[int], str]]:
    """(level, text) when the line is a heading; level None = unnumbered (nests under the open numbered heading)."""
    s = line.strip()
    m = _MD_HEADING.match(s)
    if m:
        return len(m.group(1)), m.group(2).strip().rstrip(":")
    if not s or len(s) > 100 or is_table_row(s) or len(s.split()) > 14:
        return None
    if s.endswith(_TERMINAL) or not _letters(s):
        return None
    m = _KEYWORD.match(s)
    if m:
        return (1 if m.group(1).lower() in _TOP_KEYWORDS else None), s.rstrip(":")
    m = _NUMBERED.match(s)
    if m:
        rest = m.group(2)
        if rest[0].isdigit() or len(rest.split()) > 12 or not _letters(rest) or ":" in rest.rstrip(":"):
            return None                                           # "2.1 Building: Rs 3,50,00,000" is a fact
        return m.group(1).rstrip(".)").count(".") + 1, s.rstrip(":")
    if ":" in s.rstrip(":"):                                      # "Policy No: 123" is a fact, not a heading
        return None
    letters = _letters(s)
    latin = [ch for ch in letters if ch.isascii()]
    digits = sum(ch.isdigit() for ch in s)
    if len(latin) >= 4 and len(latin) == len(letters) and sum(ch.isupper() for ch in latin) >= 0.8 * len(latin) and digits < 0.3 * len(s):
        return None, s.rstrip(":")
    if s.endswith(":") and len(s.split()) <= 8:
        return None, s.rstrip(":")
    return None


def _short_title(line: str) -> bool:
    """A short line with no sentence punctuation; used when it stands alone between blank lines (Hindi titles)."""
    s = line.strip()
    return (0 < len(s.split()) <= 8 and len(s) <= 80 and not s.endswith(_TERMINAL) and bool(_letters(s))
            and ":" not in s and not is_table_row(s) and not _LIST_ITEM.match(s))


def _numbered_depth(line: str) -> Optional[int]:
    """Depth of a short numbered line without sentence punctuation at the end ("2.1 Scope" -> 2, "1. Mr. A. Patel,
    Director (DIN 0123)" -> 1); None for anything else, including numbered paragraphs that are full sentences."""
    m = _NUMBERED.match(line)
    if not m or len(line) > 160 or line.endswith(_TERMINAL) or m.group(2)[0].isdigit() or not _letters(m.group(2)):
        return None
    return m.group(1).rstrip(".)").count(".") + 1


def clause_number(line: str) -> Optional[str]:
    m = _CLAUSE.match(line.strip())
    return next((g for g in m.groups() if g), None) if m else None


# ----------------------------------------------------------------- blocks

@dataclass
class _Block:
    kind: str                          # heading | text | list | table
    lines: List[str]
    level: Optional[int] = None        # headings only
    clause: Optional[str] = None       # numbered clause that starts this text block


def _blocks(text: str) -> Iterator[_Block]:
    lines = [l.rstrip() for l in text.split("\n")]
    n = len(lines)
    i = 0
    prev_blank = True
    while i < n:
        s = lines[i].strip()
        if not s:
            i, prev_blank = i + 1, True
            continue
        if is_table_row(s) and i + 1 < n and is_table_row(lines[i + 1].strip()):
            rows = []
            while i < n and is_table_row(lines[i].strip()):
                rows.append(lines[i].strip())
                i += 1
            yield _Block("table", rows)
            prev_blank = False
            continue
        h = heading_of(s)
        next_blank = i + 1 >= n or not lines[i + 1].strip()
        prev_line = next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")
        next_line = next((lines[j].strip() for j in range(i + 1, n) if lines[j].strip()), "")
        depth = _numbered_depth(s)
        if depth and depth in (_numbered_depth(prev_line), _numbered_depth(next_line)):
            # "1. Mr. A, Director / 2. Ms. B, Director": a run of short numbered lines is a list, not headings
            items = []
            while i < n and (not lines[i].strip() or _numbered_depth(lines[i].strip()) == depth):
                if lines[i].strip():
                    items.append(lines[i].strip())
                i += 1
            yield _Block("list", items)
            prev_blank = False
            continue
        if h and not _MD_HEADING.match(s) and s.endswith(":") and (
                _LIST_ITEM.match(next_line) or is_table_row(next_line) or clause_number(next_line)):
            h = None                # "The following are excluded:" introduces the list below; it is not a heading
        if h is None and prev_blank and next_blank and _short_title(s) and i + 1 < n:
            h = (None, s)
        if h:
            yield _Block("heading", [h[1]], level=h[0])
            i += 1
            prev_blank = False
            continue
        if _LIST_ITEM.match(s):
            items = []
            while i < n and lines[i].strip() and not is_table_row(lines[i].strip()) and not (heading_of(lines[i]) and not _LIST_ITEM.match(lines[i].strip())):
                items.append(lines[i].strip())
                i += 1
                if i < n and not lines[i].strip() and i + 1 < n and _LIST_ITEM.match(lines[i + 1].strip()):
                    i += 1                                       # a blank line between bullets keeps the list together
            yield _Block("list", items)
            prev_blank = False
            continue
        para = [s]
        clause = clause_number(s)
        i += 1
        while i < n:
            t = lines[i].strip()
            if not t or is_table_row(t) or _LIST_ITEM.match(t) or heading_of(t) or clause_number(t):
                break
            para.append(t)
            i += 1
        yield _Block("text", para, clause=clause)
        prev_blank = False


# ----------------------------------------------------------------- splitting

def sentence_ends(text: str) -> List[int]:
    """Offsets just after a sentence end where a cut is safe: not after 'Rs.', 'No.', initials, or inside '4.2'."""
    ends = []
    for m in re.finditer(r"[.!?।॥;](?=\s+\S)", text):
        if m.group() == ".":
            prev = re.split(r"\s", text[:m.start()])[-1].lower().strip("(\"'")
            nxt = text[m.end():].lstrip()[:1]
            if prev in _ABBREV or (len(prev) == 1 and prev.isalpha()) or (prev[-1:].isdigit() and nxt.isdigit()):
                continue
        ends.append(m.end())
    return ends


def _safe_space(text: str, limit: int) -> int:
    """Last whitespace before `limit` where the next word is not a number (keeps 'Rs 3,50,000' / '45 days' whole)."""
    for m in reversed(list(re.finditer(r"\s+", text[:limit]))):
        nxt = text[m.end():].split(None, 1)[0] if text[m.end():].strip() else ""
        prev = text[:m.start()].split()[-1:] or [""]
        if (m.start() > limit // 3 and not nxt[:1].isdigit() and nxt.lower().strip(".") not in _CURRENCY
                and prev[0].lower().strip(".") not in _ABBREV | _CURRENCY):
            return m.start()
    m = list(re.finditer(r"\s+", text[:limit]))
    return m[-1].start() if m else limit


def split_text(text: str, target: int = TARGET_CHARS, hard: int = MAX_CHARS) -> List[str]:
    """Cuts a long passage into pieces of about `target` chars at sentence ends (or, failing that, between words)."""
    out: List[str] = []
    while len(text) > hard:
        ends = [e for e in sentence_ends(text) if e <= target * 1.25]
        cut = ends[-1] if ends and ends[-1] >= target // 3 else _safe_space(text, target)
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def _last_sentence(text: str) -> str:
    ends = sentence_ends(text)                    # offsets of sentence starts after the first one
    tail = (text[ends[-1]:] if ends else text).strip()
    return tail if 0 < len(tail) <= OVERLAP_CHARS else ""


def _row_reading(header: str, row: str) -> str:
    """'A | B' + '1 | 2' -> 'A: 1; B: 2' (what the embedding sees for a positional table row)."""
    hs = [h.strip() for h in header.split("|")]
    vs = [v.strip() for v in row.split("|")]
    if len(hs) != len(vs):
        return row
    return "; ".join(f"{h}: {v}" for h, v in zip(hs, vs) if v)


def table_reading(text: str) -> Optional[str]:
    """The embedding reading of a stored table chunk (caption lines, then `Header: value` rows), so a chunk
    re-indexed from the database embeds exactly like a freshly chunked one."""
    lines = text.split("\n")
    first = next((k for k, l in enumerate(lines) if is_table_row(l)), None)
    rows = lines[first:] if first is not None else []
    if len(rows) < 2 or _is_kv_table(rows):
        return None
    return "\n".join(lines[:first] + [_row_reading(rows[0], r) for r in rows[1:]])


def _is_kv_table(rows: List[str]) -> bool:
    return all(all(":" in c for c in r.split("|") if c.strip()) for r in rows)


def table_pieces(rows: List[str]) -> List[Tuple[str, Optional[str]]]:
    """Table rows -> (verbatim text, embedding reading) pieces of a few rows; positional tables repeat the header."""
    kv = _is_kv_table(rows)
    header, data = (None, rows) if kv or len(rows) < 2 else (rows[0], rows[1:])
    pieces: List[Tuple[str, Optional[str]]] = []
    group: List[str] = []

    def flush():
        if group:
            body = ([header] if header else []) + group
            reading = "\n".join(_row_reading(header, r) for r in group) if header else None
            pieces.append(("\n".join(body), reading))

    size = len(header or "")
    for r in data:
        if group and (len(group) >= TABLE_ROWS or size + len(r) > TARGET_CHARS):
            flush()
            group, size = [], len(header or "")
        group.append(r)
        size += len(r) + 1
    flush()
    return pieces


# ----------------------------------------------------------------- page furniture

def _furniture(pages: List[str]) -> set:
    """Lines repeated at the top or bottom of most pages (letterheads, footers, 'Page 3 of 12')."""
    if len(pages) < 3:
        return set()
    counts: Counter = Counter()
    for text in pages:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        edge = set(lines[:2] + lines[-2:])
        counts.update({re.sub(r"\d+", "#", l) for l in edge})
    return {k for k, c in counts.items() if c >= max(3, 0.6 * len(pages))}


def _strip_furniture(text: str, furniture: set) -> str:
    if not furniture:
        return text
    return "\n".join(l for l in text.split("\n") if re.sub(r"\d+", "#", l.strip()) not in furniture)


# ----------------------------------------------------------------- assembling

class _Sections:
    """Heading stack -> section path."""

    def __init__(self):
        self.stack: List[Tuple[int, str, bool]] = []         # (level, text, numbered)

    def push(self, level: Optional[int], text: str) -> None:
        numbered = level is not None
        if level is None:
            depth = max((lv for lv, _, num in self.stack if num), default=0)
            level = depth + 1
        self.stack = [e for e in self.stack if e[0] < level] + [(level, text[:90], numbered)]

    def path(self, clauses: List[str]) -> Optional[str]:
        parts = [t for _, t, _ in self.stack]
        heading_nums = {t.split()[0].rstrip(".)") for t in parts if t[:1].isdigit()}
        clauses = [c for c in clauses if c not in heading_nums]
        if clauses:
            parts.append(clauses[0] if len(clauses) == 1 or clauses[0] == clauses[-1] else f"{clauses[0]}–{clauses[-1]}")
        return " > ".join(parts)[:300] or None


def chunk_document(doc: ParsedDocument) -> List[Chunk]:
    chunks: List[Chunk] = []
    seen: set = set()
    sections = _Sections()
    furniture = _furniture([p.text for p in doc.pages]) if doc.has_pages else set()

    def emit(text: str, page: Optional[int], section: Optional[str], kind: str = "text", embed: Optional[str] = None) -> None:
        text = text.strip()
        key = " ".join(text.lower().split())
        if not key or key in seen or not any(ch.isalnum() for ch in key):
            return
        seen.add(key)
        chunks.append(Chunk(len(chunks), page, text, section, kind, embed))

    for page in doc.pages:
        number = page.number if doc.has_pages else None
        buf: List[Tuple[str, Optional[str]]] = []                # (text piece, numbered clause it belongs to)

        def size() -> int:
            return sum(len(t) + 1 for t, _ in buf)

        def flush(force: bool = False, carry: bool = False) -> None:
            """Emit the buffer. A fragment under MIN_CHARS waits for the next block unless `force`; with `carry`
            the last sentence starts the next chunk (overlap inside a section)."""
            nonlocal buf
            text = "\n".join(t for t, _ in buf).strip()
            if not text or (len(text) < MIN_CHARS and not force):
                return
            clauses = list(dict.fromkeys(c for _, c in buf if c))
            emit(text, number, sections.path(clauses))
            last, clause = buf[-1]
            tail = _last_sentence(last) if carry else ""
            buf = [(tail, clause if tail == last.strip() else None)] if tail else []

        def pop_lead(max_len: int) -> Optional[Tuple[str, Optional[str]]]:
            """The line introducing a list/table ("You must carry:") travels with it."""
            if buf and buf[-1][0].rstrip().endswith(":") and len(buf[-1][0]) < max_len:
                return buf.pop()
            return None

        for block in _blocks(_strip_furniture(page.text, furniture)):
            if block.kind == "heading":
                flush(force=True)
                sections.push(block.level, block.lines[0])
                continue
            if block.kind == "table":
                lead = pop_lead(300)
                flush(force=True)
                for k, (text, reading) in enumerate(table_pieces(block.lines)):
                    if k == 0 and lead:
                        text, reading = f"{lead[0]}\n{text}", (f"{lead[0]}\n{reading}" if reading else None)
                    emit(text, number, sections.path([lead[1]] if lead and lead[1] else []), "table", reading)
                continue
            if block.kind == "list":
                lead = pop_lead(MAX_CHARS)
                if buf and size() + len(lead[0] if lead else "") + sum(len(x) + 1 for x in block.lines) > TARGET_CHARS:
                    flush(force=True)
                if lead:
                    buf.append(lead)
                for item in block.lines:
                    if buf and size() + len(item) > MAX_CHARS:
                        flush(force=True)
                        if lead:
                            buf = [lead]                         # each piece of a long list keeps its lead-in
                    buf.append((item, lead[1] if lead else None))
                continue
            joined = "\n".join(block.lines)
            for piece in (split_text(" ".join(block.lines)) if len(joined) > MAX_CHARS else [joined]):
                if buf and size() + len(piece) > TARGET_CHARS:
                    flush(carry=True)
                buf.append((piece, block.clause))
        flush(force=True)
        if len(chunks) >= MAX_CHUNKS:
            break
    return chunks[:MAX_CHUNKS]
