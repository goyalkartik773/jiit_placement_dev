"""Date extraction: raw RFC receive dates + structured dates from free text.

Corpus date styles observed:

* ``10 Aug 2026`` / ``10th August 2026`` / ``08 August 2026`` / ``14th April, 2026``
* ``8:30 AM on 10 Aug 2026`` / ``by 11 AM, 24 August 2026`` / ``4.30 PM``
* ``11 & 12 March 2026`` (ranges), ``5 & 6 February at JIIT``
* ``June 2027 and onwards`` (month-year only), ``25th June 2026 (Thursday)``
* typos such as ``Ist May`` (1st) and ``22 Augsut``
* receive dates as RFC-822 text with trailing tz names: ``-0800 (PST)``
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from placement_pipeline.config import MONTHS
from placement_pipeline.models import DateFact

# Common misspellings seen in the corpus.
_MONTH_TYPOS = {
    "augsut": "august",
    "agust": "august",
    "septmber": "september",
    "febuary": "february",
    "juen": "june",
    "julyy": "july",
    "october": "october",
}

_MONTH_PATTERN = "|".join(
    sorted({k for k in MONTHS} | set(_MONTH_TYPOS), key=len, reverse=True)
)

_ORD = r"(?:st|nd|rd|th)?"

# day month year  (10 Aug 2026 | 10th August 2026 | Ist May 2026)
_DMY_RE = re.compile(
    rf"\b(?P<day>\d{{1,2}}(?:st|nd|rd|th)?|Ist)\s+"
    rf"(?P<month>{_MONTH_PATTERN})\.?,?\s+(?P<year>20\d{{2}})\b",
    re.IGNORECASE,
)

# month day, year  (August 24, 2026 | Aug 10 2026)
_MDY_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+(?P<day>\d{{1,2}}){_ORD},?\s+(?P<year>20\d{{2}})\b",
    re.IGNORECASE,
)

# day range: "11 & 12 March 2026", "17 and 18 August 2026", "5 & 6 February
# at JIIT" (the year may be absent — resolved from the receive date)
_RANGE_RE = re.compile(
    rf"\b(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:&|and|to|-|–|—)\s*"
    rf"(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+"
    rf"(?P<month>{_MONTH_PATTERN})\.?,?(?:\s+(?P<year>20\d{{2}}))?\b",
    re.IGNORECASE,
)

# day month with no year ("the registration window will close on 6 September
# at 10:00 PM") — corpus mail is same-year mail, so the receive year applies
_DMY_NY_RE = re.compile(
    rf"\b(?P<day>\d{{1,2}}(?:st|nd|rd|th)?|Ist)\s+"
    rf"(?P<month>{_MONTH_PATTERN})\.?,?(?!\s*(?:19|20)\d{{2}})",
    re.IGNORECASE,
)

# month year only (June 2027)
_MY_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+(?P<year>20\d{{2}})\b", re.IGNORECASE
)

_TIME_RE = re.compile(
    r"\b(?P<hour>\d{1,2})[:.](?P<minute>\d{2})\s*(?P<ampm>[APap][Mm])\b"
    r"|\b(?P<hour2>\d{1,2})\s*(?P<ampm2>[APap][Mm])\b"
)

# Role rules are checked in order: specific logistics first, deadline last
# (deadline phrasing such as "by" / "from" is otherwise far too greedy).
_ROLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("reporting", ("report", "reporting", "sharp ", "be on time", "reach by")),
    ("joining", ("joining", "join from", "onboard", "tenure", "internship from",
                 "internship tenure", "start date", "joining / ")),
    ("interview", ("interview", "gd round", "pi round", "technical round", "personal interview")),
    ("test", ("online test", "assessment", "aptitude", "exam", "test on", "test trigger",
              "qualifier round", "scheduled on")),
    ("event", ("webinar", "session", "guest lecture", "workshop", "event", "talk",
               "seminar", "quiz", "challenge", "hackathon", "kick-off", "date:")),
    ("deadline", (
        "deadline", "apply by", "register by", "register before", "register at",
        "submit by", "volunteer by", "participate by", "revert mail", "last date",
        "closes on", "close on", "window will close", "extended until", "until",
        "upto", "eod", "consent at", "registration window", "registration link",
        "must register", "link is open",
    )),
]

_DEADLINE_BY_TIME_RE = re.compile(
    r"\b(?:by|before|until|upto|up to)\b[^.!?]{0,60}\d{1,2}[:.]?\d{0,2}\s*(?:a\.?p\.?m\.?|p\.?m\.?|am|pm)\b",
    re.IGNORECASE,
)


#: All corpus mail is Indian-college mail; normalize receive timestamps to IST
#: (naive) so dedup time-windows compare wall-clock consistently.
_IST = timezone(timedelta(hours=5, minutes=30))


def parse_received(raw: str) -> Optional[datetime]:
    """Parse an RFC-822 date string such as ``Fri, 1 Aug 2025 10:59:11 +0530``
    or ``Mon, 19 Jan 2026 20:49:46 -0800 (PST)`` and return naive IST."""
    if not raw:
        return None
    text = re.sub(r"\s*\([A-Za-z]{2,6}\)\s*$", "", raw.strip())
    text = re.sub(r"\s{2,}", " ", text)
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_IST).replace(tzinfo=None)
    return dt


def _month_num(name: str) -> Optional[int]:
    key = name.lower().rstrip(".")
    key = _MONTH_TYPOS.get(key, key)
    return MONTHS.get(key)


def _ordinal_to_int(token: str) -> Optional[int]:
    token = token.strip().lower()
    if token == "ist":  # corpus typo for "1st"
        return 1
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", token)
    if not m:
        return None
    return int(m.group(1))


def _role_for(context: str) -> str:
    low = context.lower()
    if re.search(r"\bas\s+(?:on|of)\b", low):
        # a snapshot date, not a schedule: "…status of pending Interviews
        # as on 24 June 2026" must never become an interview date
        return "mention"
    for role, keys in _ROLE_RULES:
        if any(k in low for k in keys):
            return role
    return "mention"


_SENTENCE_END_RE = re.compile(r"[.!?]+(?=\s)")
_PARA_BREAK_RE = re.compile(r"\r?\n[ \t]*\r?\n")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Spans of the sentence/paragraph containing each date.

    Role words must share the *segment* with the date: "…Internship
    (July–December 2026): Campus Update" must not inherit "assessment"
    from the next paragraph, and "…invited for interviews. … apply by 11 AM,
    08 Aug 2026" must stay a deadline. Boundaries are sentence ends and
    blank lines (the corpus often omits terminal punctuation); dotted
    abbreviations ("Aug.", "e.g.", "PM.") never end a sentence — a skipped
    boundary only widens the context, which is the safe direction.
    """
    cuts: list[tuple[int, int]] = []  # (end of segment, start of next)
    for m in _SENTENCE_END_RE.finditer(text):
        if m.end() >= len(text):
            continue
        if m.group(0).startswith("."):
            j = m.start() - 1
            while j >= 0 and text[j].isalpha():
                j -= 1
            word = text[j + 1 : m.start()]
            if 0 < len(word) <= 3:  # "Aug." / "e.g." / "PM."
                continue
        cuts.append((m.start(), m.end()))
    for m in _PARA_BREAK_RE.finditer(text):
        cuts.append((m.start(), m.end()))
    cuts.sort()

    spans: list[tuple[int, int]] = []
    start = 0
    for cut_end, next_start in cuts:
        if cut_end <= start:
            continue
        spans.append((start, cut_end))
        start = next_start
    spans.append((start, len(text)))
    return spans


