"""Company queries: listing with offer totals + per-company funnel rounds."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Email, FunnelCountRow, Offer, ShortlistEvent


def list_companies(
    session: Session,
    *,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[tuple[Company, int, int]], int]:
    """Companies with total offers / shortlist events (paginated)."""
    offer_counts = (
        select(Offer.company_id, func.count(Offer.id).label("n"))
        .group_by(Offer.company_id)
        .subquery()
    )
    shortlist_counts = (
        select(ShortlistEvent.company_id, func.count(ShortlistEvent.id).label("n"))
        .group_by(ShortlistEvent.company_id)
        .subquery()
    )
    stmt = select(
        Company,
        func.coalesce(offer_counts.c.n, 0),
        func.coalesce(shortlist_counts.c.n, 0),
    ).outerjoin(offer_counts, offer_counts.c.company_id == Company.id).outerjoin(
        shortlist_counts, shortlist_counts.c.company_id == Company.id
    )
    count_stmt = select(func.count()).select_from(Company)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Company.name.ilike(pattern))
        count_stmt = count_stmt.where(Company.name.ilike(pattern))
    total = int(session.scalar(count_stmt) or 0)
    rows = session.execute(
        stmt.order_by(Company.name)
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).all()
    return [(r[0], int(r[1]), int(r[2])) for r in rows], total


def latest_funnel(session: Session, company_id: str):
    """(email, rounds) for the company's most recent funnel email.

    Distinct events are never merged: when a company has several funnel
    emails the newest one is the current funnel and says which email it
    came from.
    """
    email = session.scalar(
        select(Email)
        .join(FunnelCountRow, FunnelCountRow.email_id == Email.id)
        .where(FunnelCountRow.company_id == company_id)
        .order_by(Email.received_at.desc().nulls_last(), Email.created_at.desc())
        .limit(1)
    )
    if email is None:
        return None, []
    rounds = list(
        session.scalars(
            select(FunnelCountRow)
            .where(
                FunnelCountRow.company_id == company_id,
                FunnelCountRow.email_id == email.id,
            )
            .order_by(FunnelCountRow.round_order)
        )
    )
    return email, rounds
