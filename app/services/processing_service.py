"""Step 2 - ``POST /api/gmail/process-pending`` (and single-email retry).

Pipeline per email (fully deterministic; LLM fallback optional):

    PENDING -> PROCESSING -> MIME/text handoff -> placement_pipeline
    classify+extract -> spec taxonomy mapping -> Pydantic-validated rows
    -> delete-this-email's-old-rows -> insert -> PROCESSED | FAILED

Guarantees:

* **Idempotent** - derived rows are deleted and rebuilt per email, so
  reprocessing converges to identical row counts (never duplicates).
* **Error isolation** - one broken email becomes FAILED (+error_message,
  retry_count) and the batch continues.
* **Honest counters** - ``by_category`` counts only successfully processed
  emails; ``rows_written`` only counts rows committed.
* Stale ``PROCESSING`` rows (interrupted runs) are reset to ``PENDING`` at
  run start - only one processing run can exist at a time (JobRunner lock).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from placement_pipeline.dedup import deduplicate
from placement_pipeline.ingest import extract_email
from placement_pipeline.models import Category, FunnelCount

from app.classifiers.llm_fallback import extract_funnel_counts
from app.classifiers.taxonomy import classify_taxonomy
from app.config import Settings
from app.extractors.companies import get_or_create_company
from app.extractors.events import build_events
from app.extractors.offers import build_offer
from app.extractors.opportunities import build_opportunity
from app.extractors.shortlists import build_shortlist
from app.models import (
    Email,
    EmailAttachment,
    EmailStatus,
    FunnelCountRow,
    Offer,
    Opportunity,
    ShortlistEvent,
    StudentPlacementEvent,
)
from app.parsers import email_adapter
from app.repositories import email_repo
from app.utils.logging import log_event

log = logging.getLogger("app.process")

_EMPTY_ROWS = {
    "offers": 0,
    "offer_students": 0,
    "shortlist_events": 0,
    "shortlist_students": 0,
    "funnel_counts": 0,
    "opportunities": 0,
    "student_placement_events": 0,
}


def _delete_derived(session: Session, email_id: str) -> None:
    """Remove this email's previous extracted rows (children cascade in DB)."""
    session.execute(
        delete(StudentPlacementEvent).where(StudentPlacementEvent.email_id == email_id)
    )
    session.execute(delete(FunnelCountRow).where(FunnelCountRow.email_id == email_id))
    session.execute(delete(Opportunity).where(Opportunity.email_id == email_id))
    session.execute(delete(ShortlistEvent).where(ShortlistEvent.email_id == email_id))
    session.execute(delete(Offer).where(Offer.email_id == email_id))
    session.commit()


def _link_cluster(session: Session, row: Email) -> None:
    """Refresh canonical/dedup/revision links for this subject+sender cluster.

    Runs cross-run (the canonical may have been processed in an earlier
    batch): revisions are linked via ``is_revision_of`` instead of being
    double-counted, while distinct events never share a cluster key.
    """
    if not row.cluster_key:
        return
    members = list(
        session.scalars(
            select(Email).where(
                Email.cluster_key == row.cluster_key, Email.id != row.id
            )
        )
    )
    if not members:
        return
    members.append(row)
    decisions = deduplicate([email_adapter.member_for_dedup(m) for m in members])
    for member in members:
        decision = decisions.get(member.id)
        if decision is None:
            continue
        member.is_canonical = decision.is_canonical
        member.dedup_of = decision.dedup_of
        member.revision_of = decision.revision_of
    session.commit()


def _attachment_texts(session: Session, email_id: str) -> list[str]:
    rows = session.scalars(
        select(EmailAttachment.extracted_text).where(
            EmailAttachment.email_id == email_id,
            EmailAttachment.extracted_text.is_not(None),
        )
    )
    return [text for text in rows if text]


