"""Read endpoints: message list/detail for the admin UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import email_repo
from app.schemas.common import ApiResponse
from app.schemas.messages import MessageDetail, MessageList
from app.schemas.serializers import message_detail, message_summary

router = APIRouter()


@router.get(
    "/gmail/messages",
    response_model=ApiResponse[MessageList],
    tags=["gmail"],
    summary="Paginated message list (filters: status, classification, q)",
)
def list_messages(
    status: str | None = Query(
        None, description="PENDING | PROCESSING | PROCESSED | FAILED | SKIPPED"
    ),
    classification: str | None = Query(
        None, description="One of the 14 taxonomy values"
    ),
    q: str | None = Query(None, description="Substring match: subject/sender/id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ApiResponse[MessageList]:
    rows, total = email_repo.list_messages(
        session,
        status=status,
        classification=classification,
        q=q,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        success=True,
        message="ok",
        data=MessageList(
            items=[message_summary(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.get(
    "/gmail/messages/{message_id}",
    response_model=ApiResponse[MessageDetail],
    tags=["gmail"],
    summary="Complete email details + extraction results (uuid or Gmail id)",
)
def get_message(
    message_id: str, session: Session = Depends(get_session)
) -> ApiResponse[MessageDetail]:
    row = email_repo.get_by_key(session, message_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"no email with id or message id {message_id!r}"
        )
    return ApiResponse(success=True, message="ok", data=message_detail(session, row))
