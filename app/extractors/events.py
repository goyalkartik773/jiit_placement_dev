"""Append-only student timeline events (identity = roll_no).

Only emails that actually carry a student list generate events; funnel-count
and notice emails contribute no per-student rows (we never invent students).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from placement_pipeline.models import Category, Extraction

from app.classifiers.taxonomy import offer_event_type
from app.extractors.evidence import CONF_TABLE_ROW, METHOD_RULE
from app.models import ShortlistEvent, StudentPlacementEvent, StudentStatus

IST = ZoneInfo("Asia/Kolkata")

_WITHDRAWN_RE = re.compile(r"withdraw|rescind|cancel", re.IGNORECASE)
_NOT_SELECTED_RE = re.compile(
    r"\bnot (shortlisted|selected)\b|\brejected\b|\bnot cleared\b", re.IGNORECASE
)


def _event_date(value: Optional[datetime]) -> Optional[date]:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(IST)
    return value.date()


def _normalized(status_raw: Optional[str], default: str) -> str:
    """Map the source's own wording; missing/other wording keeps ``default``."""
    text = (status_raw or "").strip()
    if not text:
        return default
    if _WITHDRAWN_RE.search(text):
        # Offer withdrawn = offer no longer stands; raw text stays in
        # offer_students.status_raw / shortlist_students.status_raw.
        return StudentStatus.REJECTED
    if _NOT_SELECTED_RE.search(text):
        return StudentStatus.REJECTED
    return default


def build_events(
    ext: Extraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    received_at: Optional[datetime],
    shortlist: Optional[ShortlistEvent] = None,
) -> list[StudentPlacementEvent]:
    if not ext.students:
        return []  # no student list -> no per-student events (never invented)

    event_date = _event_date(received_at)
    rows: list[StudentPlacementEvent] = []

    if ext.category == Category.OFFER:
        kind = offer_event_type(subject)
        default = (
            StudentStatus.FINAL_SELECTED
            if kind == "final_selection"
            else StudentStatus.OFFERED
        )
        stage = None
        event_type = kind
    elif ext.category == Category.SHORTLIST:
        event_type = "shortlist"
        default = StudentStatus.SHORTLISTED
        stage = (
            (shortlist.stage_raw or shortlist.stage) if shortlist else None
        )
    else:
        return []

    for student in ext.students:
        rows.append(
            StudentPlacementEvent(
                roll_no=student.roll_no,
                name=student.name or student.raw_name,
                company_id=company_id,
                email_id=email_id,
                event_type=event_type,
                stage=stage,
                normalized_status=_normalized(student.status, default),
                event_date=event_date,
                source_text=subject or None,
                confidence=CONF_TABLE_ROW,
                method=METHOD_RULE,
            )
        )
    return rows
