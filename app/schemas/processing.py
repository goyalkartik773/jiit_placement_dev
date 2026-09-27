"""Schemas for Step 2 (processing) and single-email retry."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProcessPendingRequest(BaseModel):
    limit: Optional[int] = Field(
        None, ge=1, le=10000, description="Process at most N pending emails"
    )


class ProcessStats(BaseModel):
    run_id: Optional[str] = None
    total_pending: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    by_category: dict[str, int] = Field(
        default_factory=dict, description="Spec taxonomy counts (successes only)"
    )
    rows_written: dict[str, int] = Field(
        default_factory=dict, description="Rows committed this run, per table"
    )
    seconds: float = 0.0
    finished_at: Optional[datetime] = None


class MessageProcessResult(BaseModel):
    email_id: str
    gmail_message_id: str
    status: str = Field(description="PROCESSED | FAILED")
    category: Optional[str] = None
    error: Optional[str] = None
    rows_written: dict[str, int] = Field(default_factory=dict)
