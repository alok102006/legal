"""Quote verification - the main anti-hallucination control.

Every AI finding must quote the document verbatim. We check that the quote really exists
(whitespace/case/punctuation-insensitive, Unicode-aware so Hindi/Gujarati/Marathi text works, with a
fuzzy fallback for OCR/line-break noise) and record which segment/page it came from.

Rules: a quote must carry enough content (>= 25 letters/digits, or >= 5 words); short quotes must match
exactly, only long ones may match fuzzily. Verification proves the text EXISTS; the UI shows exact vs
approximate so a reader can judge whether it supports the claim.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from rapidfuzz import fuzz

from app.workspaces.contract_intelligence.engine.segmenter import Segment

FUZZY_THRESHOLD = 90
FUZZY_MIN_CHARS = 60          # below this, only an exact normalised match counts
MIN_QUOTE_CHARS = 25
MIN_QUOTE_WORDS = 5

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def normalize(s: str) -> str:
    s = s.translate(_QUOTES).lower()
    s = re.sub(r"-\s*\n\s*", "", s)                  # de-hyphenate line breaks
    s = re.sub(r"[^\w₹%.,;:()/\- ]+", " ", s)        # \w is Unicode-aware: keeps Devanagari, Gujarati...
    s = re.sub(r"[_।]+", " ", s)               # underscores and the Devanagari danda act as spaces
    return re.sub(r"\s+", " ", s).strip()


def _content_len(q: str) -> int:
    return sum(1 for ch in q if ch.isalnum())


@dataclass
class QuoteMatch:
    verified: bool
    segment_id: Optional[str]
    page: Optional[int]
    score: float                    # 100 = exact
    exact: bool = False


def find_quote(quote: str, segments: List[Segment], hint_segment_id: Optional[str] = None) -> QuoteMatch:
    q = normalize(quote)
    if _content_len(q) < MIN_QUOTE_CHARS and len(q.split()) < MIN_QUOTE_WORDS:
        return QuoteMatch(False, hint_segment_id, None, 0.0)

    ordered = list(segments)
    if hint_segment_id:
        ordered.sort(key=lambda s: 0 if s.id == hint_segment_id else 1)

    for seg in ordered:                               # 1) exact (normalised) substring
        if q in normalize(seg.text):
            return QuoteMatch(True, seg.id, seg.page_start, 100.0, exact=True)

    if len(q) < FUZZY_MIN_CHARS:                      # short quotes: exact or nothing
        return QuoteMatch(False, hint_segment_id, None, 0.0)

    best: Optional[QuoteMatch] = None                 # 2) fuzzy partial match for long quotes
    for seg in ordered:
        score = fuzz.partial_ratio(q, normalize(seg.text))
        if score >= FUZZY_THRESHOLD and (best is None or score > best.score):
            best = QuoteMatch(True, seg.id, seg.page_start, float(score))
    return best or QuoteMatch(False, hint_segment_id, None, 0.0)


def locate_by_keywords(keywords: List[str], segments: List[Segment]) -> Optional[Segment]:
    """Best segment containing the most of the given keywords (used to anchor rule findings)."""
    best, best_hits = None, 0
    for seg in segments:
        t = seg.text.lower()
        hits = sum(1 for k in keywords if k.lower() in t)
        if hits > best_hits:
            best, best_hits = seg, hits
    return best
