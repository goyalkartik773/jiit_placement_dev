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

import re
from datetime import datetime
from typing import Any, Optional

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

# Same two shapes the deterministic cell matcher accepts
# (``src/placement_pipeline/tables.py::_ROLL_CELL_RE``). Kept in sync by
# ``test_llm_roll_normalisation`` so the two paths agree on what a roll is.
_ROLL_DIGITS_RE = re.compile(r"^\d{8,12}$")
_ROLL_ALPHA_RE = re.compile(r"^\d{3}[A-Za-z]\d{3}$")
_DIGIT_RUN_RE = re.compile(r"\d+")
_SCIENTIFIC_RE = re.compile(r"^\d+(?:\.\d+)?[eE][+-]?\d+$")


def normalize_roll(value: Optional[str]) -> Optional[str]:
    """Canonical roll number, or ``None`` when the source lost the number.

    A spreadsheet export renders long enrolment numbers in scientific
    notation (``9.93E+11``), and two different students in the *same* email
    can collapse onto that one string. The deterministic parser never emits
    it (the cell regex rejects it), but the model copies it verbatim - and two
    rows sharing ``(email_id, roll_no, event_type)`` violate
    ``uq_student_placement_events_email``, rolling back every row for the
    email. An unrecoverable number therefore becomes ``None``: the student is
    still written, identified by name, and PostgreSQL's unique index treats
    ``NULL`` as distinct so the insert cannot collide.

    Accepted forms are exactly the deterministic pair (8-12 digits, or
    ``NNNLNNN``) plus light punctuation around them; anything ambiguous
    (several digit runs, a run too long to be a roll) is dropped rather than
    guessed at, because a wrong roll silently maps a student onto somebody
    else's record.
    """
    text = (value or "").strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)
    if _SCIENTIFIC_RE.match(compact):
        return None  # precision was already lost upstream - never guess it back
    if _ROLL_DIGITS_RE.match(compact):
        return compact
    if _ROLL_ALPHA_RE.match(compact):
        return compact.upper()
    runs = _DIGIT_RUN_RE.findall(compact)
    # Exactly one unambiguous run of roll-shaped digits, and nothing else.
    if len(runs) == 1 and _ROLL_DIGITS_RE.match(runs[0]):
        return runs[0]
    return None



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


def _det_student_index(
    ext: Extraction,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Index the deterministic table parse by roll, then by normalised name.

    The model reads the same table but answers with ``roll_number`` / ``name``
    / ``branch`` / ``program`` only - it never echoes the ``University``,
    ``Role Offered`` or ``Status`` cells, and its ``role`` is the *email-level*
    one ("Specialist Programmer (L1, L2, L3) and Digital Specialist Engineer").
    Those per-student cells live on the deterministic row that
    ``tables.extract_students`` already produced, so they are carried across
    here rather than written as ``None`` - writing ``None`` is what left
    ``offer_students.college`` 100 % blank even though every offer table
    carries a ``University`` column.
    """
    by_roll: dict[str, Any] = {}
    by_name: dict[str, Any] = {}
    for row in ext.students:
        roll = normalize_roll(row.roll_no)
        if roll and roll not in by_roll:
            by_roll[roll] = row
        if row.name:
            key = re.sub(r"\s+", " ", row.name).strip().lower()
            if key and key not in by_name:
                by_name[key] = row
    return by_roll, by_name


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
    """One ``offers`` row + its students; model-sourced offer, cell-sourced students."""
    by_roll, by_name = _det_student_index(ext)

    def _det_row(s: Any) -> Any:
        roll = normalize_roll(s.roll_number)
        if roll and roll in by_roll:
            return by_roll[roll]
        if s.name:
            return by_name.get(re.sub(r"\s+", " ", s.name).strip().lower())
        return None

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
    students: list[OfferStudent] = []
    for s in result.students:
        roll = normalize_roll(s.roll_number)
        if not (roll or s.name):
            continue
        det = _det_row(s)
        # Per-STUDENT "Role Offered" cell beats the email-level role the model
        # returns; the model's value stays as the fallback for tables whose
        # role column is missing or blank.
        students.append(
            OfferStudent(
                roll_no=roll,
                name=s.name or None,
                branch=s.branch,
                program=s.program,
                college=getattr(det, "college", None),
                email=getattr(det, "email", None),
                role=(getattr(det, "role", None) or None) or result.role,
                status_raw=getattr(det, "status", None),
            )
        )
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
    """Timeline events for the students the model says were *offered*.

    Two rows may never share ``(email_id, roll_no, event_type)``: a repeated
    roll in the model's answer would trip
    ``uq_student_placement_events_email`` and discard the email's whole
    timeline, so the first occurrence wins and later repeats are dropped.
    """
    from app.extractors.events import _event_date  # shared date normalisation

    if not result.students:
        return []

    kind = offer_event_type(subject)
    default = (
        StudentStatus.FINAL_SELECTED if kind == "final_selection" else StudentStatus.OFFERED
    )
    event_date = _event_date(received_at)

    rows: list[StudentPlacementEvent] = []
    seen: set[tuple[Optional[str], str]] = set()
    for student in result.students:
        roll = normalize_roll(student.roll_number)
        if not (roll or student.name):
            continue
        if roll is not None:
            key = (roll, kind)
            if key in seen:
                continue  # same student listed twice -> one event, not a crash
            seen.add(key)
        rows.append(
            StudentPlacementEvent(
                roll_no=roll,
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
    "normalize_roll",
    "resolve_company_id",
]
