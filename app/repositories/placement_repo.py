"""Placement queries: per-student timeline and aggregate summary."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Email,
    EmailStatus,
    FunnelCountRow,
    Offer,
    OfferStudent,
    Opportunity,
    ShortlistEvent,
    ShortlistStudent,
    StudentPlacementEvent,
)


def student_timeline(session: Session, roll_no: str) -> dict:
    """Events (append-only timeline) + offers + shortlists for one roll number."""
    upper = roll_no.strip().upper()
    events = list(
        session.scalars(
            select(StudentPlacementEvent)
            .where(func.upper(StudentPlacementEvent.roll_no) == upper)
            .order_by(
                StudentPlacementEvent.event_date.asc().nulls_last(),
                StudentPlacementEvent.created_at.asc(),
            )
        )
    )
    offers = list(
        session.scalars(
            select(Offer)
            .where(Offer.students.any(func.upper(OfferStudent.roll_no) == upper))
            .order_by(Offer.created_at)
        ).unique()
    )
    shortlists = list(
        session.scalars(
            select(ShortlistEvent)
            .where(
                ShortlistEvent.students.any(
                    func.upper(ShortlistStudent.roll_no) == upper
                )
            )
            .order_by(ShortlistEvent.created_at)
        ).unique()
    )
    name = next(
        (e.name for e in events if e.name),
        next((s.name for o in offers for s in o.students if s.name), None),
    )
    return {"events": events, "offers": offers, "shortlists": shortlists, "name": name}


def summary(session: Session) -> dict:
    """Computed aggregates only - every number comes from the tables."""
    emails_by_status = {
        status: int(n)
        for status, n in session.execute(
            select(Email.processing_status, func.count()).group_by(
                Email.processing_status
            )
        ).all()
    }
    emails_by_category = {
        (category or "UNCLASSIFIED"): int(n)
        for category, n in session.execute(
            select(Email.classification, func.count())
            .where(Email.processing_status == EmailStatus.PROCESSED)
            .group_by(Email.classification)
        ).all()
    }
    students_by_status = {
        status: int(n)
        for status, n in session.execute(
            select(
                StudentPlacementEvent.normalized_status, func.count()
            ).group_by(StudentPlacementEvent.normalized_status)
        ).all()
    }
    students_offered = int(
        session.scalar(
            select(func.count(func.distinct(StudentPlacementEvent.roll_no))).where(
                StudentPlacementEvent.normalized_status.in_(("OFFERED", "FINAL_SELECTED"))
            )
        )
        or 0
    )
    students_shortlisted = int(
        session.scalar(
            select(func.count(func.distinct(StudentPlacementEvent.roll_no))).where(
                StudentPlacementEvent.normalized_status == "SHORTLISTED"
            )
        )
        or 0
    )
    package_row = session.execute(
        select(
            func.min(Offer.ctc_total),
            func.max(Offer.ctc_total),
            func.avg(Offer.ctc_total),
            func.count(Offer.ctc_total),
        )
    ).one()
    return {
        "emails_by_status": emails_by_status,
        "emails_by_category": emails_by_category,
        "total_offers": int(
            session.scalar(select(func.count()).select_from(Offer)) or 0
        ),
        "total_shortlist_events": int(
            session.scalar(select(func.count()).select_from(ShortlistEvent)) or 0
        ),
        "total_funnel_rows": int(
            session.scalar(select(func.count()).select_from(FunnelCountRow)) or 0
        ),
        "total_opportunities": int(
            session.scalar(select(func.count()).select_from(Opportunity)) or 0
        ),
        "students_offered": students_offered,
        "students_shortlisted": students_shortlisted,
        "students_by_status": students_by_status,
        "package": {
            "min_inr": int(package_row[0]) if package_row[0] is not None else None,
            "max_inr": int(package_row[1]) if package_row[1] is not None else None,
            "avg_inr": int(package_row[2]) if package_row[2] is not None else None,
            "sample_size": int(package_row[3] or 0),
        },
    }
