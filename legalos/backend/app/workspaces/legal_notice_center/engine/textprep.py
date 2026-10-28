"""Getting a notice's text into a clean, verifiable form.

- clean_notice_text: Unicode NFC (so Hindi typed on different keyboards compares equal), invisible marks removed, and
  WhatsApp export noise ("[12/10/26, 9:41 PM] Ramesh: ", "<Media omitted>", *bold*) stripped when the text is a chat paste.
  The cleaned text is what we store and show, so highlighted quotes always line up with it.
- verify_quote: the shared find_quote check, applied after the same Unicode canonicalisation on both sides (NFC,
  zero-width joiners dropped, Devanagari/Gujarati digits as ASCII) so a verbatim Hindi quote verifies even when the
  model's copy differs from the notice only in invisible encoding.
"""
import re
import unicodedata
from typing import List, Tuple

from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.contract_intelligence.engine.segmenter import Segment
from app.workspaces.legal_notice_center.engine.dates import NATIVE_DIGITS

# Removed from stored text: never meaningful in a notice. (ZWJ / ZWNJ are kept in storage: they shape Indic conjuncts.)
_INVISIBLE = dict.fromkeys(map(ord, "​‎‏‪‫‬‭‮⁦⁧⁨⁩﻿­"), None)
_JOINERS = dict.fromkeys(map(ord, "‌‍"), None)

_WA_PREFIX = re.compile(
    r"^\s*\[?\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[apAP]\.?\s?[mM]\.?)?\]?\s*(?:-\s*)?"
    r"(?:[^:\n]{1,40}:\s)?")
_WA_SYSTEM = re.compile(
    r"^\s*(?:<?media omitted>?|<attached:[^>]*>|image omitted|document omitted|this message was deleted|you deleted this message|"
    r"messages and calls are end-to-end encrypted.*|forwarded|forwarded many times|<this message was edited>|null)\s*$", re.I)
_WA_BOLD = re.compile(r"(?<![\w*])\*(\S(?:[^*\n]*\S)?)\*(?![\w*])")
_WA_STRIKE = re.compile(r"(?<![\w~])~(\S(?:[^~\n]*\S)?)~(?![\w~])")


def _looks_like_chat(lines: List[str]) -> bool:
    hits = sum(1 for ln in lines if ln.strip() and _WA_PREFIX.match(ln) and _WA_PREFIX.match(ln).end() > 8)
    return hits >= 2 and hits >= 0.2 * sum(1 for ln in lines if ln.strip())


def clean_notice_text(text: str) -> Tuple[str, bool]:
    """-> (clean text, whether chat-export noise was removed)."""
    t = unicodedata.normalize("NFC", text or "").translate(_INVISIBLE).replace("\r\n", "\n").replace("\r", "\n")
    lines = t.split("\n")
    chat = _looks_like_chat(lines)
    if chat:
        kept = []
        for ln in lines:
            m = _WA_PREFIX.match(ln)
            ln = ln[m.end():] if m and m.end() > 8 else ln
            if not _WA_SYSTEM.match(ln):
                kept.append(_WA_STRIKE.sub(r"\1", _WA_BOLD.sub(r"\1", ln)).rstrip())
        lines = kept
    t = "\n".join(ln.rstrip() for ln in lines)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip(), chat


def canon_for_match(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").translate(_INVISIBLE).translate(_JOINERS).translate(NATIVE_DIGITS)


def notice_segments(text: str) -> List[Segment]:
    """The whole notice as one searchable segment: notices are short, and a quote may cross a numbered paragraph."""
    return [Segment("S1", None, "", canon_for_match(text), 1, 1)]


def _numbers(s: str) -> set:
    return set(re.findall(r"\d+", re.sub(r"(?<=\d),(?=\d)", "", s)))


def verify_quote(quote: str, segments: List[Segment]) -> bool:
    """find_quote, plus: every number in the quote must occur in the notice.

    The fuzzy fallback tolerates OCR noise, but for Indic scripts the shared normaliser drops vowel signs, so two different
    sentences can look alike; a quote with a different amount, period or date must never pass as verified."""
    if not (quote and quote.strip()):
        return False
    q = canon_for_match(quote)
    if not verify.find_quote(q, segments).verified:
        return False
    return _numbers(q) <= set().union(*(_numbers(s.text) for s in segments))
