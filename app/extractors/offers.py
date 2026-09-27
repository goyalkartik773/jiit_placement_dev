"""Type-1 extraction: final selection / offer emails -> offers + students."""

from __future__ import annotations

import re
from typing import Optional

from placement_pipeline import normalize
from placement_pipeline.models import Extraction, SubPattern  # noqa: F401

from app.extractors.evidence import (
    CONF_INFERRED,
    CONF_LABELED,
    CONF_TABLE_ROW,
    METHOD_RULE,
    find_evidence,
)
from app.models import Offer, OfferStudent

_LOCATION_LABEL = r"(?:job\s+)?location"
_TO_FULLTIME_RE = re.compile(
    r"to be converted to full[- ]?time|convert(ed)? to full[- ]?time", re.IGNORECASE
)
_INTERN_RE = re.compile(r"\bintern(ship|e)?\b", re.IGNORECASE)


def employment_type(subject: str, ext: Extraction) -> Optional[str]:
    """full_time | internship | internship_to_fulltime from source wording."""
    hay = f"{subject}\n{ext.role or ''}\n{ext.duration or ''}\n{ext.package_raw or ''}"
    if _TO_FULLTIME_RE.search(hay):
        return "internship_to_fulltime"
    if _INTERN_RE.search(hay):
        return "internship"
    if ext.package_inr or ext.stipend_inr:
        return "full_time"
    return None


def location(body: str, subject: str) -> Optional[str]:
    try:
        value = normalize.labelled_value(body or "", _LOCATION_LABEL)
    except Exception:
        value = ""
    value = (value or "").strip()
    if not value:
        return None
    # Guard against degenerate captures ("Location:" with nothing after it).
    return value[:200] if len(value) >= 2 else None


def build_offer(
    ext: Extraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    body: str,
) -> tuple[Offer, list[OfferStudent]]:
    evidence = ext.package_raw or find_evidence(
        body, ext.package_raw or ext.role, fallback=subject
    )
    offer = Offer(
        email_id=email_id,
        company_id=company_id,
        role=ext.role,
        employment_type=employment_type(subject, ext),
        duration=ext.duration,
        stipend=ext.stipend_inr,
        ctc_total=ext.package_inr,
        ctc_raw=ext.package_raw,
        ctc_basis=ext.package_basis,
        location=location(body, subject),
        deadline=ext.deadline,
        evidence=evidence,
        confidence=CONF_LABELED if ext.package_raw else CONF_INFERRED,
        method=METHOD_RULE,
    )
    students = [
        OfferStudent(
            roll_no=row.roll_no,
            name=row.name or row.raw_name,
            branch=row.branch,
            program=row.program,
            college=row.college,
            email=row.email,
            role=row.role,
            status_raw=row.status,
        )
        for row in ext.students
    ]
    return offer, students
