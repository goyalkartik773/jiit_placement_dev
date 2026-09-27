"""Read endpoints: companies and per-company funnel rounds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models import Company
from app.repositories import company_repo
from app.schemas.common import ApiResponse
from app.schemas.companies import CompanyList, CompanyOut, FunnelOut, FunnelSource
from app.schemas.serializers import funnel_out

router = APIRouter()


@router.get(
    "/companies",
    response_model=ApiResponse[CompanyList],
    tags=["companies"],
    summary="Companies with total offer/shortlist counts",
)
def list_companies(
    q: str | None = Query(None, description="Substring match on company name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ApiResponse[CompanyList]:
    rows, total = company_repo.list_companies(
        session, q=q, page=page, page_size=page_size
    )
    items = [
        CompanyOut(
            id=company.id,
            name=company.name,
            raw_name=company.raw_name,
            aliases=list(company.aliases or []),
            total_offers=offers,
            total_shortlist_events=shortlists,
            created_at=company.created_at,
        )
        for company, offers, shortlists in rows
    ]
    return ApiResponse(
        success=True,
        message="ok",
        data=CompanyList(items=items, total=total, page=page, page_size=page_size),
    )


@router.get(
    "/companies/{company_id}/funnel",
    response_model=ApiResponse[FunnelOut],
    tags=["companies"],
    summary="Latest funnel rounds [{round_name, count}] for one company",
)
def company_funnel(
    company_id: str, session: Session = Depends(get_session)
) -> ApiResponse[FunnelOut]:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"unknown company {company_id!r}")
    email, rounds = company_repo.latest_funnel(session, company_id)
    source = (
        FunnelSource(
            email_id=email.id,
            gmail_message_id=email.gmail_message_id,
            subject=email.subject or "",
            received_at=email.received_at,
            classification=email.classification,
        )
        if email is not None
        else None
    )
    return ApiResponse(
        success=True,
        message="ok",
        data=FunnelOut(
            company_id=company.id,
            company_name=company.name,
            source=source,
            rounds=[funnel_out(row) for row in rounds],
        ),
    )
