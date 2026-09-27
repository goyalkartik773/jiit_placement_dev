"""Builders that turn a *validated* LLM extraction into database rows.

The deterministic builders in :mod:`app.extractors.offers` and
:mod:`app.extractors.events` are untouched: for offer-type emails their output
is still computed and stored, but only as audit evidence (``method`` marks
which one was actually written).

Rows built here are only ever created from a
:class:`~app.llm.schema.FinalSelectionExtraction` whose ``email_type`` is
``FINAL_SELECTION`` - a ``NOT_FINAL_SELECTION`` / ``UNCERTAIN`` verdict
produces **no** offer row and **no** ``FINAL_SELECTED`` / ``OFFERED`` event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from placement_pipeline.models import Category, Extraction

from app.classifiers.taxonomy import offer_event_type
from app.extractors.evidence import CONF_LLM, METHOD_LLM, METHOD_RULE  # noqa: F401
from app.extractors.offers import employment_type
from app.llm.router import LLMResult
from app.llm.schema import FinalSelectionExtraction
from app.models import (
    Company,
    Offer,
    OfferStudent,
    StudentPlacementEvent,
    StudentStatus,
)

#: Written when every LLM account failed and the deterministic result was kept.
METHOD_RULE_FALLBACK = "rule_based_fallback"


def resolve_company_id(
    session: Session, ext: Extraction, llm_company: Optional[str]
) -> Optional[str]:
    """Company id from the parser's name, else the one the model read off.

    Distinct names are never merged - this only adds the name the parser
    could not resolve when the model did.
    """
    if ext.company:
        from app.extractors.companies import get_or_create_company

        company = get_or_create_company(session, ext)
        return company.id if company else None

    name = (llm_company or "").strip()
    if not name:
        return None
    company = session.scalar(select(Company).where(Company.name == name))
    if company is None:
        company = Company(name=name, raw_name=name)
        session.add(company)
        session.flush()
    return company.id


def build_llm_offer(
    result: FinalSelectionExtraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    body: str,
    ext: Extraction,
    method: str,
) -> tuple[Offer, list[OfferStudent]]:
    """One ``offers`` row + its students, all fields sourced from the model."""
    offer = Offer(
        email_id=email_id,
        company_id=company_id,
        role=result.role or ext.role,
        employment_type=employment_type(subject, ext),
        duration=ext.duration,
        stipend=_int_or_none(result.stipend),
        ctc_total=_int_or_none(result.ctc_total),
        # No raw CTC text exists in the model's JSON - never invent one.
        ctc_raw=None,
        ctc_basis=None,
        location=result.location,
        deadline=ext.deadline,
        evidence=(result.evidence or None),
        confidence=result.confidence,
        method=method,
    )
    students = [
        OfferStudent(
            roll_no=s.roll_number or None,
            name=s.name or None,
            branch=s.branch,
            program=s.program,
            college=None,
            email=None,
            role=result.role,
            status_raw=None,
        )
        for s in result.students
        if (s.roll_number or s.name)
    ]
    return offer, students


def build_llm_events(
    result: FinalSelectionExtraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    received_at: Optional[datetime],
    method: str,
) -> list[StudentPlacementEvent]:
    """Timeline events for the students the model says were *offered*."""
    from app.extractors.events import _event_date  # shared date normalisation

    if not result.students:
        return []

    kind = offer_event_type(subject)
    default = (
        StudentStatus.FINAL_SELECTED if kind == "final_selection" else StudentStatus.OFFERED
    )
    event_date = _event_date(received_at)

    rows: list[StudentPlacementEvent] = []
    for student in result.students:
        if not (student.roll_number or student.name):
            continue
        rows.append(
            StudentPlacementEvent(
                roll_no=student.roll_number or None,
                name=student.name or None,
                company_id=company_id,
                email_id=email_id,
                event_type=kind,
                stage=None,
                normalized_status=default,
                event_date=event_date,
                source_text=subject or None,
                confidence=result.confidence,
                method=method,
            )
        )
    return rows


def deterministic_statuses(ext: Extraction, subject: str) -> dict[str, int]:
    """What the deterministic path *would* have written, as an audit count.

    Computed for every offer candidate regardless of which path wins, so a
    deterministic-vs-LLM disagreement is always on record.
    """
    from app.extractors.events import _normalized

    if ext.category != Category.OFFER or not ext.students:
        return {}
    default = (
        StudentStatus.FINAL_SELECTED
        if offer_event_type(subject) == "final_selection"
        else StudentStatus.OFFERED
    )
    out: dict[str, int] = {}
    for student in ext.students:
        status = _normalized(student.status, default)
        out[status] = out.get(status, 0) + 1
    return out


def audit_signals(
    *,
    det_category: str,
    det_offer_rows: int,
    det_statuses: dict[str, int],
    call: Optional[LLMResult],
    error: Optional[str],
    method: str,
    low_confidence: bool,
    written_offers: int,
    written_events: int,
) -> list[str]:
    """Structured audit trail: what the rules said vs what the model said.

    Stored in ``emails.classification_signals`` next to the parser's own
    signals, so a deterministic-vs-LLM disagreement is queryable later
    (golden-dataset building, regression reports) without re-running either.
    """
    signals: list[str] = [f"det:category={det_category}"]
    signals.append(f"det:offer_rows={det_offer_rows}")
    if det_statuses:
        rendered = ",".join(
            f"{key}:{value}" for key, value in sorted(det_statuses.items())
        )
        signals.append(f"det:normalized={rendered}")
    signals.append(f"method={method}")

    if call is None:
        if error:
            reason = error.replace(" ", "_")[:120]
            signals.append(f"llm:unavailable={reason}")
        # call=None and no error means the hybrid layer was switched off:
        # ``method=rule_based`` already says so, no invented llm: signal.
        signals.append(f"written:offers={written_offers},events={written_events}")
        return signals

    ext = call.extraction
    signals.append(f"llm:account={call.account_label}")
    signals.append(f"llm:email_type={ext.email_type}")
    signals.append(f"llm:confidence={ext.confidence:.2f}")
    signals.append(f"llm:students={len(ext.students)}")
    if call.failed_over:
        signals.append("llm:failed_over=true")
    if low_confidence:
        signals.append("llm:low_confidence=true")

    deterministic_final = det_statuses.get(StudentStatus.FINAL_SELECTED, 0) + det_statuses.get(
        StudentStatus.OFFERED, 0
    )
    if ext.is_final() and not deterministic_final:
        signals.append("llm:overrides_deterministic=adds_offers")
    elif not ext.is_final() and deterministic_final:
        signals.append("llm:overrides_deterministic=suppresses_offers")
    elif ext.is_final() and len(ext.students) != det_offer_rows:
        signals.append(
            f"llm:overrides_deterministic=row_count "
            f"({det_offer_rows} -> {len(ext.students)})"
        )
    else:
        signals.append("llm:agrees_with_deterministic")

    signals.append(f"written:offers={written_offers},events={written_events}")
    return signals


def _int_or_none(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(float(value)))


__all__ = [
    "METHOD_LLM",
    "METHOD_RULE",
    "METHOD_RULE_FALLBACK",
    "audit_signals",
    "build_llm_events",
    "build_llm_offer",
    "deterministic_statuses",
    "resolve_company_id",
]
