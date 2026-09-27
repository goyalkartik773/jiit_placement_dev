"""Email rows: idempotent inserts, status transitions, filtered listings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from placement_pipeline import dedup as pipeline_dedup
from placement_pipeline import normalize

from app.gmail.mime import MailMessage
from app.models import Email, EmailStatus


def cleaned_body(text: str) -> str:
    """Current-section clean body for display (never raises)."""
    try:
        parts = normalize.prepare_parts(text or "")
        return parts[0] if parts else (text or "")
    except Exception:
        return text or ""


def cluster_key_for(subject: str, sender_email: Optional[str]) -> str:
    """Same subject+sender cluster the parser uses for dedup/revision links."""
    return pipeline_dedup.cluster_key(subject or "", sender_email or "")


def get_by_gmail_message_id(session: Session, gmail_message_id: str) -> Optional[Email]:
    return session.scalar(
        select(Email).where(Email.gmail_message_id == gmail_message_id)
    )


def get_by_key(session: Session, key: str) -> Optional[Email]:
    """Lookup by internal uuid **or** Gmail message id (API accepts both)."""
    return session.scalar(
        select(Email).where(or_(Email.id == key, Email.gmail_message_id == key))
    )


def insert_mail(session: Session, mail: MailMessage) -> Email:
    """Stage a new PENDING row. ``IntegrityError`` bubbles up as the
    idempotency backstop (unique index on ``gmail_message_id``)."""
    row = Email(
        gmail_message_id=mail.gmail_message_id,
        thread_id=mail.thread_id,
        message_id_header=mail.message_id_header,
        in_reply_to=mail.in_reply_to,
        source_group=mail.source_group,
        source_group_email=mail.source_group_email,
        sender=mail.sender,
        sender_email=mail.sender_email,
        recipient=mail.recipient,
        cc=mail.cc,
        subject=mail.subject or "",
        received_raw=mail.received_raw,
        received_at=mail.received_at,
        body_text=mail.body_text or "",
        body_html=mail.body_html,
        body_clean=cleaned_body(mail.body_text or ""),
        snippet=mail.snippet,
        has_attachments=bool(mail.has_attachments),
        label_ids=list(mail.label_ids or []),
        cluster_key=cluster_key_for(mail.subject or "", mail.sender_email),
        processing_status=EmailStatus.PENDING,
    )
    session.add(row)
    session.flush()
    return row


def status_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Email.processing_status, func.count()).group_by(
            Email.processing_status
        )
    ).all()
    counts = {status: 0 for status in EmailStatus.ALL}
    counts.update({status: int(n) for status, n in rows})
    counts["TOTAL"] = sum(counts.values())
    return counts


def pending_ids(session: Session, limit: Optional[int] = None) -> list[str]:
    stmt = (
        select(Email.id)
        .where(Email.processing_status == EmailStatus.PENDING)
        .order_by(Email.received_at.asc().nulls_last(), Email.created_at.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def list_messages(
    session: Session,
    *,
    status: Optional[str] = None,
    classification: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Email], int]:
    """Filtered, paginated listing for the admin UI (no full bodies)."""
    filters = []
    if status:
        filters.append(Email.processing_status == status.upper())
    if classification:
        filters.append(Email.classification == classification.upper())
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(Email.subject.ilike(like), Email.sender.ilike(like),
                Email.gmail_message_id.ilike(like))
        )

    count_stmt = select(func.count()).select_from(Email)
    stmt = select(Email)
    for flt in filters:
        count_stmt = count_stmt.where(flt)
        stmt = stmt.where(flt)
    total = int(session.scalar(count_stmt) or 0)
    rows = list(
        session.scalars(
            stmt.order_by(Email.received_at.desc().nulls_last())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
    )
    return rows, total
