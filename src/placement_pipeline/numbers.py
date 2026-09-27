"""Money parsing for Indian placement emails.

Observed formats:

* ``INR 46,38,000`` / ``₹46,38,000`` — absolute totals (Indian grouping)
* ``INR 21 LPA`` / ``21 LPA`` — lakhs per annum
* ``INR 5.00 Lakhs`` / ``4 Lakhs`` / ``₹6.00 Lacs`` — lakh totals
* ``INR 1,10,000 PM for six months`` / ``30,000 per month`` — monthly
* ``INR 75,000 joining bonus`` / ``1 lakh joining bonus`` — bonus
* corpus quirks: ``INR INR 7.30 Lakhs`` (doubled prefix),
  ``INR 14,20,600 Lakhs`` (value is a total despite the trailing word)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LAKH = 100_000

_NUMBER = r"(?:\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"

_MONEY_RE = re.compile(
    rf"(?P<currency>INR|Rs\.?|₹|INR\s+INR)\s*:?\s*(?P<amount>{_NUMBER})"
    rf"(?P<unit>\s*(?:LPA|Lakhs?|Lacs?)\b)?"
    rf"(?P<suffix>\s*(?:PM|per\s+month|a\s+month)\b)?",
    re.IGNORECASE,
)

# bare number followed by LPA / Lakhs without currency prefix
_BARE_UNIT_RE = re.compile(
    rf"(?<![\d,])(?P<amount>{_NUMBER})\s*(?P<unit>LPA|Lakhs?|Lacs?)\b",
    re.IGNORECASE,
)

# "30,000 per month" / "1,10,000 PM for six months" / "per annum"
_MONTHLY_RE = re.compile(
    rf"(?P<amount>{_NUMBER})\s*(?:PM|per\s+month|a\s+month)\b",
    re.IGNORECASE,
)

_BONUS_RE = re.compile(
    rf"(?P<amount>{_NUMBER})\s*(?P<unit>lakh|lakhs)?\s*(?:join(ing)?\s+bonus|sign-on)",
    re.IGNORECASE,
)

_MONEY_CONTEXT_RE = re.compile(
    r"(?i)\b(salary|package|ctc|compensation|stipend|bonus|lpa|lakh|lacs|"
    r"per\s+month|offer(?:ed)?|remuneration|pay|ctc)\b|₹|INR|Rs\.?"
)

_LABELLED_LINE_RE = re.compile(
    r"^(?P<label>[^:\n]{2,60}):\s*(?P<value>.+)$"
)
# a heading alone on its line: "Salary Package:" / "Relocation Perks:"
_LABEL_ONLY_RE = re.compile(r"^(?P<label>[^:\n]{2,60}):[ \t]*$")


@dataclass
class MoneyFact:
    raw: str
    value: int            # rupees (already scaled; monthly for basis="month")
    basis: str            # total | lpa | lakh | month | bonus
    label: str = ""       # surrounding label, e.g. "Salary Package"

    @property
    def per_annum(self) -> int | None:
        if self.basis == "month":
            return self.value * 12
        if self.basis in {"total", "lpa", "lakh", "bonus"}:
            return self.value
        return None


def _to_int(amount: str) -> float:
    return float(amount.replace(",", ""))


def _rupees(num: float) -> int:
    return int(round(num))


def _unit_basis(unit: str | None, amount: str, trailing_word: str = "") -> str:
    has_comma = "," in amount
    if unit and re.search(r"(?i)LPA", unit):
        return "lpa"
    if unit and re.search(r"(?i)Lakh|Lac", unit):
        # "14,20,600 Lakhs" is really a full total, not 14,20,600 lakhs
        return "total" if has_comma else "lakh"
    if has_comma:
        return "total"
    if re.search(r"(?i)Lakh|Lac|LPA", trailing_word):
        return "lakh" if not re.search(r"(?i)LPA", trailing_word) else "lpa"
    return "total"


def extract_money(text: str) -> list[MoneyFact]:
    """Extract money mentions that sit in a money-ish context.

    Lines are matched individually so a label can be attached. A labelled
    line with no amount on it (``Salary Package:``) is a *heading*: it
    labels the money lines below it until the next heading (observed:
    ``Salary Package:`` + ``UG Candidates: INR 6.04 Lakhs``, while the
    later ``Relocation Perks:`` heading keeps its own amounts out of the
    salary pool). Bare numbers never in money context are skipped.
    """
    facts: list[MoneyFact] = []
    seen: set[tuple[int, str]] = set()

    def _add(fact: MoneyFact) -> None:
        key = (fact.value, fact.basis)
        if key not in seen:
            seen.add(key)
            facts.append(fact)

    pending = ""  # current heading label (its line carried no amount)
    lines = text.split("\n")
    for line in lines:
        flat_line = re.sub(r"\s+", " ", line).strip()
        if not flat_line:
            continue
        label = pending
        lm = _LABELLED_LINE_RE.match(flat_line)
        lonly = _LABEL_ONLY_RE.match(flat_line)
        search_line = flat_line
        if lm:
            inner = lm.group("label").strip()
            if _MONEY_CONTEXT_RE.search(inner):
                label = inner
                search_line = lm.group("value")
            if not _MONEY_RE.search(search_line):
                pending = inner  # heading line — owns the amounts below
        elif lonly:
            pending = lonly.group("label").strip()
        elif not _MONEY_CONTEXT_RE.search(flat_line):
            continue

        for m in _MONEY_RE.finditer(search_line):
            amount = m.group("amount")
            unit = m.group("unit")
            suffix = m.group("suffix")
            # trailing words after the number help disambiguate basis
            tail = search_line[m.end() : m.end() + 20]
            num = _to_int(amount)
            if suffix:
                if num < 1000:  # clock-like guards ("10 PM")
                    continue
                fact = MoneyFact(raw=m.group(0).strip(), value=_rupees(num),
                                 basis="month", label=label)
            else:
                basis = _unit_basis(unit, amount, tail)
                value = num * _LAKH if basis in {"lpa", "lakh"} else num
                fact = MoneyFact(raw=m.group(0).strip(), value=_rupees(value),
                                 basis=basis, label=label)
            _add(fact)

        # bare amounts with units inside a money-context line: "21 LPA", "4 Lakhs"
        for m in _BARE_UNIT_RE.finditer(search_line):
            unit = m.group("unit")
            amount = m.group("amount")
            basis = _unit_basis(unit, amount)
            num = _to_int(amount)
            value = num * _LAKH if basis in {"lpa", "lakh"} else num
            _add(MoneyFact(raw=m.group(0).strip(), value=_rupees(value),
                           basis=basis, label=label))

        # monthly amounts without currency prefix: "Stipend: 30,000 per month"
        for m in _MONTHLY_RE.finditer(search_line):
            num = _to_int(m.group("amount"))
            if num < 1000:  # guard against clock-like matches
                continue
            _add(MoneyFact(raw=m.group(0).strip(), value=_rupees(num),
                           basis="month", label=label))

        for m in _BONUS_RE.finditer(search_line):
            num = _to_int(m.group("amount"))
            unit = (m.group("unit") or "").lower()
            if unit.startswith("lakh"):
                num *= _LAKH
            _add(MoneyFact(raw=m.group(0).strip(), value=_rupees(num),
                           basis="bonus", label=label))

    return facts


def pick_package(facts: list[MoneyFact]) -> MoneyFact | None:
    """Prefer a labelled 'Salary Package'/'CTC' total, else the largest total
    or LPA figure (packages dominate perks/bonuses)."""
    if not facts:
        return None
    labelled = [
        f for f in facts
        if f.label and re.search(r"(?i)salary|package|ctc|compensation", f.label)
    ]
    pool = labelled or facts
    totals = [f for f in pool if f.basis in {"total", "lpa", "lakh"}]
    if not totals:
        # a labelled pool with only monthly/bonus facts must not hide the
        # actual package stated elsewhere in the body
        totals = [f for f in facts if f.basis in {"total", "lpa", "lakh"}]
    if not totals:
        return None
    return max(totals, key=lambda f: (f.per_annum or 0))


def pick_stipend(facts: list[MoneyFact]) -> MoneyFact | None:
    for f in facts:
        if f.basis == "month":
            return f
        if f.label and re.search(r"(?i)stipend", f.label):
            return f
    return None