def _find_time(context: str) -> Optional[tuple[int, int]]:
    m = _TIME_RE.search(context)
    if not m:
        return None
    hour = int(m.group("hour") or m.group("hour2"))
    minute = int(m.group("minute") or 0)
    ampm = (m.group("ampm") or m.group("ampm2") or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def extract_dates(text: str, *, reference: Optional[datetime] = None) -> list[DateFact]:
    """Extract dated mentions from ``text``.

    ``reference`` (usually the email's receive date) resolves yearless
    day-month mentions and month-year-only mentions and keeps sanity
    bounds. Time-of-day is attached when a clock time sits next to the
    date; the role of a date comes from the sentence/paragraph it sits in
    (never from a neighbouring paragraph).
    """
    facts: list[DateFact] = []
    seen: set[tuple[int, int, int, str]] = set()
    segments = _sentence_spans(text)

    def _segment_for(span: tuple[int, int]) -> str:
        for s, e in segments:
            if s <= span[0] < e:
                return text[s:e]
        return text[span[0] : span[1]]

    def _add(year: int, month: int, day: int, raw: str, span: tuple[int, int]) -> None:
        try:
            when = datetime(year, month, day)
        except ValueError:
            return
        context = _segment_for(span)
        role = _role_for(context)
        clock = _find_time(context)
        if clock:
            when = when.replace(hour=clock[0], minute=clock[1])
        key = (when.year, when.month, when.day, role)
        if key in seen:
            return
        seen.add(key)
        facts.append(DateFact(when=when, role=role, raw=raw.strip()))

    # day ranges first ("11 & 12 March 2026") — each day becomes its own fact
    range_spans: list[tuple[int, int]] = []
    for m in _RANGE_RE.finditer(text):
        month = _month_num(m.group("month"))
        year = int(m.group("year")) if m.group("year") else None
        if month is None:
            continue
        if year is None:
            if reference is None:
                continue  # yearless range without a receive date: skip honestly
            year = reference.year
        range_spans.append(m.span())
        for day_token in (m.group("d1"), m.group("d2")):
            day = int(day_token)
            if day > 31:
                continue
            _add(year, month, day, m.group(0), m.span())

    def _in_range(span: tuple[int, int]) -> bool:
        return any(s <= span[0] < e for s, e in range_spans)

    for regex in (_DMY_RE, _MDY_RE):
        for m in regex.finditer(text):
            if _in_range(m.span()):
                continue
            day = _ordinal_to_int(m.group("day"))
            month = _month_num(m.group("month"))
            if day is None or month is None:
                continue
            _add(int(m.group("year")), month, day, m.group(0), m.span())

    # day month with no year: corpus mail states same-year deadlines
    # ("close on 6 September at 10:00 PM") — the receive date supplies it
    if reference is not None:
        for m in _DMY_NY_RE.finditer(text):
            if _in_range(m.span()):
                continue
            day = _ordinal_to_int(m.group("day"))
            month = _month_num(m.group("month"))
            if day is None or month is None:
                continue
            if any(
                f.when.year == reference.year
                and f.when.month == month
                and f.when.day == day
                for f in facts
            ):
                continue
            _add(reference.year, month, day, m.group(0), m.span())

    # month-year only (never overrides a concrete day-date already found)
    concrete = {(f.when.year, f.when.month, f.when.day) for f in facts}
    for m in _MY_RE.finditer(text):
        month = _month_num(m.group("month"))
        if month is None:
            continue
        year = int(m.group("year"))
        if (year, month, 1) in concrete:
            continue
        # skip when a concrete day already exists in this month
        if any(f.when.year == year and f.when.month == month for f in facts):
            continue
        _add(year, month, 1, m.group(0), m.span())

    facts.sort(key=lambda f: f.when)
    return facts


def primary_date(facts: list[DateFact], role: str) -> Optional[DateFact]:
    for f in facts:
        if f.role == role:
            return f
    return None


def deadline_from(facts: list[DateFact]) -> Optional[DateFact]:
    """Pick the deadline date; among several, the latest wins (deadlines get
    extended). Strict: only dates whose context looked like a deadline count."""
    candidates = [f for f in facts if f.role == "deadline"]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.when)


def within_days(a: datetime, b: datetime, days: int) -> bool:
    return abs(a - b) <= timedelta(days=days)
