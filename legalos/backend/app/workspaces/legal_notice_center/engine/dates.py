"""Deterministic reading of dates and time periods in Indian notices (English, Hindi, Marathi, Gujarati).

Why this exists: the AI returns ISO dates, but Indian notices write "12.10.2026", "12-10-26", "12th October 2026",
"30 अक्टूबर 2026" or "૩૦ ઓક્ટોબર". The verified deadline quote is re-read here so a model slip (for example a
day/month swap on 12.10.2026) is caught and corrected from the notice's own words. Indian dates are always
day-first; nothing here guesses a month-first reading.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

# Devanagari and Gujarati digits -> ASCII (the same mapping is used for quote verification)
NATIVE_DIGITS = str.maketrans("०१२३४५६७८९૦૧૨૩૪૫૬૭૮૯", "01234567890123456789")
_NUKTA = "़"

_MONTHS = {
    1: ["january", "jan", "जनवरी", "जानेवारी", "જાન્યુઆરી"],
    2: ["february", "feb", "फरवरी", "फेब्रुवारी", "ફેબ્રુઆરી"],
    3: ["march", "mar", "मार्च", "માર્ચ"],
    4: ["april", "apr", "अप्रैल", "अप्रेल", "एप्रिल", "એપ્રિલ"],
    5: ["may", "मई", "मे", "મે"],
    6: ["june", "jun", "जून", "જૂન", "જુન"],
    7: ["july", "jul", "जुलाई", "जुलै", "જુલાઈ", "જુલાઇ"],
    8: ["august", "aug", "अगस्त", "ऑगस्ट", "ઓગસ્ટ", "ઑગસ્ટ"],
    9: ["september", "sept", "sep", "सितंबर", "सितम्बर", "सप्टेंबर", "સપ્ટેમ્બર"],
    10: ["october", "oct", "अक्टूबर", "अक्तूबर", "ऑक्टोबर", "ઓક્ટોબર", "ઑક્ટોબર"],
    11: ["november", "nov", "नवंबर", "नवम्बर", "नोव्हेंबर", "નવેમ્બર"],
    12: ["december", "dec", "दिसंबर", "दिसम्बर", "डिसेंबर", "ડિસેમ્બર"],
}
_MONTH_OF = {name: num for num, names in _MONTHS.items() for name in names}
_MONTH_ALT = "|".join(sorted((re.escape(n) for n in _MONTH_OF), key=len, reverse=True))
_MONTH = rf"(?<![A-Za-z])(?P<mon>{_MONTH_ALT})(?![a-z])\.?"
_ORD = r"(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>\d{4})"

_NUMERIC = re.compile(r"(?<!\d)(?P<d>\d{1,2})\s?[./-]\s?(?P<m>\d{1,2})\s?[./-]\s?(?P<y>\d{4}|\d{2})(?!\d)")
_ISO = re.compile(r"(?<!\d)(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?!\d)")
_DAY_MONTH = re.compile(rf"(?<!\d)(?P<d>\d{{1,2}}){_ORD}\s*(?:day\s+of\s+)?{_MONTH}[\s,]*(?:{_YEAR})?", re.I)
_MONTH_DAY = re.compile(rf"{_MONTH}\s+(?P<d>\d{{1,2}}){_ORD},?\s*(?:{_YEAR})?", re.I)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fourteen": 14, "fifteen": 15, "twenty": 20, "twenty-one": 21, "twenty one": 21, "thirty": 30,
    "forty-five": 45, "forty five": 45, "sixty": 60, "ninety": 90,
    "तीन": 3, "सात": 7, "दस": 10, "दहा": 10, "चौदह": 14, "पंद्रह": 15, "पन्द्रह": 15, "पंधरा": 15, "इक्कीस": 21,
    "तीस": 30, "पैंतालीस": 45, "साठ": 60, "नब्बे": 90,
    "સાત": 7, "દસ": 10, "પંદર": 15, "ત્રીસ": 30, "સાઠ": 60,
}
_NUMBER_WORD_RX = re.compile(
    "(?<![A-Za-z])(?:" + "|".join(sorted((re.escape(w) for w in _NUMBER_WORDS), key=len, reverse=True)) + ")(?![A-Za-z])", re.I)
_UNIT = re.compile(
    r"(?<![A-Za-z])(?P<unit>working\s+days?|clear\s+days?|days?|months?|कार्य\s*दिवस|कामकाजी\s*दिन|दिनों|दिन(?!ांक)|दिवसांच्या|"
    r"दिवसां|दिवस|महीनों|महीने|महिने|माह|દિવસ|મહિના)(?![a-z])", re.I)
_RECEIPT = re.compile(r"receipt|received|service|served|प्राप्ति|प्राप्त|मिलने|मिळाल|મળ્ય|પ્રાપ્ત", re.I)
_NOTICE_DATE = re.compile(r"date\s+(?:of\s+)?(?:this\s+notice|hereof|of\s+issue)|issue\s+of\s+(?:this|the)\s+notice|from\s+the\s+date\s+of\s+(?:this|the)\s+(?:notice|letter)|"
                          r"इस\s+(?:नोटिस|सूचना)\s+की\s+(?:तारीख|दिनांक)|नोटीसच्या\s+तारखे|નોટિસની\s+તારીખ", re.I)
_FORTHWITH = re.compile(r"forthwith|immediately|at\s+once|without\s+(?:any\s+)?delay|तुरंत|तत्काल|ताबडतोब|त्वरित|તાત્કાલિક|તરત", re.I)


def canon(text: str) -> str:
    """NFC, ASCII digits, no nukta: the form every pattern here is written against."""
    return unicodedata.normalize("NFC", text or "").translate(NATIVE_DIGITS).replace(_NUKTA, "")


def _year(raw: Optional[str], ref: Optional[date], day: int, month: int) -> Optional[int]:
    if raw:
        y = int(raw)
        return 2000 + y if y < 100 else y
    if ref is None:
        return None
    # "by 30 October": the next such date on or after the reference (notice / receipt) date
    try:
        return ref.year if date(ref.year, month, day) >= ref else ref.year + 1
    except ValueError:
        return ref.year


def _make(day: int, month: int, year: Optional[int]) -> Optional[date]:
    if year is None or not 1990 <= year <= 2100:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_dates(text: str, ref: Optional[date] = None) -> List[date]:
    """Every calendar date written in `text`, in order of appearance (day-first, Indian style).

    `ref` resolves a missing year ("by 30 October"); without it such dates are skipped, never guessed."""
    s = canon(text)
    found: List[tuple[int, date]] = []
    taken: List[range] = []

    def add(m: re.Match, d: Optional[date]) -> None:
        if d and not any(m.start() in r for r in taken):
            found.append((m.start(), d))
            taken.append(range(m.start(), m.end()))

    for m in _ISO.finditer(s):
        add(m, _make(int(m["d"]), int(m["m"]), int(m["y"])))
    for m in _NUMERIC.finditer(s):
        day, month = int(m["d"]), int(m["m"])
        add(m, _make(day, month, _year(m["y"], ref, day, month)) if 1 <= month <= 12 else None)
    for rx in (_DAY_MONTH, _MONTH_DAY):
        for m in rx.finditer(s):
            day, month = int(m["d"]), _MONTH_OF[m["mon"].lower().rstrip(".")]
            add(m, _make(day, month, _year(m["year"], ref, day, month)))
    return [d for _, d in sorted(found, key=lambda x: x[0])]


@dataclass(frozen=True)
class Period:
    count: int
    unit: str          # days | working_days | months


def _unit_name(raw: str) -> str:
    r = raw.lower()
    if r.startswith("working") or "कार्य" in r or "कामकाजी" in r:
        return "working_days"
    if r.startswith("month") or any(k in r for k in ("मही", "महि", "माह", "મહિના")):
        return "months"
    return "days"


def find_period(text: str) -> Optional[Period]:
    """The first "N days / N working days / N months" period in `text` ("fifteen (15) days", "15 दिन", "૧૫ દિવસ")."""
    s = canon(text)
    for m in _UNIT.finditer(s):
        before = s[max(0, m.start() - 40):m.start()]
        digits = re.findall(r"(?<![\d.,/-])(\d{1,3})(?![A-Za-z\d])(?![.,/-]\d)", before)   # not part of 2026, 2,40,000, 25F
        count = int(digits[-1]) if digits else None
        if count is None:
            hits = [(w.start(), _NUMBER_WORDS[w.group(0).lower()]) for w in _NUMBER_WORD_RX.finditer(before)]
            count = max(hits)[1] if hits else None
        if count:
            return Period(count, _unit_name(m["unit"]))
    return None


def period_anchor(text: str) -> Optional[str]:
    """What a period counts from, as the notice words it: 'receipt' | 'notice_date' | None (not said)."""
    s = canon(text)
    if _RECEIPT.search(s):
        return "receipt"
    if _NOTICE_DATE.search(s):
        return "notice_date"
    return None


def says_forthwith(text: str) -> bool:
    return bool(_FORTHWITH.search(canon(text)))
