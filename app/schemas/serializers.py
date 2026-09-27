"""Row -> schema serializers (one place that knows response shapes)."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Email,
    EmailAttachment,
    FunnelCountRow,
    Offer,
    Opportunity,
    ShortlistEvent,
    StudentPlacementEvent,
)
from app.schemas.messages import (
    AttachmentOut,
    FunnelCountOut,
    MessageDetail,
    MessageSummary,
    OfferOut,
    OfferStudentOut,
    OpportunityLink,
    OpportunityOut,
    ShortlistEventOut,
    ShortlistStudentOut,
    StudentEventOut,
)

BODY_CAP = 50_000


def company_names(session: Session, ids: Iterable[Optional[str]]) -> dict[str, str]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = session.execute(
        select(Company.id, Company.name).where(Company.id.in_(wanted))
    ).all()
    return dict(rows)


def offer_out(offer: Offer, names: dict[str, str]) -> OfferOut:
    return OfferOut(
        id=offer.id,
        company_id=offer.company_id,
        company_name=names.get(offer.company_id or ""),
        role=offer.role,
        employment_type=offer.employment_type,
        duration=offer.duration,
        stipend=int(offer.stipend) if offer.stipend is not None else None,
        ctc_total=int(offer.ctc_total) if offer.ctc_total is not None else None,
        ctc_raw=offer.ctc_raw,
        ctc_basis=offer.ctc_basis,
        location=offer.location,
        deadline=offer.deadline,
        evidence=offer.evidence,
        confidence=offer.confidence or 0.0,
        method=offer.method,
        students=[
            OfferStudentOut(
                roll_no=s.roll_no,
                name=s.name,
                branch=s.branch,
                program=s.program,
                college=s.college,
                email=s.email,
                role=s.role,
                status_raw=s.status_raw,
            )
            for s in offer.students
        ],
    )


def shortlist_out(event: ShortlistEvent, names: dict[str, str]) -> ShortlistEventOut:
    return ShortlistEventOut(
        id=event.id,
        company_id=event.company_id,
        company_name=names.get(event.company_id or ""),
        stage=event.stage,
        stage_raw=event.stage_raw,
        venue=event.venue,
        reporting_at=event.reporting_at,
        selection_process=list(event.selection_process or []),
        interview_dates=list(event.interview_dates or []),
        deadline=event.deadline,
        evidence=event.evidence,
        confidence=event.confidence or 0.0,
        method=event.method,
        students=[
            ShortlistStudentOut(
                roll_no=s.roll_no,
                name=s.name,
                branch=s.branch,
                program=s.program,
                college=s.college,
                status_raw=s.status_raw,
            )
            for s in event.students
        ],
    )


def funnel_out(row: FunnelCountRow) -> FunnelCountOut:
    return FunnelCountOut(
        round_name=row.round_name,
        round_order=row.round_order,
        count=row.count,
        evidence=row.evidence,
        confidence=row.confidence or 0.0,
        method=row.method,
    )


def opportunity_out(
    opp: Opportunity,
    names: dict[str, str],
    *,
    subject: Optional[str] = None,
    received_at=None,
) -> OpportunityOut:
    return OpportunityOut(
        id=opp.id,
        email_id=opp.email_id,
        company_id=opp.company_id,
        organization_name=opp.organization_name,
        event_name=opp.event_name,
        event_type=opp.event_type,
        stages=list(opp.stages or []),
        eligibility=list(opp.eligibility or []),
        team_rules=list(opp.team_rules or []),
        links=[OpportunityLink(**link) for link in (opp.links or [])],
        registration_link=opp.registration_link,
        deadline=opp.deadline,
        career_note=opp.career_note,
        is_revision_of=opp.is_revision_of,
        evidence=opp.evidence,
        confidence=opp.confidence or 0.0,
        method=opp.method,
        received_at=received_at,
        subject=subject,
    )


def event_out(
    event: StudentPlacementEvent, names: dict[str, str], *, received_at=None
) -> StudentEventOut:
    return StudentEventOut(
        id=event.id,
        roll_no=event.roll_no,
        name=event.name,
        company_id=event.company_id,
        company_name=names.get(event.company_id or ""),
        event_type=event.event_type,
        stage=event.stage,
        normalized_status=event.normalized_status,
        event_date=event.event_date,
        source_text=event.source_text,
        confidence=event.confidence or 0.0,
        method=event.method,
        received_at=received_at,
    )


def message_summary(row: Email) -> MessageSummary:
    return MessageSummary(
        id=row.id,
        gmail_message_id=row.gmail_message_id,
        thread_id=row.thread_id,
        subject=row.subject or "",
        sender=row.sender,
        sender_email=row.sender_email,
        source_group=row.source_group or row.source_group_email,
        received_at=row.received_at,
        processing_status=row.processing_status,
        classification=row.classification,
        classification_confidence=row.classification_confidence,
        has_attachments=bool(row.has_attachments),
        is_canonical=bool(row.is_canonical),
        dedup_of=row.dedup_of,
        revision_of=row.revision_of,
        retry_count=row.retry_count or 0,
        error_message=row.error_message,
        created_at=row.created_at,
    )


def message_detail(session: Session, row: Email) -> MessageDetail:
    body = row.body_text or ""
    truncated = len(body) > BODY_CAP

    attachments = list(
        session.scalars(
            select(EmailAttachment).where(EmailAttachment.email_id == row.id)
        )
    )
    offer = session.scalar(select(Offer).where(Offer.email_id == row.id))
    shortlists = list(
        session.scalars(
            select(ShortlistEvent)
            .where(ShortlistEvent.email_id == row.id)
            .order_by(ShortlistEvent.created_at)
        )
    )
    funnels = list(
        session.scalars(
            select(FunnelCountRow)
            .where(FunnelCountRow.email_id == row.id)
            .order_by(FunnelCountRow.round_order)
        )
    )
    opportunities = list(
        session.scalars(select(Opportunity).where(Opportunity.email_id == row.id))
    )
    events = list(
        session.scalars(
            select(StudentPlacementEvent)
            .where(StudentPlacementEvent.email_id == row.id)
            .order_by(StudentPlacementEvent.created_at)
        )
    )

    names = company_names(
        session,
        [r.company_id for r in (offer, *shortlists, *opportunities, *events) if r],
    )

    summary = message_summary(row).model_dump()
    return MessageDetail(
        **summary,
        message_id_header=row.message_id_header,
        in_reply_to=row.in_reply_to,
        recipient=row.recipient,
        cc=row.cc,
        received_raw=row.received_raw,
        source_group_email=row.source_group_email,
        cluster_key=row.cluster_key,
        classification_signals=list(row.classification_signals or []),
        classification_method=row.classification_method,
        snippet=row.snippet,
        body_text=body[:BODY_CAP],
        body_truncated=truncated,
        label_ids=list(row.label_ids or []),
        attachments=[
            AttachmentOut(
                id=a.id,
                filename=a.filename,
                mime_type=a.mime_type,
                file_size=a.file_size,
                method=a.method,
                has_text=bool(a.extracted_text),
            )
            for a in attachments
        ],
        offer=offer_out(offer, names) if offer else None,
        shortlists=[shortlist_out(s, names) for s in shortlists],
        funnel_counts=[funnel_out(f) for f in funnels],
        opportunities=[opportunity_out(o, names) for o in opportunities],
        events=[event_out(e, names, received_at=row.received_at) for e in events],
    )
