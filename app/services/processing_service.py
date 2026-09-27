"""Step 2 - ``POST /api/gmail/process-pending`` (and single-email retry).

Pipeline per email (hybrid: deterministic rules + LLM for offer candidates):

    PENDING -> PROCESSING -> MIME/text handoff -> placement_pipeline
    classify+extract -> spec taxonomy mapping -> Pydantic-validated rows
    -> delete-this-email's-old-rows -> insert -> PROCESSED | FAILED

Hybrid rule (see ``app.llm``):

* **not** a final-selection candidate -> deterministic extraction only,
  ``method='rule_based'`` - this path is untouched.
* candidate + LLM answered -> the LLM's schema-validated JSON is the source
  of truth; the deterministic output for the same email is still computed and
  stored as audit signals (``det:*`` vs ``llm:*``) but never blocks the write.
  ``NOT_FINAL_SELECTION`` / ``UNCERTAIN`` produce **no** offer row and **no**
  ``FINAL_SELECTED``/``OFFERED`` event. ``method='llm'``.
* candidate + every provider/account failed -> the deterministic result is
  written and clearly marked ``method='rule_based_fallback'``; the email goes
  back to ``PENDING`` so the next run retries it.

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
from app.classifiers.taxonomy import classify_taxonomy, is_final_selection_candidate
from app.config import Settings
from app.extractors.events import build_events
from app.extractors.llm_offers import (
    METHOD_RULE_FALLBACK,
    audit_signals,
    build_llm_events,
    build_llm_offer,
    deterministic_statuses,
    resolve_company_id,
)
from app.extractors.offers import build_offer
from app.extractors.opportunities import build_opportunity
from app.extractors.shortlists import build_shortlist
from app.llm import LLMUnavailable, get_service, stats_snapshot
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

    # ------------------------------------------------------------------ #
    # Hybrid layer: the LLM is authoritative ONLY for final-selection
    # candidates.  Everything else keeps the deterministic-only path.
    # ------------------------------------------------------------------ #
    candidate = is_final_selection_candidate(
        ext, taxonomy.category, subject=row.subject, body=row.body_text
    )
    llm_call = None
    llm_error: Optional[str] = None
    if candidate and settings.hybrid.enabled:
        try:
            llm_call = get_service(settings.hybrid).extract(
                subject=row.subject, body=row.body_text
            )
        except LLMUnavailable as exc:
            llm_error = exc.reason
            log_event(
                log,
                "process.llm_unavailable",
                level=logging.WARNING,
                email_id=row.id,
                reason=exc.reason[:200],
            )

    llm_final = llm_call is not None and llm_call.extraction.is_final()
    llm_suppress = llm_call is not None and not llm_final

    if not candidate:
        method = "rule_based"
    elif llm_call is not None:
        method = "llm"
    elif llm_error is not None:
        method = METHOD_RULE_FALLBACK
    else:
        # candidate, but the hybrid layer is switched off -> rules only
        method = "rule_based"

    det_statuses = deterministic_statuses(ext, row.subject)
    llm_company = llm_call.extraction.company if llm_call else None

    _delete_derived(session, row.id)  # idempotent: rebuild from scratch

    company_id = resolve_company_id(session, ext, llm_company)
    counts = dict(_EMPTY_ROWS)
    shortlist: Optional[ShortlistEvent] = None

    if llm_final:
        # LLM authoritative: the model's student list IS the offer list.
        offer, offer_students = build_llm_offer(
            llm_call.extraction,
            email_id=row.id,
            company_id=company_id,
            subject=row.subject,
            body=row.body_text,
            ext=ext,
            method=method,
        )
        session.add(offer)
        session.flush()
        for student in offer_students:
            student.offer_id = offer.id
            session.add(student)
        counts["offers"] = 1
        counts["offer_students"] = len(offer_students)

    elif ext.category == Category.OFFER and llm_suppress:
        # LLM said NOT_FINAL_SELECTION / UNCERTAIN: no offer row at all, so
        # no FINAL_SELECTED/OFFERED record can be produced from this email.
        pass

    elif ext.category == Category.OFFER:
        # Deterministic offer kept: hybrid disabled, or every LLM account
        # failed (method already marks it ``rule_based_fallback``).
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

    if llm_final:
        events = build_llm_events(
            llm_call.extraction,
            email_id=row.id,
            company_id=company_id,
            subject=row.subject,
            received_at=row.received_at,
            method=method,
        )
    elif ext.category == Category.OFFER and llm_suppress:
        events = []  # the fix: suppressed rows never reach the timeline
    else:
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

    # ------------------------------------------------------------------ #
    # Classification: the LLM verdict wins for candidates; the deterministic
    # label survives as an audit signal either way.
    # ------------------------------------------------------------------ #
    category = taxonomy.category
    confidence = taxonomy.confidence
    if llm_final:
        category = "FINAL_SELECTION"
        confidence = llm_call.extraction.confidence
    elif llm_suppress and taxonomy.category == "FINAL_SELECTION":
        if llm_call.extraction.email_type == "NOT_FINAL_SELECTION":
            # Explicit verdict: this is not a final-selection email.
            category = "UNKNOWN"
            confidence = llm_call.extraction.confidence
        # UNCERTAIN keeps the deterministic label (no records either way).

    signals = list(taxonomy.signals)
    if candidate:
        # Audit trail only exists for emails the LLM was asked about - the
        # deterministic-only path keeps its signals byte-for-byte unchanged.
        signals += audit_signals(
            det_category=taxonomy.category,
            det_offer_rows=len(ext.students) if ext.category == Category.OFFER else 0,
            det_statuses=det_statuses,
            call=llm_call,
            error=llm_error,
            method=method,
            low_confidence=bool(
                llm_call is not None
                and llm_call.extraction.confidence < settings.hybrid.low_confidence
            ),
            written_offers=counts["offers"],
            written_events=counts["student_placement_events"],
        )

    row.classification = category
    row.classification_confidence = confidence
    row.classification_signals = signals[:40]
    row.classification_method = method

    return {
        "category": category,
        "rows": counts,
        "signals": signals,
        "method": method,
        "llm_unavailable": llm_error is not None,
    }


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
        if outcome.get("llm_unavailable"):
            # Deterministic rows were kept (method=rule_based_fallback); the
            # email goes back to PENDING so the next run can retry the LLM.
            row.processing_status = EmailStatus.PENDING
            row.error_message = (
                "LLM unavailable for this run - deterministic result kept, "
                "queued for automatic retry"
            )[:2000]
            row.retry_count = (row.retry_count or 0) + 1
        else:
            row.processing_status = EmailStatus.PROCESSED
            row.error_message = None
        session.commit()
        log_event(
            log,
            "process.email",
            email_id=row.id,
            category=outcome["category"],
            rows=sum(outcome["rows"].values()),
            method=outcome.get("method"),
            requeued=bool(outcome.get("llm_unavailable")),
        )
        return {
            "email_id": row.id,
            "gmail_message_id": row.gmail_message_id,
            "status": (
                EmailStatus.PENDING
                if outcome.get("llm_unavailable")
                else EmailStatus.PROCESSED
            ),
            "category": outcome["category"],
            "error": None,
            "rows_written": outcome["rows"],
            "method": outcome.get("method"),
            "requeued": bool(outcome.get("llm_unavailable")),
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
        "requeued_for_llm_retry": 0,
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
            if outcome.get("requeued"):
                # Deterministic fallback written; retried next run.
                stats["succeeded"] += 1
                stats["requeued_for_llm_retry"] += 1
                category = outcome["category"] or "UNKNOWN"
                stats["by_category"][category] = (
                    stats["by_category"].get(category, 0) + 1
                )
                for key, value in outcome["rows_written"].items():
                    stats["rows_written"][key] = (
                        stats["rows_written"].get(key, 0) + value
                    )
            elif outcome["status"] == EmailStatus.PROCESSED:
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
    # Router counters (calls, failovers, tokens) for the run's own report.
    if settings.hybrid.enabled:
        stats["llm"] = stats_snapshot()
    log_event(
        log,
        "process.completed",
        seconds=stats["seconds"],
        total_pending=stats["total_pending"],
        processed=stats["processed"],
        succeeded=stats["succeeded"],
        failed=stats["failed"],
        requeued=stats["requeued_for_llm_retry"],
        by_category=stats["by_category"],
        rows_written=stats["rows_written"],
        llm=stats.get("llm"),
    )
    return stats
