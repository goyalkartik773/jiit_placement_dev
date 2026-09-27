"""Live run-status endpoints (poll while POST /api/gmail/* is running)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.container import Container
from app.schemas.common import ApiResponse
from app.schemas.sync import JobStatus

router = APIRouter()


@router.get(
    "/sync/status",
    response_model=ApiResponse[JobStatus],
    tags=["status"],
    summary="Live progress of the current/last Gmail sync run",
)
def sync_status(container: Container = Depends(get_container)) -> ApiResponse[JobStatus]:
    return ApiResponse(success=True, message="ok", data=container.status.snapshot("sync"))


@router.get(
    "/processing/status",
    response_model=ApiResponse[JobStatus],
    tags=["status"],
    summary="Live progress of the current/last process-pending run",
)
def processing_status(
    container: Container = Depends(get_container),
) -> ApiResponse[JobStatus]:
    return ApiResponse(
        success=True, message="ok", data=container.status.snapshot("processing")
    )
