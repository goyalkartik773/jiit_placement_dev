"""Shortlist parsing (category SHORTLIST).

Sub-pattern A — named student list plus a selection stage. The stage comes
from the subject, e.g. ``...-Test Selects-Virtual Interview-1 August``,
``Shortlisted Students for 2nd round of interviews``,
``List of Students Shortlisted For Technical Interviews``,
``Updated List of Registered Students``. Specific rounds (test /
assessment / interview / round) beat generic "shortlist" wording, and the
leftmost specific mention wins.

Sub-pattern B — aggregate counts in prose. Corpus examples:

* ``288 Students Not Registered`` (subject) + ``out of 1068 eligible
  students have not yet registered`` (body)
* ``107 students ... have not submitted their updated Gmail ID``
* ``60 students doing registration through the above given link``

Only sentences that carry both a number and a recognised funnel verb become
counts — ``238 students) CL1, CL2`` (a licensing rule) and batch-year noise
like ``2027 students click here to apply`` are skipped, never force-fit.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from placement_pipeline.company import extract_company
from placement_pipeline.models import FunnelCount, Link
from placement_pipeline.normalize import find_sentences_with, strip_markdown
from placement_pipeline.parse_util import dated_facts, links_from

# specific rounds first (label, pattern); the leftmost match wins
_STAGE_RULES: tuple[tuple[str, str], ...] = (
    (r"qualifier\s+round\s*(\d)", None),
    (r"(\d)(?:st|nd|rd|th)?\s+round", None),
    (r"round\s*(\d)", None),
    (r"test\s+selects?", "test selects"),
    (r"online\s+test", "online test"),
    (r"aptitude\s+test", "aptitude test"),
    (r"online\s+assessment", "online assessment"),
    (r"technical\s+interviews?", "technical interview"),
    (r"virtual\s+interviews?", "virtual interview"),
    (r"panel\s+interviews?", "panel interview"),
    (r"\binterviews?\b", "interview"),
    (r"\bassessment\b", "assessment"),
)
_GENERIC_STAGE_RULES: tuple[tuple[str, str], ...] = (
    (
        r"registered?\s+students|consent\s+(?:list|to register)|"
        r"(?:complete\s+)?registration",
        "registration",
    ),
    (r"selection\s+status", "selection status"),
    (r"shortlist\w*", "shortlist"),
    (r"\blist\b", "list"),
)

_FUNNEL_VERBS = (
    r"(?:have|has|had|will|would|can|being|being|doing|to\s+do|are)?\s*"
    r"(?:not\s+yet\s+|not\s+)?"
    r"(?:registered|submitted|applied|appeared|shortlisted|selected|qualified|"
    r"attended|participated|volunteered|consented|opted|updated|reported|"
    r"chosen|recruited|hired|cleared|invited|rejected|waitlisted|registration)"
)

_YEAR_COUNTS = {2024, 2025, 2026, 2027, 2028, 2029, 2030}


def _stage_from_subject(subject: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", subject or "").strip()
    if not text:
        return None
    best: tuple[int, str] | None = None
    for pattern, fixed in _STAGE_RULES:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            label = _label_for(m, fixed)
            if best is None or m.start() < best[0]:
                best = (m.start(), label)
            break  # leftmost per rule is enough; rules are specific-first
    if best is None:
        for pattern, fixed in _GENERIC_STAGE_RULES:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return _label_for(m, fixed)
        return None
    return best[1]


def _label_for(m: re.Match[str], fixed: Optional[str]) -> str:
    if fixed:
        return fixed
    matched = re.sub(r"\s+", " ", m.group(0).lower()).strip()
    if re.fullmatch(r"\d(?:st|nd|rd|th)?\s+round", matched):
        digit = re.match(r"\d", matched).group(0)
        return f"round {digit}"
    if matched.startswith("qualifier"):
        return matched
    return matched


def _funnel_counts(subject: str, text: str) -> list[FunnelCount]:
    """Number + funnel-verb sentences (subject line counts too)."""
    seen: set[tuple[int, str]] = set()
    counts: list[FunnelCount] = []
    sentences = find_sentences_with(
        text, r"\b\d{1,4}\s+(?:eligible\s+|successful\s+|registered\s+)?"
        r"(?:students|candidates|aspirants)\b"
    )
    # the subject often carries the headline count ("288 Students Not Registered")
    sentences = [re.sub(r"\s+", " ", subject)] + sentences

    count_re = re.compile(
        r"\b(?P<count>\d{1,4})\s+(?P<qual>eligible\s+|successful\s+)?"
        r"(?:students|candidates|aspirants)\b",
        re.IGNORECASE,
    )
    for sent in sentences:
        m = count_re.search(sent)
        if not m:
            continue
        count = int(m.group("count"))
        if count in _YEAR_COUNTS:
            continue
        after = sent[m.end() :]
        vm = re.search(_FUNNEL_VERBS, after, re.IGNORECASE)
        if not vm:
            continue  # no funnel verb -> it is not a funnel count
        stage = re.sub(r"\s+", " ", vm.group(0)).strip().lower()
        stage = re.sub(r"^(?:have|has|had|will|would|can|are|is|to|being)\s+", "", stage)
        stage = stage.strip(" ,.;:-")
        key = (count, stage)
        if key in seen:
            continue
        seen.add(key)
        counts.append(
            FunnelCount(
                stage=stage or "mentioned",
                count=count,
                qualifier=(m.group("qual") or "").strip().lower(),
                sentence=sent[:300],
            )
        )
        if len(counts) >= 10:
            break
    return counts


def parse_shortlist(
    subject: str,
    body: str,
    *,
    reference: Optional[datetime] = None,
    students: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Extract shortlist facts (stage, dates, funnel counts, links)."""
    text = strip_markdown(body or "")
    out: dict[str, Any] = {"warnings": []}

    company_raw, company = extract_company(subject, text)
    out["company_raw"] = company_raw
    out["company"] = company
    if not company:
        out["warnings"].append("company not identified")

    out["stage"] = _stage_from_subject(subject)

    dated, deadline = dated_facts(text, reference)
    out["deadline"] = deadline
    out["interview_dates"] = dated
    out["funnel_counts"] = _funnel_counts(subject, text)
    out["links"] = [Link(url=u, label=lbl) for u, lbl in links_from(text)]

    if not out["funnel_counts"] and not (students or []):
        # honest: some SHORTLIST mails are pure logistics prose
        out["warnings"].append("no student rows and no funnel counts")
    return out
