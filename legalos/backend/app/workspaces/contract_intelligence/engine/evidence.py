"""Locating the exact clause text a deterministic rule is about.

Rules must never fire on a hunch: every presence rule finds the sentence that triggers it, quotes it verbatim
(cut to 300 characters around the match) and records its segment and page. Helpers here also read numbers
written the Indian way ("thirty-six (36) months", "15%", "१८० दिन") and work out which party a sentence binds.
"""
import re
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

from app.workspaces.contract_intelligence.engine.segmenter import Segment

MAX_QUOTE = 300
MIN_SENTENCE_CHARS = 25

# Abbreviations that end with a dot but do not end a sentence ("Rs. 5,000", "Clause No. 4", "i.e. ...").
_ABBREV = re.compile(r"(?:\b(?:rs|no|nos|sr|mr|mrs|ms|dr|viz|ltd|pvt|co|inc|etc|sec|cl|vs|st|i\.e|e\.g|approx|max|min|p\.a|p\.m)\.)$", re.I)
_SENT_END = re.compile(r"(?<=[.;?!।])\s+")


@dataclass
class Evidence:
    segment: Segment
    sentence: str
    quote: str            # verbatim, at most MAX_QUOTE characters
    start: int            # match position inside `sentence`


def sentences(text: str) -> Iterator[str]:
    """Sentences of a clause, keeping lines apart (numbered sub-clauses are on their own lines)."""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        buf = ""
        pos = 0
        for m in _SENT_END.finditer(line):
            piece = line[pos:m.start()]
            buf = f"{buf} {piece}".strip() if buf else piece
            pos = m.end()
            if not _ABBREV.search(buf):
                yield buf
                buf = ""
        tail = line[pos:]
        rest = f"{buf} {tail}".strip() if buf else tail
        if rest:
            yield rest


def quote_around(sentence: str, start: int, end: int) -> str:
    """Verbatim window of at most MAX_QUOTE characters around [start, end), cut at word boundaries."""
    if len(sentence) <= MAX_QUOTE:
        return sentence
    left = max(0, min(start - 100, len(sentence) - MAX_QUOTE))
    right = min(len(sentence), left + MAX_QUOTE)
    if left > 0:
        sp = sentence.find(" ", left)
        left = sp + 1 if 0 <= sp < start else left
    if right < len(sentence):
        sp = sentence.rfind(" ", left, right)
        right = sp if sp > end else right
    return sentence[left:right].strip()


def find_all(segments: Sequence[Segment], pattern: re.Pattern, also: Optional[re.Pattern] = None,
             unless: Optional[re.Pattern] = None) -> Iterator[Evidence]:
    """Every sentence matching `pattern` (and `also`, and not `unless`), in document order."""
    for seg in segments:
        for sent in sentences(seg.text):
            if sum(ch.isalnum() for ch in sent) < MIN_SENTENCE_CHARS:
                continue                  # bare headings ("PRICE AND PAYMENT") are not evidence
            m = pattern.search(sent)
            if not m or (also and not also.search(sent)) or (unless and unless.search(sent)):
                continue
            yield Evidence(seg, sent, quote_around(sent, m.start(), m.end()), m.start())


def find_first(segments: Sequence[Segment], pattern: re.Pattern, also: Optional[re.Pattern] = None,
               unless: Optional[re.Pattern] = None) -> Optional[Evidence]:
    return next(find_all(segments, pattern, also, unless), None)


def mentions(segments: Sequence[Segment], pattern: re.Pattern) -> bool:
    return any(pattern.search(s.text) for s in segments)


# ------------------------------------------------------------------ numbers

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20, "twenty-four": 24, "thirty": 30,
    "thirty-six": 36, "forty-five": 45, "forty-eight": 48, "sixty": 60, "ninety": 90,
    "one hundred and twenty": 120, "one hundred and eighty": 180, "three hundred and sixty-five": 365,
}
NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted((re.escape(w) for w in _WORD_NUMBERS), key=len, reverse=True)) + r")"
_UNIT_DAYS = r"days?|दिन|दिनों"
_UNIT_MONTHS = r"months?|माह|महीने|महीनों|मास"
_UNIT_YEARS = r"years?|वर्ष|वर्षों|साल"
_DURATION = re.compile(rf"\b{NUM}\s*\)?\s*(?:\(\s*\w[\w\s-]*\)\s*)?({_UNIT_DAYS}|{_UNIT_MONTHS}|{_UNIT_YEARS})", re.I)
_PERCENT = re.compile(rf"\b{NUM}\s*\)?\s*(?:%|per\s*cent|percent|प्रतिशत)", re.I)
_PER_MONTH = re.compile(r"^\W{0,3}(?:\([^)]*\)\s*)?(?:per\s+month|a\s+month|p\.?\s?m\.?\b|monthly|per\s+mensem|प्रति\s*(?:माह|मास)|मासिक)", re.I)


def to_number(token: str) -> Optional[float]:
    """'36' / '१८०' / 'thirty-six' -> number; int() understands Devanagari digits."""
    token = token.strip().lower()
    if token in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[token])
    try:
        return float(token)
    except ValueError:
        return None


def _durations(text: str, pattern: re.Pattern = _DURATION) -> Iterator[Tuple[float, str]]:
    """(number, 'd'|'m'|'y') for every duration the pattern finds."""
    for m in pattern.finditer(text):
        n = to_number(m.group(1))
        if n is None:
            continue
        unit = m.group(2)
        kind = "m" if re.fullmatch(_UNIT_MONTHS, unit, re.I) else "y" if re.fullmatch(_UNIT_YEARS, unit, re.I) else "d"
        yield n, kind


