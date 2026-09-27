"""DB email rows -> placement_pipeline ``Email`` models (and back)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from placement_pipeline.models import Email as PipelineEmail

from app.models import Email as EmailRow

IST = ZoneInfo("Asia/Kolkata")


def ist_naive(value: datetime | None) -> datetime | None:
    """PG timestamptz -> IST wall-clock naive (legacy corpus semantics)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(IST).replace(tzinfo=None)


def to_pipeline_email(row: EmailRow) -> PipelineEmail:
    return PipelineEmail(
        id=row.id,
        gmail_message_id=row.gmail_message_id or "",
        source_group=row.source_group or row.source_group_email or "",
        sender=row.sender or "",
        sender_email=row.sender_email or "",
        subject=row.subject or "",
        received_raw=row.received_raw or "",
        received_at=ist_naive(row.received_at),
        body_text=row.body_text or "",
        has_attachments=bool(row.has_attachments),
        message_id_header=row.message_id_header,
        in_reply_to=row.in_reply_to,
    )


def member_for_dedup(row: EmailRow) -> PipelineEmail:
    """Minimal projection used only for cluster canonical/revision decisions."""
    return PipelineEmail(
        id=row.id,
        gmail_message_id=row.gmail_message_id or "",
        source_group="",
        sender="",
        sender_email=row.sender_email or "",
        subject=row.subject or "",
        received_raw=row.received_raw or "",
        received_at=ist_naive(row.received_at) or datetime(1970, 1, 1),
        body_text="",
    )
