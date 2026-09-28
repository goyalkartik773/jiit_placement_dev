#!/usr/bin/env python3
"""Per-email extraction report: exactly what the pipeline scraped from every message.

Read-only against the live database (no writes, no reprocessing).  Four
artefacts land in ``reports/``:

===============================  ===========================================
``email_extraction_report.md``    human digest: one row per email + QA checks
                                 (counts only - no student names, safe to commit)
``email_extraction_report.csv``   one row per email, flat counts + previews
``email_extraction_report_details.jsonl``
                                 full extracted payload, one JSON object per
                                 email (every field written back to the DB)
``email_extraction_report_students.csv``
                                 one row per extracted student row
                                 (roll / name / verbatim status / normalised status)
===============================  ===========================================

The ``.csv`` / ``.jsonl`` artefacts carry student names and roll numbers -
that is the point: they are what you validate accuracy against.  They are
git-ignored; only the Markdown digest is committed.

Usage::

    python -u scripts/email_extraction_report.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402

from app.db import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    Company,
    Email,
    FunnelCountRow,
    Offer,
    OfferStudent,
    Opportunity,
    ShortlistEvent,
    ShortlistStudent,
    StudentPlacementEvent,
)

REPORTS = ROOT / "reports"

#: Human labels for the spec taxonomy (report-only; no backend behaviour).
LABELS: dict[str, str] = {
    "FINAL_SELECTION": "Final selection / offer",
    "SHORTLIST": "Shortlist",
    "SELECTION_PROCESS_NOTICE": "Selection process notice",
    "GENERAL_PLACEMENT_NOTICE": "General placement notice",
    "JOB_OPPORTUNITY": "Job opportunity",
    "INTERNSHIP_OPPORTUNITY": "Internship opportunity",
    "REGISTRATION": "Registration / eligibility",
    "HACKATHON": "Hackathon",
    "WEBINAR": "Webinar",
    "WORKSHOP": "Workshop",
    "EVENT": "Event",
    "UNKNOWN": "Unclassified",
}

#: Categories whose job is *not* to produce structured rows - a zero-row
#: result is correct there and must not show up as a defect.
NO_ENTITY_CATEGORIES = {
    "GENERAL_PLACEMENT_NOTICE",
    "REGISTRATION",
    "UNKNOWN",
}

DERIVED_TABLES = [
    "offers",
    "offer_students",
    "shortlist_events",
    "shortlist_students",
    "funnel_counts",
    "opportunities",
    "student_placement_events",
]

MAX_CELL = 400


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _clip(value: Any, limit: int = MAX_CELL) -> str:
    """Stringify ``value`` and cap it - evidence fields can be a whole line."""
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return None if value is None else str(value)


def _dt(value: Any) -> str:
    """``2026-09-26 20:00`` for CSV cells (timezone preserved as written)."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return "" if value is None else str(value)


def _preview(rows: list[str], limit: int = 8) -> str:
    if not rows:
        return ""
    head = "; ".join(rows[:limit])
    return head if len(rows) <= limit else f"{head}; \u2026 +{len(rows) - limit} more"


# --------------------------------------------------------------------------- #
# load (all SELECTs)
# --------------------------------------------------------------------------- #
def load(session) -> dict[str, Any]:
    emails: list[Email] = list(
        session.scalars(
            select(Email).order_by(Email.received_at.desc().nullslast(), Email.id)
        )
    )
    ids = [e.id for e in emails]

    companies: dict[str, str] = dict(
        session.execute(select(Company.id, Company.name)).all()
    )

    def by_email(model, column) -> dict[str, list]:
        if not ids:
            return {}
        grouped: dict[str, list] = defaultdict(list)
        for row in session.scalars(select(model).where(column.in_(ids))):
            grouped[row.email_id].append(row)
        return grouped

    offers = by_email(Offer, Offer.email_id)
    shortlists = by_email(ShortlistEvent, ShortlistEvent.email_id)
    funnels = by_email(FunnelCountRow, FunnelCountRow.email_id)
    opportunities = by_email(Opportunity, Opportunity.email_id)
    events = by_email(StudentPlacementEvent, StudentPlacementEvent.email_id)

    counts: dict[str, int] = {}
    for table in DERIVED_TABLES:
        counts[table] = int(
            session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        )

    return {
        "emails": emails,
        "companies": companies,
        "offers": offers,
        "shortlists": shortlists,
        "funnels": funnels,
        "opportunities": opportunities,
        "events": events,
        "counts": counts,
    }