def durations_in_days(text: str, pattern: re.Pattern = _DURATION) -> List[float]:
    """Every duration in the text, in days (months = 30, years = 365)."""
    return [n * {"d": 1, "m": 30, "y": 365}[k] for n, k in _durations(text, pattern)]


def durations_in_months(text: str) -> List[float]:
    """Every duration in the text, in months (days / 30, years * 12)."""
    return [round(n * {"d": 1 / 30, "m": 1, "y": 12}[k], 1) for n, k in _durations(text)]


def duration_after(words: str) -> re.Pattern:
    """A duration introduced by one of `words` ('within|after'): '... within one hundred and eighty (180) days'."""
    return re.compile(rf"\b(?:{words})\s+(?:a\s+period\s+of\s+)?{NUM}\s*\)?\s*(?:\(\s*\w[\w\s-]*\)\s*)?"
                      rf"({_UNIT_DAYS}|{_UNIT_MONTHS}|{_UNIT_YEARS})", re.I)


def annual_rates(text: str) -> List[Tuple[float, bool]]:
    """(rate per year in %, was stated monthly) for every percentage in the text."""
    out = []
    for m in _PERCENT.finditer(text):
        n = to_number(m.group(1))
        if n is None:
            continue
        monthly = bool(_PER_MONTH.search(text[m.end():m.end() + 30]))
        out.append((n * 12 if monthly else n, monthly))
    return out


def percents(text: str) -> List[float]:
    return [n for n in (to_number(m.group(1)) for m in _PERCENT.finditer(text)) if n is not None]


def number_pattern(value: float, unit: str = "") -> re.Pattern:
    """Matches a number as written in a contract ('45', '(45)'), optionally followed by a unit regex."""
    n = int(value) if float(value).is_integer() else value
    tail = rf"\s*\)?\s*(?:{unit})" if unit else r"(?![\d])"
    return re.compile(rf"(?<![\d.,]){re.escape(str(n))}{tail}", re.I)


def days_pattern(days: float) -> List[re.Pattern]:
    """'60 days', or the same period written in months ('six (6) months')."""
    out = [number_pattern(days, _UNIT_DAYS)]
    if days >= 30 and days % 30 == 0:
        out.append(number_pattern(days // 30, _UNIT_MONTHS))
    return out

# ------------------------------------------------------------------ who a sentence binds

_GENERIC_ROLE_WORDS = {"party", "the", "of", "and", "first", "second", "other", "one", "part", "m/s", "private",
                       "limited", "ltd", "pvt", "llp", "company", "co", "india", "mr", "ms", "mrs", "shri", "smt"}
_DEFINED_AS = re.compile(
    r"(?:referred\s+to\s+as|called)\s+(?:the\s+)?[\"“'‘]([A-Za-z][A-Za-z .&-]{1,40}?)[\"”'’]"
    r"|\(\s*(?:the\s+|hereinafter\s+)?[\"“'‘]([A-Za-z][A-Za-z .&-]{1,40}?)[\"”'’]",
    re.I)
_MUTUAL = re.compile(r"\b(?:either|each|both|neither|any)\s+part(?:y|ies)\b|\bthe\s+parties\b", re.I)


def defined_term_for(name: str, full_text: str) -> Optional[str]:
    """The defined term a party is given in the preamble ('... Brightpath ... hereinafter the "LICENSEE"')."""
    words = [w for w in re.findall(r"[A-Za-z]{3,}", name) if w.lower() not in _GENERIC_ROLE_WORDS][:2]
    if not words:
        return None
    m = re.search(r"\W+".join(re.escape(w) for w in words), full_text, re.I)
    if not m:
        return None
    d = _DEFINED_AS.search(full_text, m.end(), m.end() + 700)
    term = (d.group(1) or d.group(2)) if d else None
    return term.strip().lower() if term else None


def aliases(name: str, role: str, full_text: str) -> List[str]:
    """Words the contract uses for a party: its role, its defined term and the distinctive part of its name."""
    out = {role.strip().lower()} if role.strip() else set()
    out |= {w for w in re.split(r"[^a-z]+", role.lower()) if len(w) >= 4 and w not in _GENERIC_ROLE_WORDS}
    term = defined_term_for(name, full_text)
    if term:
        out.add(term)
    first = next((w for w in re.findall(r"[A-Za-z]{4,}", name) if w.lower() not in _GENERIC_ROLE_WORDS), None)
    if first:
        out.add(first.lower())
    return sorted((a for a in out if a), key=len, reverse=True)


def last_party_before(sentence: str, pos: int, client: Iterable[str], other: Iterable[str]) -> Optional[str]:
    """'client' / 'other' / 'both': the party named closest before `pos` (the subject of the verb at pos)."""
    window = sentence[max(0, pos - 160):pos].lower()
    best: Tuple[int, Optional[str]] = (-1, None)
    for who, words in (("client", client), ("other", other)):
        for w in words:
            for m in re.finditer(rf"\b{re.escape(w)}\b", window):
                if m.start() > best[0]:
                    best = (m.start(), who)
    mutual = list(_MUTUAL.finditer(window))
    if mutual and mutual[-1].start() > best[0]:
        return "both"
    return best[1]
