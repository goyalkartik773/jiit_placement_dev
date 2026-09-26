"""Opportunity parsing (category OPPORTUNITY).

Corpus examples:

* Flipkart GRiD 8.0 — contest, deadline ``05 PM, 03 July 2026`` (subject +
  ``consent at the link given below by 05 PM, 03 July 2026``), eligibility
  ``Eligible Degrees: B.Tech, M.Tech, Integrated - CSE-IT-ECE...``,
  stages ``Round 1 / Round 2 / Round 3``.
* LTM guest lecture — session, ``Date: 25th June 2026 (Thursday) Time:
  4:00 PM`` (event role), Teams join link.
* HackWithInfy / Amazon ML Challenge — hackathon with an apply link.
* Tata Crucible Campus Quiz — quiz.
* Hiring drives (ST Micro, Cadence, ... ) — ``drive``.

The type is decided by ordered keywords (hackathon before contest before
session ...), links keep their real markdown labels, and a missing deadline
stays ``None``.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from placement_pipeline.company import extract_company
from placement_pipeline.models import Link
from placement_pipeline.normalize import flat, strip_markdown
from placement_pipeline.parse_util import (
    dated_facts,
    labelled_block,
    labelled_value,
    links_from,
)

# ordered: first match on (subject + body head) wins
_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("hackathon", r"hackathon|hack\s*on|72-hour\s+hack|ml\s+challenge"),
    ("quiz", r"\bquiz\b|crucible"),
    ("contest", r"\bcontest\b|\bchallenge\b|\bgr\d\b|prompt the future"),
    ("webinar", r"webinar"),
    ("session", r"guest\s+lecture|technical\s+session|masterclass|\bsession\b"),
    ("drive", r"recruitment\s+drive|hiring\s+drive|campus\s+drive|is\s+hiring"),
    ("internship", r"internship\s+(?:opportunity|program|opening)"),
    ("event", r"\bevent\b|workshop|orientation|kick-?off"),
)

_ELIG_LABEL = r"(?:eligibility\s+criteria|eligible\s+degrees|eligibility)"
_KIND_ATTENTION = r"(?:kind\s+attention|kind\s+attn\.?)"

_STAGE_RE = re.compile(r"\b(?:round|stage|level)\s*#?\s*(\d)\b", re.IGNORECASE)
_TEAM_RE = re.compile(r"\bteam\b[^.!?]{0,120}", re.IGNORECASE)


def _opportunity_type(subject: str, text: str) -> Optional[str]:
    hay = subject + "\n" + text[:1200]
    for kind, pattern in _TYPE_RULES:
        if re.search(pattern, hay, re.IGNORECASE):
            return kind
    return None


def _eligibility(text: str) -> Optional[str]:
    value = labelled_block(text, _ELIG_LABEL)
    if value:
        return value[:300]
    # fallback: the "Kind attention:" line states the audience
    value = labelled_value(text, _KIND_ATTENTION)
    if value:
        return value[:300]
    return None


def _event_stages(text: str) -> list[str]:
    stages: list[str] = []
    for m in _STAGE_RE.finditer(text):
        label = f"Round {m.group(1)}"
        if label not in stages:
            stages.append(label)
        if len(stages) >= 8:
            break
    return stages


def _team_rules(text: str) -> list[str]:
    rules: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", flat(text)):
        if _TEAM_RE.search(sentence) and re.search(
            r"\b(?:of|size|members?|upto|up to|maximum|max)\b\s*\d|\b\d\s*(?:-\s*)?"
            r"(?:member|people|students)\b",
            sentence,
            re.IGNORECASE,
        ):
            rule = sentence.strip()[:200]
            if rule not in rules:
                rules.append(rule)
        if len(rules) >= 5:
            break
    return rules


def parse_opportunity(
    subject: str,
    body: str,
    *,
    reference: Optional[datetime] = None,
    students: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Extract opportunity facts (type, links, eligibility, stages, dates)."""
    text = strip_markdown(body or "")
    out: dict[str, Any] = {"warnings": []}

    company_raw, company = extract_company(subject, text)
    out["company_raw"] = company_raw
    out["company"] = company
    if not company:
        out["warnings"].append("company not identified")

    out["opportunity_type"] = _opportunity_type(subject, text)
    if not out["opportunity_type"]:
        out["warnings"].append("opportunity type not recognised")

    dated, deadline = dated_facts(text, reference)
    out["deadline"] = deadline
    out["interview_dates"] = dated
    out["links"] = [Link(url=u, label=lbl) for u, lbl in links_from(text)]
    out["eligibility"] = _eligibility(text)
    out["event_stages"] = _event_stages(text)
    out["team_rules"] = _team_rules(text)

    if not out["links"] and not deadline:
        out["warnings"].append("no link and no deadline found")
    return out
