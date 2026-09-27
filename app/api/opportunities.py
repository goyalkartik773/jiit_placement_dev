"""Read endpoint: opportunity listing (optionally upcoming only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models import Email
from app.repositories import opportunity_repo
from app.schemas.common import ApiResponse
from app.schemas.messages import OpportunityOut
from app.schemas.opportunities import OpportunityList
from app.schemas.serializers import company_names, opportunity_out

router = APIRouter()


@router.get(
    "/opportunities",
    response_model=ApiResponse[OpportunityList],
    tags=["opportunities"],
    summary="Hackathons/events/opportunities (upcoming = deadline not past)",
)
def list_opportunities(
    upcoming: bool = Query(
        False, description="Only opportunities with no deadline or a future one"
    ),
    event_type: str | None = Query(
        None, description="HACKATHON | WEBINAR | EVENT | WORKSHOP | ..."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ApiResponse[OpportunityList]:
    rows, total = opportunity_repo.list_opportunities(
        session, upcoming=upcoming, event_type=event_type, page=page, page_size=page_size
    )
    email_ids = [row.email_id for row in rows]
    emails = {
        e.id: e
        for e in session.scalars(select(Email).where(Email.id.in_(email_ids) if email_ids else False))
    } if email_ids else {}
    names = company_names(session, [row.company_id for row in rows])
    items: list[OpportunityOut] = [
        opportunity_out(
            row,
            names,
            subject=(emails[row.email_id].subject if row.email_id in emails else None),
            received_at=(
                emails[row.email_id].received_at if row.email_id in emails else None
            ),
        )
        for row in rows
    ]
    return ApiResponse(
        success=True,
        message="ok",
        data=OpportunityList(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            upcoming_only=upcoming,
        ),
    )