# --------------------------------------------------------------------------- #
# per-email row
# --------------------------------------------------------------------------- #
def _company_of(loaded, email: Email) -> list[str]:
    names: set[str] = set()
    companies: dict[str, str] = loaded["companies"]

    def add(cid: Optional[str]) -> None:
        if cid and cid in companies:
            names.add(companies[cid])

    for o in loaded["offers"].get(email.id, []):
        add(o.company_id)
    for se in loaded["shortlists"].get(email.id, []):
        add(se.company_id)
    for fc in loaded["funnels"].get(email.id, []):
        add(fc.company_id)
    for op in loaded["opportunities"].get(email.id, []):
        add(op.company_id)
        if op.organization_name:
            names.add(op.organization_name)
    return sorted(names)


def build_rows(loaded: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Return ``(email_rows, student_rows)`` - one entry per source object."""
    emails: list[Email] = loaded["emails"]
    email_rows: list[dict] = []
    student_rows: list[dict] = []

    # (email_id, roll, event_type) -> event, plus a name-keyed fallback for the
    # rows whose source table had no roll number at all (name-only identity).
    event_idx: dict[tuple[str, str, str], StudentPlacementEvent] = {}
    event_by_name: dict[tuple[str, str, str], StudentPlacementEvent] = {}
    for evs in loaded["events"].values():
        for ev in evs:
            if ev.roll_no:
                event_idx.setdefault(
                    (ev.email_id, ev.roll_no, ev.event_type), ev
                )
            if ev.name:
                event_by_name.setdefault(
                    (ev.email_id, ev.event_type, ev.name.strip().lower()), ev
                )

    def find_event(
        email_id: str, roll: Optional[str], event_type: str, name: Optional[str]
    ) -> Optional[StudentPlacementEvent]:
        if roll:
            hit = event_idx.get((email_id, roll, event_type))
            if hit is not None:
                return hit
        if name:
            return event_by_name.get(
                (email_id, event_type, name.strip().lower())
            )
        return None

    for n, email in enumerate(emails, start=1):
        offers = loaded["offers"].get(email.id, [])
        shortlists = loaded["shortlists"].get(email.id, [])
        funnels = loaded["funnels"].get(email.id, [])
        opportunities = loaded["opportunities"].get(email.id, [])
        events = loaded["events"].get(email.id, [])

        company_names = _company_of(loaded, email)

        # --- offers ---------------------------------------------------------
        offer_students: list[OfferStudent] = [s for o in offers for s in o.students]
        offer_preview = [
            f"{s.roll_no or '-'} {s.name or '?'}"
            + (f" [{s.status_raw}]" if s.status_raw else "")
            for s in offer_students
        ]

        # --- shortlists -----------------------------------------------------
        short_students: list[ShortlistStudent] = [
            s for se in shortlists for s in se.students
        ]

        # --- funnel ---------------------------------------------------------
        funnel_detail = [
            f"{fc.round_name}={fc.count}"
            for fc in sorted(funnels, key=lambda f: (f.round_order, f.round_name))
        ]

        # --- opportunity ----------------------------------------------------
        first_opp = opportunities[0] if opportunities else None

        # --- events ---------------------------------------------------------
        event_types = Counter(e.event_type for e in events)
        event_statuses = Counter(e.normalized_status for e in events)

        derived = (
            len(offers)
            + len(offer_students)
            + len(shortlists)
            + len(short_students)
            + len(funnels)
            + len(opportunities)
            + len(events)
        )

        attachments = list(email.attachments)
        class_label = LABELS.get(email.classification or "", email.classification or "")

        email_rows.append(
            {
                "n": n,
                "gmail_message_id": email.gmail_message_id,
                "email_id": email.id,
                "received_at": _dt(email.received_at),
                "source_group": email.source_group or "",
                "sender": _clip(email.sender, 200),
                "subject": _clip(email.subject, 300),
                "classification": email.classification or "",
                "category_label": class_label,
                "classification_method": email.classification_method or "",
                "confidence": (
                    ""
                    if email.classification_confidence is None
                    else round(float(email.classification_confidence), 3)
                ),
                "processing_status": email.processing_status,
                "is_revision": "yes" if email.revision_of else "no",
                "is_canonical": "yes" if email.is_canonical else "no",
                "has_attachments": "yes" if email.has_attachments else "no",
                "attachments": "; ".join(
                    a.filename or "?" for a in attachments
                ),
                "attachment_text_chars": sum(
                    len(a.extracted_text or "") for a in attachments
                ),
                "companies": "; ".join(company_names),
                "offers": len(offers),
                "offer_students": len(offer_students),
                "offer_with_roll": sum(1 for s in offer_students if s.roll_no),
                "offer_without_roll": sum(1 for s in offer_students if not s.roll_no),
                "offer_preview": _preview(offer_preview),
                "shortlist_events": len(shortlists),
                "shortlist_students": len(short_students),
                "shortlist_stages": "; ".join(
                    sorted({f"{se.stage}" + (f" ({se.stage_raw})" if se.stage_raw and se.stage_raw != se.stage else "") for se in shortlists})
                ),
                "shortlist_deadline": "; ".join(
                    sorted({str(se.deadline) for se in shortlists if se.deadline})
                ),
                "funnel_rounds": len(funnels),
                "funnel_total": sum(fc.count for fc in funnels),
                "funnel_detail": "; ".join(funnel_detail),
                "opportunities": len(opportunities),
                "opportunity_type": "; ".join(
                    sorted({op.event_type or "" for op in opportunities if op.event_type})
                ),
                "opportunity_name": "; ".join(
                    sorted({op.event_name or "" for op in opportunities if op.event_name})
                ),
                "opportunity_deadline": "; ".join(
                    sorted({str(op.deadline) for op in opportunities if op.deadline})
                ),
                "registration_link": _clip(
                    first_opp.registration_link if first_opp else "", 200
                ),
                "opportunity_links": len(
                    [l for op in opportunities for l in (op.links or [])]
                ),
                "placement_events": len(events),
                "event_types": "; ".join(
                    f"{k}={v}" for k, v in sorted(event_types.items())
                ),
                "event_statuses": "; ".join(
                    f"{k}={v}" for k, v in sorted(event_statuses.items())
                ),
                "derived_rows": derived,
                "error_message": _clip(email.error_message, 300),
                "_offers": offers,
                "_shortlists": shortlists,
                "_funnels": funnels,
                "_opportunities": opportunities,
                "_events": events,
                "_offer_students": offer_students,
                "_short_students": short_students,
                "_attachments": attachments,
                "_companies": company_names,
            }
        )

        # --- student rows ---------------------------------------------------
        for o in offers:
            for s in o.students:
                ev = find_event(
                    email.id, s.roll_no, "offer", s.name
                ) or find_event(email.id, s.roll_no, "final_selection", s.name)
                student_rows.append(
                    {
                        "email_n": n,
                        "gmail_message_id": email.gmail_message_id,
                        "received_at": _dt(email.received_at),
                        "classification": email.classification or "",
                        "classification_method": email.classification_method or "",
                        "company": loaded["companies"].get(o.company_id, ""),
                        "source": "offer_student",
                        "roll_no": s.roll_no or "",
                        "name": s.name or "",
                        "program": s.program or "",
                        "branch": s.branch or "",
                        "role": s.role or "",
                        "status_raw": s.status_raw or "",
                        "normalized_status": ev.normalized_status if ev else "",
                        "event_type": ev.event_type if ev else "",
                        "event_stage": (ev.stage or "") if ev else "",
                    }
                )
        for se in shortlists:
            for s in se.students:
                ev = find_event(email.id, s.roll_no, "shortlist", s.name)
                student_rows.append(
                    {
                        "email_n": n,
                        "gmail_message_id": email.gmail_message_id,
                        "received_at": _dt(email.received_at),
                        "classification": email.classification or "",
                        "classification_method": email.classification_method or "",
                        "company": loaded["companies"].get(se.company_id, ""),
                        "source": "shortlist_student",
                        "roll_no": s.roll_no or "",
                        "name": s.name or "",
                        "program": s.program or "",
                        "branch": s.branch or "",
                        "role": "",
                        "status_raw": s.status_raw or "",
                        "normalized_status": ev.normalized_status if ev else "",
                        "event_type": ev.event_type if ev else "",
                        "event_stage": (ev.stage or "") if ev else "",
                    }
                )

    return email_rows, student_rows


def detail_payload(row: dict, companies: dict[str, str]) -> dict:
    """Full extraction payload for one email - every field written to the DB."""
    events_for_email = row["_events"]
    return {
        "n": row["n"],
        "gmail_message_id": row["gmail_message_id"],
        "email_id": row["email_id"],
        "received_at": row["received_at"],
        "source_group": row["source_group"],
        "sender": row["sender"],
        "subject": row["subject"],
        "classification": row["classification"],
        "classification_label": row["category_label"],
        "classification_method": row["classification_method"],
        "confidence": row["confidence"],
        "processing_status": row["processing_status"],
        "error_message": row["error_message"] or None,
        "attachments": [
            {
                "filename": a.filename,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "method": a.method,
                "extracted_text_chars": len(a.extracted_text or ""),
                "extracted_text_preview": _clip(a.extracted_text, 300),
            }
            for a in row["_attachments"]
        ],
        "companies": row["_companies"],
        "offers": [
            {
                "offer_id": o.id,
                "company": companies.get(o.company_id),
                "role": o.role,
                "employment_type": o.employment_type,
                "duration": o.duration,
                "stipend": _iso(o.stipend),
                "ctc_total": _iso(o.ctc_total),
                "ctc_raw": o.ctc_raw,
                "ctc_basis": o.ctc_basis,
                "location": o.location,
                "deadline": _iso(o.deadline),
                "confidence": o.confidence,
                "method": o.method,
                "evidence": _clip(o.evidence, 300),
                "students": [
                    {
                        "roll_no": s.roll_no,
                        "name": s.name,
                        "program": s.program,
                        "branch": s.branch,
                        "college": s.college,
                        "email": s.email,
                        "role": s.role,
                        "status_raw": s.status_raw,
                    }
                    for s in o.students
                ],
            }
            for o in row["_offers"]
        ],
        "shortlists": [
            {
                "event_id": se.id,
                "company": companies.get(se.company_id),
                "stage": se.stage,
                "stage_raw": se.stage_raw,
                "venue": se.venue,
                "reporting_at": _iso(se.reporting_at),
                "selection_process": list(se.selection_process or []),
                "interview_dates": list(se.interview_dates or []),
                "deadline": _iso(se.deadline),
                "confidence": se.confidence,
                "method": se.method,
                "evidence": _clip(se.evidence, 300),
                "students": [
                    {
                        "roll_no": s.roll_no,
                        "name": s.name,
                        "program": s.program,
                        "branch": s.branch,
                        "college": s.college,
                        "status_raw": s.status_raw,
                    }
                    for s in se.students
                ],
            }
            for se in row["_shortlists"]
        ],
        "funnel_counts": [
            {
                "company": companies.get(fc.company_id),
                "round_name": fc.round_name,
                "round_order": fc.round_order,
                "count": fc.count,
                "confidence": fc.confidence,
                "method": fc.method,
                "evidence": _clip(fc.evidence, 300),
            }
            for fc in row["_funnels"]
        ],
        "opportunities": [
            {
                "company": companies.get(op.company_id),
                "organization_name": op.organization_name,
                "event_name": op.event_name,
                "event_type": op.event_type,
                "stages": list(op.stages or []),
                "eligibility": list(op.eligibility or []),
                "team_rules": list(op.team_rules or []),
                "links": list(op.links or []),
                "registration_link": op.registration_link,
                "deadline": _iso(op.deadline),
                "career_note": op.career_note,
                "confidence": op.confidence,
                "method": op.method,
                "evidence": _clip(op.evidence, 300),
            }
            for op in row["_opportunities"]
        ],
        "placement_events": [
            {
                "roll_no": ev.roll_no,
                "name": ev.name,
                "event_type": ev.event_type,
                "stage": ev.stage,
                "normalized_status": ev.normalized_status,
                "event_date": _iso(ev.event_date),
                "confidence": ev.confidence,
                "method": ev.method,
                "source_text": _clip(ev.source_text, 300),
            }
            for ev in events_for_email
        ],
        "derived_rows": row["derived_rows"],
    }


# --------------------------------------------------------------------------- #
# QA checks
# --------------------------------------------------------------------------- #
def qa_checks(email_rows: list[dict], student_rows: list[dict], loaded) -> list[tuple]:
    """Return ``[(severity, check, count, detail)]`` - ``count`` 0 = pass."""
    checks: list[tuple] = []

    def add(kind: str, name: str, count: int, detail: str = "") -> None:
        checks.append((kind, name, count, detail))

    def bundle(rows: list[dict], limit: int = 20) -> str:
        out = "; ".join(
            f"#{r['n']} {r['classification']} \u201c{r['subject'][:70]}\u201d"
            for r in rows[:limit]
        )
        if len(rows) > limit:
            out += f"; \u2026 +{len(rows) - limit} more"
        return out

    def grouped(rows: list[dict], key: str) -> str:
        return ", ".join(
            f"{k}={v}"
            for k, v in sorted(Counter(r[key] or "(none)" for r in rows).items())
        )

    pending = [r for r in email_rows if r["processing_status"] == "PENDING"]
    failed = [r for r in email_rows if r["processing_status"] == "FAILED"]
    errored = [r for r in email_rows if r["error_message"]]
    add("warn", "emails still PENDING", len(pending))
    add("warn", "emails FAILED", len(failed))
    add("warn", "emails carrying error_message", len(errored))

    # --- coverage ----------------------------------------------------------
    zero = [r for r in email_rows if r["derived_rows"] == 0]
    zero_expected = [r for r in zero if r["classification"] in NO_ENTITY_CATEGORIES]
    zero_review = [r for r in zero if r["classification"] not in NO_ENTITY_CATEGORIES]
    add(
        "info",
        "zero-row emails in purely informational categories (correct by spec)",
        len(zero_expected),
        grouped(zero_expected, "classification"),
    )
    add(
        "info",
        "zero-row emails in categories that normally yield rows - review these",
        len(zero_review),
        bundle(zero_review),
    )

    # --- identity ----------------------------------------------------------
    offer_students = [s for s in student_rows if s["source"] == "offer_student"]
    short_students = [
        s for s in student_rows if s["source"] == "shortlist_student"
    ]
    no_roll_offers = [s for s in offer_students if not s["roll_no"]]
    no_roll_short = [s for s in short_students if not s["roll_no"]]
    add(
        "info",
        "offer_students with no roll_no (source table had none; name kept)",
        len(no_roll_offers),
        ", ".join(
            sorted({s["company"] or "(no company)" for s in no_roll_offers})
        ),
    )
    add(
        "info",
        "shortlist_students with no roll_no (source table had none; name kept)",
        len(no_roll_short),
        ", ".join(sorted({s["company"] or "(no company)" for s in no_roll_short}))
        or "",
    )

    dup_offer = {
        k: v
        for k, v in Counter(
            (s["gmail_message_id"], s["roll_no"])
            for s in offer_students
            if s["roll_no"]
        ).items()
        if v > 1
    }
    add(
        "warn",
        "duplicate (email, roll) inside offer_students (uq index must hold)",
        len(dup_offer),
    )
    dup_short = {
        k: v
        for k, v in Counter(
            (s["gmail_message_id"], s["roll_no"])
            for s in short_students
            if s["roll_no"]
        ).items()
        if v > 1
    }
    add(
        "warn",
        "duplicate (email, roll) inside shortlist_students",
        len(dup_short),
    )
    add(
        "warn",
        "student rows with no matching placement event (status not assigned)",
        sum(1 for s in student_rows if not s["normalized_status"]),
    )

    # --- reverse direction: every timeline row must have a source student ---
    id_to_gm = {e.id: e.gmail_message_id for e in loaded["emails"]}
    offer_keys = {
        (s["gmail_message_id"], s["roll_no"])
        for s in offer_students
        if s["roll_no"]
    }
    short_keys = {
        (s["gmail_message_id"], s["roll_no"])
        for s in short_students
        if s["roll_no"]
    }
    orphan_events = 0
    for eid, evs in loaded["events"].items():
        gm = id_to_gm.get(eid, "")
        for ev in evs:
            if not ev.roll_no:
                continue
            if ev.event_type == "shortlist":
                if (gm, ev.roll_no) not in short_keys:
                    orphan_events += 1
            elif (gm, ev.roll_no) not in offer_keys:
                orphan_events += 1
    add(
        "warn",
        "placement events with no matching offer/shortlist student row",
        orphan_events,
    )

    # --- cross-posts / dedup ------------------------------------------------
    # A cross-posted email is flagged is_canonical=false + dedup_of=<original>.
    # Both copies are stored; the question is whether they hold the SAME rows.
    by_id = {e.id: e for e in loaded["emails"]}

    def identities(eid: str) -> set[str]:
        """Roll numbers (or lower-cased names when the source had no roll)."""
        out: set[str] = set()
        for o in loaded["offers"].get(eid, []):
            for s in o.students:
                out.add(s.roll_no or (s.name or "").strip().lower())
        for se in loaded["shortlists"].get(eid, []):
            for s in se.students:
                out.add(s.roll_no or (s.name or "").strip().lower())
        return out

    def payload(eid: str) -> int:
        """Structured rows for one email (students counted individually)."""
        offers_ = loaded["offers"].get(eid, [])
        shorts_ = loaded["shortlists"].get(eid, [])
        return (
            sum(len(o.students) for o in offers_)
            + sum(len(se.students) for se in shorts_)
            + len(loaded["funnels"].get(eid, []))
            + len(loaded["opportunities"].get(eid, []))
        )

    double_rows = 0
    double_detail: list[str] = []
    different_detail: list[str] = []
    noncanonical_producing = 0
    for e in loaded["emails"]:
        if e.is_canonical:
            continue
        mine = payload(e.id)
        if not mine:
            continue
        noncanonical_producing += 1
        target = by_id.get(e.dedup_of) if e.dedup_of else None
        theirs = payload(target.id) if target else 0
        if not theirs:
            continue
        shared = identities(e.id) & identities(target.id)
        if shared:
            double_rows += len(shared)
            double_detail.append(
                f"#{e.gmail_message_id} \u201c{_clip(e.subject, 55)}\u201d "
                f"stores {len(shared)} student(s) already stored by its canonical copy"
            )
        else:
            different_detail.append(
                f"#{e.gmail_message_id} \u201c{_clip(e.subject, 55)}\u201d "
                f"({mine} rows, canonical has {theirs}, no shared students)"
            )
    add(
        "warn",
        "cross-posted copies storing students their canonical email already has "
        "(double-counted)",
        len(double_detail),
        "; ".join(double_detail[:12])
        + (f"; \u2026 +{len(double_detail) - 12} more" if len(double_detail) > 12 else ""),
    )
    add(
        "info",
        "students stored twice by such copies",
        double_rows,
    )
    add(
        "info",
        "non-canonical emails that produced rows but share no students with their "
        "canonical copy (genuinely different email)",
        len(different_detail),
        "; ".join(different_detail[:8])
        + (f"; \u2026 +{len(different_detail) - 8} more" if len(different_detail) > 8 else ""),
    )
    add(
        "info",
        "non-canonical emails that produced any rows at all",
        noncanonical_producing,
    )

    # --- successive offer rounds (NOT a defect) ------------------------------
    co_per_student: dict[tuple[str, str], set[str]] = defaultdict(set)
    for rows in loaded["offers"].values():
        for o in rows:
            if not o.company_id:
                continue
            for s in o.students:
                if s.roll_no:
                    co_per_student[(o.company_id, s.roll_no)].add(o.email_id)
    multi = [k for k, v in co_per_student.items() if len(v) > 1]
    by_company = Counter(
        loaded["companies"].get(cid, "?") for cid, _roll in multi
    )
    add(
        "info",
        "same student + company in more than one offer email "
        "(successive offer rounds - dashboard counts once per company)",
        len(multi),
        ", ".join(f"{k}={v}" for k, v in by_company.most_common(8)),
    )

    # --- company / packaging ------------------------------------------------
    offers = [o for rows in loaded["offers"].values() for o in rows]
    no_company = [o for o in offers if not o.company_id]
    add("warn", "offers with no company resolved", len(no_company))
    no_pack = [o for o in offers if not o.ctc_total and not o.stipend]
    add(
        "info",
        "offers with no CTC and no stipend (source email stated none)",
        len(no_pack),
        ", ".join(
            sorted({loaded["companies"].get(o.company_id, "(none)") for o in no_pack})
        ),
    )

    # --- opportunities ------------------------------------------------------
    opps = [o for rows in loaded["opportunities"].values() for o in rows]
    no_deadline = [o for o in opps if not o.deadline]
    no_link = [o for o in opps if not o.registration_link]
    add(
        "info",
        "opportunities with no explicit deadline in the source",
        len(no_deadline),
        ", ".join(
            f"{k}={v}"
            for k, v in sorted(Counter(o.event_type or "(none)" for o in no_deadline).items())
        ),
    )
    add(
        "info",
        "opportunities with no registration link in the source",
        len(no_link),
        ", ".join(
            f"{k}={v}"
            for k, v in sorted(Counter(o.event_type or "(none)" for o in no_link).items())
        ),
    )

    # --- timeline statuses ---------------------------------------------------
    evs = [e for rows in loaded["events"].values() for e in rows]
    add(
        "warn",
        "placement events with UNKNOWN normalised status",
        sum(1 for e in evs if e.normalized_status == "UNKNOWN"),
    )
    add(
        "warn",
        "student rows whose normalised status is UNKNOWN",
        sum(1 for s in student_rows if s["normalized_status"] == "UNKNOWN"),
    )
    return checks


# --------------------------------------------------------------------------- #
# writers
# --------------------------------------------------------------------------- #
EMAIL_COLUMNS = [
    "n", "gmail_message_id", "email_id", "received_at", "source_group",
    "sender", "subject", "classification", "category_label",
    "classification_method", "confidence", "processing_status",
    "is_revision", "is_canonical", "has_attachments", "attachments",
    "attachment_text_chars", "companies",
    "offers", "offer_students", "offer_with_roll", "offer_without_roll",
    "offer_preview",
    "shortlist_events", "shortlist_students", "shortlist_stages",
    "shortlist_deadline",
    "funnel_rounds", "funnel_total", "funnel_detail",
    "opportunities", "opportunity_type", "opportunity_name",
    "opportunity_deadline", "registration_link", "opportunity_links",
    "placement_events", "event_types", "event_statuses",
    "derived_rows", "error_message",
]

STUDENT_COLUMNS = [
    "email_n", "gmail_message_id", "received_at", "classification",
    "classification_method", "company", "source", "roll_no", "name",
    "program", "branch", "role", "status_raw", "normalized_status",
    "event_type", "event_stage",
]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_details(path: Path, email_rows: list[dict], companies: dict[str, str]) -> int:
    written = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in email_rows:
            fh.write(
                json.dumps(
                    detail_payload(row, companies),
                    ensure_ascii=False,
                    default=str,
                )
            )
            fh.write("\n")
            written += 1
    return written


def write_markdown(
    path: Path,
    email_rows: list[dict],
    student_rows: list[dict],
    loaded,
    checks: list[tuple],
) -> None:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    n = len(email_rows)
    dates = [r["received_at"] for r in email_rows if r["received_at"]]
    counts = loaded["counts"]

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in email_rows:
        by_cat[r["classification"] or "(unclassified)"].append(r)

    lines: list[str] = []
    a = lines.append

    a("# Per-email extraction report")
    a("")
    a(f"Generated `{now}` - read-only query over the live `jiit_placement` database.")
    a("")
    a(f"- **{n} emails** in scope, received "
      f"`{min(dates) if dates else '-'}` \u2192 `{max(dates) if dates else '-'}`")
    a(f"- **{len(student_rows):,} extracted student rows** "
      f"({sum(1 for s in student_rows if s['source'] == 'offer_student'):,} from offer "
      f"tables, "
      f"{sum(1 for s in student_rows if s['source'] == 'shortlist_student'):,} from "
      f"shortlist tables)")
    a("")
    a("| artefact | contents |")
    a("| --- | --- |")
    a("| `email_extraction_report.md` | this digest - one row per email, counts only |")
    a("| `email_extraction_report.csv` | same rows, flat columns + preview cells |")
    a("| `email_extraction_report_details.jsonl` | full payload written to the DB, per email |")
    a("| `email_extraction_report_students.csv` | one row per extracted student "
      "(roll / name / verbatim + normalised status) |")
    a("")

    # ---- derived table totals -------------------------------------------
    a("## Derived table totals")
    a("")
    a("| table | rows |")
    a("| --- | ---: |")
    for table in DERIVED_TABLES:
        a(f"| `{table}` | {counts[table]:,} |")
    a("")

    # ---- per category -----------------------------------------------------
    a("## What each category produced")
    a("")
    a("| category | emails | w/ company | offers | offer students | shortlist "
      "events | shortlist students | funnel rounds | opportunities | events "
      "| rows/email |")
    a("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for cat, rows in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        a(
            f"| {LABELS.get(cat, cat)} `{cat}` "
            f"| {len(rows)} "
            f"| {sum(1 for r in rows if r['companies'])} "
            f"| {sum(r['offers'] for r in rows)} "
            f"| {sum(r['offer_students'] for r in rows)} "
            f"| {sum(r['shortlist_events'] for r in rows)} "
            f"| {sum(r['shortlist_students'] for r in rows)} "
            f"| {sum(r['funnel_rounds'] for r in rows)} "
            f"| {sum(r['opportunities'] for r in rows)} "
            f"| {sum(r['placement_events'] for r in rows)} "
            f"| {sum(r['derived_rows'] for r in rows) / len(rows):.1f} |"
        )
    a("")

    # ---- method -----------------------------------------------------------
    a("## Extraction method (as recorded on the email)")
    a("")
    a("| classification_method | emails | share |")
    a("| --- | ---: | ---: |")
    methods = Counter(r["classification_method"] or "(null)" for r in email_rows)
    for method, count in methods.most_common():
        a(f"| `{method}` | {count} | {count / n * 100:.1f}% |")
    a("")

    # ---- QA ---------------------------------------------------------------
    a("## Quality checks")
    a("")
    a("`0` means clean. Anything else is listed with the affected emails.")
    a("")
    a("| | check | count | detail |")
    a("| --- | --- | ---: | --- |")
    for severity, name, count, detail in checks:
        mark = "OK" if count == 0 else ("NOTE" if severity == "info" else "WARN")
        safe = detail.replace("|", "/") if detail else ""
        a(f"| {mark} | {name} | {count:,} | {safe} |")
    a("")
    a("Severity: **WARN** = something to fix or investigate, **NOTE** = explained "
      "by the source data (no action unless you disagree) - every NOTE row spells "
      "out exactly what it found so you can eyeball it. **OK** = clean.")
    a("")

    open_items = [
        (name, count, detail)
        for severity, name, count, detail in checks
        if severity == "warn" and count
    ]
    a("## Needs a decision")
    a("")
    if not open_items:
        a("Nothing - every integrity check came back clean.")
        a("")
    else:
        for name, count, detail in open_items:
            a(f"- **{count}** - {name}.")
            if detail:
                a(f"  - {detail}")
        a("")

    # ---- digest -----------------------------------------------------------
    a("## Per-email digest")
    a("")
    a("Ordered newest first - the same order as the CSV (`n` is the row number). "
      "`\u2013` = nothing structured was extracted for that message.")
    a("")
    a("| # | received | category | method | company | subject | extracted |")
    a("| ---: | --- | --- | --- | --- | --- | --- |")
    for r in email_rows:
        parts: list[str] = []
        if r["offers"]:
            parts.append(
                f"offers {r['offers']} / students {r['offer_students']}"
            )
        if r["shortlist_events"]:
            parts.append(
                f"shortlist {r['shortlist_events']} / students {r['shortlist_students']}"
            )
        if r["funnel_rounds"]:
            parts.append(
                f"funnel {r['funnel_rounds']} rounds ({r['funnel_total']} total)"
                + (f" {r['funnel_detail']}" if r["funnel_detail"] else "")
            )
        if r["opportunities"]:
            opp = f"opportunity {r['opportunity_type'] or '?'}"
            if r["opportunity_deadline"]:
                opp += f", deadline {r['opportunity_deadline']}"
            if r["registration_link"]:
                opp += ", link"
            parts.append(opp)
        if r["has_attachments"] == "yes":
            parts.append(f"attachments {r['attachments'] or '(unnamed)'}")
        if r["placement_events"]:
            parts.append(f"events {r['placement_events']}")
        extracted = "; ".join(parts) if parts else "\u2013"
        company = (r["companies"].split("; ")[0] if r["companies"] else "")
        subject = r["subject"].replace("|", "/")
        a(
            f"| {r['n']} | {r['received_at'][:10]} "
            f"| {r['classification'] or '-'} "
            f"| {r['classification_method'] or '-'} "
            f"| {company} | {subject} | {extracted} |"
        )
    a("")

    a("### Reading the digest")
    a("")
    a("- `company` shows the first resolved company; the CSV/JSONL carry the full list.")
    a("- `extracted` is a count summary - open "
      "`email_extraction_report_details.jsonl` for the actual fields, or "
      "`email_extraction_report_students.csv` for student-level rows.")
    a("- Emails marked `- / -` with no extracted cell are informational notices "
      "(general notice / registration / unclassified): no structured rows is the "
      "correct outcome for them.")
    a("")
    a("## Re-run")
    a("")
    a("```bash")
    a("python -u scripts/email_extraction_report.py")
    a("```")
    a("")

    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        loaded = load(session)
        email_rows, student_rows = build_rows(loaded)
        checks = qa_checks(email_rows, student_rows, loaded)
    finally:
        session.close()

    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "email_extraction_report.md"
    csv_path = REPORTS / "email_extraction_report.csv"
    jsonl_path = REPORTS / "email_extraction_report_details.jsonl"
    students_path = REPORTS / "email_extraction_report_students.csv"

    write_csv(csv_path, EMAIL_COLUMNS, email_rows)
    details = write_details(jsonl_path, email_rows, loaded["companies"])
    write_csv(students_path, STUDENT_COLUMNS, student_rows)
    write_markdown(md_path, email_rows, student_rows, loaded, checks)

    print(f"emails            : {len(email_rows)}")
    print(f"student rows      : {len(student_rows)}")
    print(f"details lines     : {details}")
    for path in (md_path, csv_path, jsonl_path, students_path):
        print(f"{path.name}: {path.stat().st_size:,} bytes")
    print()
    print("QA:")
    for severity, name, count, detail in checks:
        flag = "ok  " if count == 0 else ("info" if severity == "info" else "WARN")
        print(f"  [{flag}] {count:>6} {name}")
        if detail and count:
            print(f"          -> {detail[:400]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
