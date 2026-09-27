"""Schemas for Step 1 (sync) and the live job-status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    query: Optional[str] = Field(
        None,
        description="Gmail search query; when set it replaces the per-group "
        "'list:' queries",
    )
    max_results: Optional[int] = Field(
        None, ge=1, le=20000, description="Cap on messages fetched this run"
    )
    groups: Optional[list[str]] = Field(
        None, description="Override the configured source Google Groups"
    )
    download_attachments: bool = Field(
        True,
        description="Download+parse attachments that the legacy system has "
        "not already extracted (already-extracted text is always reused)",
    )


class GroupSyncStats(BaseModel):
    group: str
    listed: int = 0
    new_messages: int = 0
    duplicates_skipped: int = 0
    failed_messages: int = 0


class SyncStats(BaseModel):
    run_id: Optional[str] = None
    total_fetched: int = 0
    new_messages: int = 0
    duplicates_skipped: int = 0
    failed_messages: int = 0
    attachments_legacy_copied: int = 0
    attachments_downloaded: int = 0
    attachments_skipped: int = 0
    groups: list[GroupSyncStats] = []
    seconds: float = 0.0
    finished_at: Optional[datetime] = None


class JobStatus(BaseModel):
    kind: str
    run_id: Optional[str] = None
    state: str = Field("idle", description="idle | running | completed | failed")
    message: str = ""
    counters: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
