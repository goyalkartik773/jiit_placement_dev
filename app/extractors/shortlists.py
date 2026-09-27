"""Type-2 extraction: shortlist emails -> event + students + funnel counts.

Both sub-patterns land here: 2A (named shortlist + process steps/venue) and
2B (aggregate round counts -> ordered ``[{round_name, count}]``).
``stage_raw`` keeps the source wording verbatim while ``stage`` holds the
normalized enum.
"""

from __future__ import annotations

import re
from typing import Optional

from placement_pipeline import normalize
from placement_pipeline.models import Extraction

from app.extractors.evidence import (
    CONF_SENTENCE,
    CONF_TABLE_ROW,
    METHOD_RULE,
    METHOD_LLM,
    CONF_LLM,
)
from app.models import FunnelCountRow, ShortlistEvent, ShortlistStudent

_PROCESS_LABEL = r"selection\s+process(?:\s+(?:steps|flow|schedule))?"
_STEP_SPLIT_RE = re.compile(r"[\n;]+|\s\d{1,2}[.)]\s")


def normalize_stage(raw: Optional[str]) -> str:
    """Stage enum preserving semantics (raw text is kept alongside)."""
    text = (raw or "").lower()
    if not text:
        return "SHORTLISTED"
    if re.search(r"\btest\b|assessment|online test|aptitude", text):
        return "TEST_SHORTLISTED"
    if re.search(r"group discussion|\bgd\b", text):
        return "GD_SHORTLISTED"
    if re.search(r"interview", text):
        return "INTERVIEW_SHORTLISTED"
    return "SHORTLISTED"


def selection_process_steps(body: str) -> list[str]:
    """Ordered steps from the "Selection Process:" block (deterministic)."""
    try:
        block = normalize.labelled_block(body or "", _PROCESS_LABEL)
    except Exception:
        block = ""
    if not block:
        return []
    steps: list[str] = []
    for piece in _STEP_SPLIT_RE.split(block):
        step = re.sub(r"^\s*\d{1,2}[.)]\s*", "", piece).strip()
        step = re.sub(r"\s+", " ", step)
        if step and step.lower() not in {s.lower() for s in steps}:
            steps.append(step[:300])
        if len(steps) >= 12:
            break
    return steps


def build_shortlist(
    ext: Extraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    body: str,
    funnel_method: str = METHOD_RULE,
) -> tuple[ShortlistEvent, list[ShortlistStudent], list[FunnelCountRow]]:
    steps = selection_process_steps(body)
    interview_dates = [
        fact.when.isoformat() for fact in ext.interview_dates if fact.when
    ]
    event = ShortlistEvent(
        email_id=email_id,
        company_id=company_id,
        stage=normalize_stage(ext.stage),
        stage_raw=ext.stage,
        venue=ext.venue,
        reporting_at=ext.reporting_at,
        selection_process=steps,
        interview_dates=interview_dates,
        deadline=ext.deadline,
        evidence=ext.stage or (steps[0] if steps else subject),
        confidence=CONF_TABLE_ROW if ext.students else (
            CONF_SENTENCE if ext.funnel_counts else 0.75
        ),
        method=METHOD_RULE,
    )
    students = [
        ShortlistStudent(
            roll_no=row.roll_no,
            name=row.name or row.raw_name,
            branch=row.branch,
            program=row.program,
            college=row.college,
            status_raw=row.status,
        )
        for row in ext.students
    ]
    funnels = [
        FunnelCountRow(
            email_id=email_id,
            company_id=company_id,
            round_name=count.stage,
            round_order=index + 1,
            count=count.count,
            evidence=count.sentence or None,
            confidence=CONF_LLM if funnel_method == METHOD_LLM else CONF_SENTENCE,
            method=funnel_method,
        )
        for index, count in enumerate(ext.funnel_counts)
    ]
    return event, students, funnels
