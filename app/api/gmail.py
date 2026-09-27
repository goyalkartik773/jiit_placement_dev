"""Gmail endpoints: ``POST /api/gmail/sync`` (Step 1).

Later steps add ``/gmail/process-pending`` and the ``/gmail/messages``
list/detail/retry endpoints to this same router.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import get_container, get_session
from app.container import Container
from app.db import get_session_factory
from app.gmail.auth import GmailAuthError
from app.gmail.client import GmailApiError
from app.repositories import email_repo
from app.schemas.common import ApiResponse
from app.schemas.processing import (
    MessageProcessResult,
    ProcessPendingRequest,
    ProcessStats,
)
from app.schemas.sync import SyncRequest, SyncStats
from app.services.processing_service import process_one, run_processing
from app.services.status_store import JobBusyError
from app.services.sync_service import run_sync
from sqlalchemy.orm import Session

router = APIRouter()


@router.post(
    "/gmail/sync",
    response_model=ApiResponse[SyncStats],
    tags=["gmail"],
    summary="Step 1: fetch raw messages from Gmail into PostgreSQL",
)
def gmail_sync(
    payload: SyncRequest | None = Body(default=None),
    container: Container = Depends(get_container),
) -> ApiResponse[SyncStats]:
    payload = payload or SyncRequest()

    def body(handle):
        # Session is created inside the run (closed by run_sync's finally),
        # so a 409 busy-reject never leaks a connection.
        session = get_session_factory()()
        return run_sync(
            client=container.gmail_client(),
            session=session,
            handle=handle,
            payload=payload,
            settings=container.settings,
        )

    try:
        stats = container.runner.execute("sync", body)
    except JobBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "A sync run is already in progress", "status": exc.snapshot},
        )
    except GmailAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except GmailApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    stats["run_id"] = container.status.snapshot("sync").get("run_id")
    message = (
        f"Sync completed: {stats['new_messages']} new, "
        f"{stats['duplicates_skipped']} duplicates skipped, "
        f"{stats['failed_messages']} failed"
    )
    if stats.get("errors"):
        message += (
            f"; {len(stats['errors'])} group error(s), re-run to resume "
            "(committed rows are kept)"
        )
    return ApiResponse(
        success=True,
        message=message,
        data=stats,
    )


@router.post(
    "/gmail/process-pending",
    response_model=ApiResponse[ProcessStats],
    tags=["gmail"],
    summary="Step 2: classify + extract PENDING emails into normalized tables",
)
def gmail_process_pending(
    payload: ProcessPendingRequest | None = Body(default=None),
    container: Container = Depends(get_container),
) -> ApiResponse[ProcessStats]:
    payload = payload or ProcessPendingRequest()

    def body(handle):
        return run_processing(
            session_factory=get_session_factory(),
            handle=handle,
            payload=payload,
            settings=container.settings,
        )

    try:
        stats = container.runner.execute("processing", body)
    except JobBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A processing run is already in progress",
                "status": exc.snapshot,
            },
        )

    stats["run_id"] = container.status.snapshot("processing").get("run_id")
    return ApiResponse(
        success=True,
        message=(
            f"Processed {stats['succeeded']}/{stats['processed']} emails"
            + (f" ({stats['failed']} failed)" if stats["failed"] else "")
        ),
        data=stats,
    )


@router.post(
    "/gmail/messages/{message_id}/process",
    response_model=ApiResponse[MessageProcessResult],
    tags=["gmail"],
    summary="Process or retry a single email (any status); 404 if unknown",
)
def gmail_process_message(
    message_id: str,
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> ApiResponse[MessageProcessResult]:
    row = email_repo.get_by_key(session, message_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"no email with id or message id {message_id!r}"
        )
    email_id = row.id

    def body(handle):
        run_session = get_session_factory()()
        try:
            return process_one(run_session, email_id, container.settings)
        finally:
            run_session.close()

    try:
        result = container.runner.execute("processing", body)
    except JobBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A processing run is already in progress",
                "status": exc.snapshot,
            },
        )

    ok = result["status"] == "PROCESSED"
    return ApiResponse(
        success=ok,
        message=(
            f"Email {result['gmail_message_id']} processed as {result['category']}"
            if ok
            else f"Email {result['gmail_message_id']} failed: {result['error']}"
        ),
        data=result,
    )
