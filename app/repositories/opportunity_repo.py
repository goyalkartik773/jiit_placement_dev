"""Opportunity listing (optionally upcoming only, i.e. deadline not past)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Email, Opportunity


def list_opportunities(
    session: Session,
    *,
    upcoming: bool = False,
    event_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Opportunity], int]:
    filters = []
    if upcoming:
        filters.append(
            or_(Opportunity.deadline.is_(None), Opportunity.deadline >= date.today())
        )
    if event_type:
        filters.append(Opportunity.event_type == event_type.upper())

    count_stmt = select(func.count()).select_from(Opportunity)
    stmt = select(Opportunity).join(Email, Email.id == Opportunity.email_id)
    for flt in filters:
        count_stmt = count_stmt.where(flt)
        stmt = stmt.where(flt)
    total = int(session.scalar(count_stmt) or 0)
    rows = list(
        session.scalars(
            stmt.order_by(
                Opportunity.deadline.asc().nulls_last(), Email.received_at.desc()
            )
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
    )
    return rows, total