def _extract_and_store(session: Session, row: Email, settings: Settings) -> dict:
    _link_cluster(session, row)  # first: row.revision_of feeds opportunities

    pipeline_email = email_adapter.to_pipeline_email(row)
    result = extract_email(pipeline_email, _attachment_texts(session, row.id))
    ext = result.extraction

    # Optional LLM fallback - only genuinely ambiguous free-prose funnels.
    funnel_method = "rule_based"
    if (
        settings.llm_enabled
        and ext.category == Category.SHORTLIST
        and not ext.students
        and not ext.funnel_counts
    ):
        llm_rows = extract_funnel_counts(settings, row.subject, row.body_text)
        if llm_rows:
            ext.funnel_counts = [
                FunnelCount(
                    stage=item["round_name"],
                    count=item["count"],
                    sentence=item.get("evidence", ""),
                )
                for item in llm_rows
            ]
            funnel_method = "llm"

    taxonomy = classify_taxonomy(ext, subject=row.subject, body=row.body_text)

    _delete_derived(session, row.id)  # idempotent: rebuild from scratch

    company = get_or_create_company(session, ext)
    company_id = company.id if company else None
    counts = dict(_EMPTY_ROWS)
    shortlist: Optional[ShortlistEvent] = None

    if ext.category == Category.OFFER:
        offer, offer_students = build_offer(
            ext,
            email_id=row.id,
            company_id=company_id,
            subject=row.subject,
            body=row.body_text,
        )
        session.add(offer)
        session.flush()
        for student in offer_students:
            student.offer_id = offer.id
            session.add(student)
        counts["offers"] = 1
        counts["offer_students"] = len(offer_students)

    elif ext.category == Category.SHORTLIST:
        shortlist, shortlist_students, funnels = build_shortlist(
            ext,
            email_id=row.id,
            company_id=company_id,
            subject=row.subject,
            body=row.body_text,
            funnel_method=funnel_method,
        )
        session.add(shortlist)
        session.flush()
        for student in shortlist_students:
            student.shortlist_event_id = shortlist.id
            session.add(student)
        for funnel in funnels:
            session.add(funnel)
        counts["shortlist_events"] = 1
        counts["shortlist_students"] = len(shortlist_students)
        counts["funnel_counts"] = len(funnels)

    elif ext.category == Category.OPPORTUNITY:
        opportunity = build_opportunity(
            ext,
            email_id=row.id,
            company_id=company_id,
            subject=row.subject,
            body=row.body_text,
            event_type=taxonomy.category,
            is_revision_of=row.revision_of,
        )
        session.add(opportunity)
        counts["opportunities"] = 1

    events = build_events(
        ext,
        email_id=row.id,
        company_id=company_id,
        subject=row.subject,
        received_at=row.received_at,
        shortlist=shortlist,
    )
    for event in events:
        session.add(event)
    counts["student_placement_events"] = len(events)

    row.classification = taxonomy.category
    row.classification_confidence = taxonomy.confidence
    row.classification_signals = taxonomy.signals[:20]
    row.classification_method = taxonomy.method

    return {"category": taxonomy.category, "rows": counts, "signals": taxonomy.signals}


def process_one(session: Session, email_id: str, settings: Settings) -> dict:
    """Process a single email with full error isolation (never raises for
    extraction failures; raises :class:`LookupError` only when missing)."""
    row = session.get(Email, email_id)
    if row is None:
        raise LookupError(f"email {email_id} not found")

    row.processing_status = EmailStatus.PROCESSING
    row.error_message = None
    session.commit()

    try:
        outcome = _extract_and_store(session, row, settings)
        row.processing_status = EmailStatus.PROCESSED
        row.error_message = None
        session.commit()
        log_event(
            log,
            "process.email",
            email_id=row.id,
            category=outcome["category"],
            rows=sum(outcome["rows"].values()),
        )
        return {
            "email_id": row.id,
            "gmail_message_id": row.gmail_message_id,
            "status": EmailStatus.PROCESSED,
            "category": outcome["category"],
            "error": None,
            "rows_written": outcome["rows"],
        }
    except Exception as exc:
        session.rollback()
        fresh = session.get(Email, email_id)
        if fresh is not None:
            fresh.processing_status = EmailStatus.FAILED
            fresh.error_message = f"{type(exc).__name__}: {exc}"[:2000]
            fresh.retry_count = (fresh.retry_count or 0) + 1
            session.commit()
        log_event(
            log,
            "process.email_failed",
            level=logging.WARNING,
            email_id=email_id,
            subject=(row.subject or "")[:120],
            error=type(exc).__name__,
            detail=str(exc)[:400],
        )
        return {
            "email_id": email_id,
            "gmail_message_id": row.gmail_message_id,
            "status": EmailStatus.FAILED,
            "category": None,
            "error": f"{type(exc).__name__}: {exc}"[:400],
            "rows_written": {},
        }


def run_processing(
    *, session_factory, handle, payload, settings: Settings
) -> dict:
    """Process the PENDING queue (oldest first, optional ``limit``)."""
    started = time.perf_counter()
    session = session_factory()
    stats: dict = {
        "total_pending": 0,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "by_category": {},
        "rows_written": dict(_EMPTY_ROWS),
    }
    try:
        # Crash recovery: nothing can legitimately be PROCESSING right now
        # (JobRunner allows only one processing run at a time).
        session.execute(
            update(Email)
            .where(Email.processing_status == EmailStatus.PROCESSING)
            .values(processing_status=EmailStatus.PENDING)
        )
        session.commit()

        ids = email_repo.pending_ids(session, payload.limit)
        stats["total_pending"] = len(ids)
        handle.update(message="processing queued", total_pending=len(ids))

        for index, email_id in enumerate(ids, 1):
            outcome = process_one(session, email_id, settings)
            stats["processed"] += 1
            if outcome["status"] == EmailStatus.PROCESSED:
                stats["succeeded"] += 1
                category = outcome["category"] or "UNKNOWN"
                stats["by_category"][category] = (
                    stats["by_category"].get(category, 0) + 1
                )
                for key, value in outcome["rows_written"].items():
                    stats["rows_written"][key] = (
                        stats["rows_written"].get(key, 0) + value
                    )
            else:
                stats["failed"] += 1
            handle.update(
                message=f"processing {index}/{len(ids)}",
                processed=stats["processed"],
                succeeded=stats["succeeded"],
                failed=stats["failed"],
            )
    finally:
        session.close()

    stats["seconds"] = round(time.perf_counter() - started, 3)
    stats["finished_at"] = datetime.now(timezone.utc)
    log_event(
        log,
        "process.completed",
        seconds=stats["seconds"],
        total_pending=stats["total_pending"],
        processed=stats["processed"],
        succeeded=stats["succeeded"],
        failed=stats["failed"],
        by_category=stats["by_category"],
        rows_written=stats["rows_written"],
    )
    return stats
