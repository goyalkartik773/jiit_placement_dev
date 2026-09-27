"""Gmail endpoints: ``POST /api/gmail/sync`` (Step 1).

Later steps add ``/gmail/process-pending`` and the ``/gmail/messages``
list/detail/retry endpoints to this same router.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import get_container
from app.container import Container
from app.db import get_session_factory
from app.gmail.auth import GmailAuthError
from app.gmail.client import GmailApiError
from app.schemas.common import ApiResponse
from app.schemas.sync import SyncRequest, SyncStats
from app.services.status_store import JobBusyError
from app.services.sync_service import run_sync

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
    return ApiResponse(
        success=True,
        message=(
            f"Sync completed: {stats['new_messages']} new, "
            f"{stats['duplicates_skipped']} duplicates skipped, "
            f"{stats['failed_messages']} failed"
        ),
        data=stats,
    )
