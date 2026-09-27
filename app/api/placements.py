"""Read endpoints: per-student placement timeline + aggregate summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import placement_repo
from app.schemas.common import ApiResponse
from app.schemas.placements import PlacementSummary, StudentTimeline
from app.schemas.serializers import company_names, event_out, offer_out, shortlist_out

router = APIRouter()


@router.get(
    "/placements",
    response_model=ApiResponse[StudentTimeline],
    tags=["placements"],
    summary="Placement timeline for one student (append-only events)",
)
def student_placements(
    student_roll: str = Query(..., min_length=1, max_length=64),
    session: Session = Depends(get_session),
) -> ApiResponse[StudentTimeline]:
    roll = student_roll.strip()
    data = placement_repo.student_timeline(session, roll)
    names = company_names(
        session,
        [
            *(e.company_id for e in data["events"]),
            *(o.company_id for o in data["offers"]),
            *(s.company_id for s in data["shortlists"]),
        ],
    )
    return ApiResponse(
        success=True,
        message="ok",
        data=StudentTimeline(
            roll_no=roll,
            name=data["name"],
            events=[event_out(e, names) for e in data["events"]],
            offers=[offer_out(o, names) for o in data["offers"]],
            shortlists=[shortlist_out(s, names) for s in data["shortlists"]],
        ),
    )


@router.get(
    "/placements/summary",
    response_model=ApiResponse[PlacementSummary],
    tags=["placements"],
    summary="Aggregate counts + package stats (computed, never invented)",
)
def placements_summary(
    session: Session = Depends(get_session),
) -> ApiResponse[PlacementSummary]:
    return ApiResponse(success=True, message="ok", data=placement_repo.summary(session))
