"""Step 2 - POST /api/gmail/process-pending: classification, extraction,
error isolation, idempotency and the status machine.

Synthetic bodies below were verified against the real parser
(``extract_email`` + ``classify_taxonomy``) before being locked in here.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.classifiers.taxonomy import TAXONOMY
from app.models import (
    Email,
    EmailStatus,
    FunnelCountRow,
    Offer,
    OfferStudent,
    Opportunity,
    ShortlistEvent,
    ShortlistStudent,
    StudentPlacementEvent,
    StudentStatus,
)

OFFER_SUBJECT = "Acme Corporation - Final Offers - 2027 Batch"
OFFER_BODY = (
    "Dear All,\n\n"
    "Congratulations! The following students of B.Tech 2027 batch have "
    "been selected for full time roles at Acme Corporation.\n\n"
    "S.No. | Roll No | Name | CTC (per annum)\n"
    "1 | 21103001 | Kartik Goel | 650000\n"
    "2 | 21103002 | Aarav Sharma | 650000\n\n"
    "All selected students are required to submit their documents on or "
    "before 15 Oct 2026.\n\nRegards,\nTraining & Placement Cell\n"
)

SHORTLIST_SUBJECT = "Acme Corporation - Shortlisted Students & Selection Process"
SHORTLIST_BODY = (
    "Dear All,\n\n"
    "The following students have been shortlisted for the next round of "
    "the selection process for Acme Corporation.\n\n"
    "1. Kartik Goel - 21103001\n"
    "2. Aarav Sharma - 21103002\n\n"
    "Reporting time: 10:00 AM, Venue: Hall 1. Please be on time.\n\n"
    "Regards,\nT&P Cell\n"
)

FUNNEL_SUBJECT = "Acme Mass Recruitment Drive - Pending Registration | Deadline 6 Sep"
FUNNEL_BODY = (
    "Kind attention to the aspirants of Acme Mass Recruitment Drive - "
    "Hiring for Full Time Role from 2027 Batch:\n\n"
    "Please find attached the list of 393 eligible students, as received "
    "from Acme, who are yet to complete their registration on the Acme "
    "portal.\n\nThe registration window will close on 6 September at "
    "10:00 PM.\n\nRegards,\nT&P Cell\n"
)

WEBINAR_SUBJECT = "AI Agents Webinar - 2027 Batch - Register"
WEBINAR_BODY = (
    "Dear Students,\n\n"
    "Join our webinar on 'Beginners guide to working with AI Agents' on "
    "20 Oct 2026, 5:00 PM.\n\nRegister here: https://example.com/webinar\n"
)


def _process(client, payload: dict | None = None) -> dict:
    response = client.post("/api/gmail/process-pending", json=payload or {})
    assert response.status_code == 200
    return response.json()["data"]


def _derived_counts(session) -> dict[str, int]:
    return {
        "offers": session.execute(
            select(func.count()).select_from(Offer)
        ).scalar_one(),
        "offer_students": session.execute(
            select(func.count()).select_from(OfferStudent)
        ).scalar_one(),
        "shortlist_events": session.execute(
            select(func.count()).select_from(ShortlistEvent)
        ).scalar_one(),
        "shortlist_students": session.execute(
            select(func.count()).select_from(ShortlistStudent)
        ).scalar_one(),
        "funnel_counts": session.execute(
            select(func.count()).select_from(FunnelCountRow)
        ).scalar_one(),
        "opportunities": session.execute(
            select(func.count()).select_from(Opportunity)
        ).scalar_one(),
        "events": session.execute(
            select(func.count()).select_from(StudentPlacementEvent)
        ).scalar_one(),
    }


def test_offer_email_extracts_rows_and_lifecycle_events(
    client, session, insert_email
):
    insert_email(
        gmail_message_id="gm-offer",
        subject=OFFER_SUBJECT,
        body_text=OFFER_BODY,
    )

    stats = _process(client)
    assert stats["succeeded"] == 1 and stats["failed"] == 0
    assert stats["by_category"] == {"FINAL_SELECTION": 1}

    row = session.scalar(select(Email).where(Email.gmail_message_id == "gm-offer"))
    assert row.processing_status == EmailStatus.PROCESSED
    assert row.classification == "FINAL_SELECTION"
    assert row.classification in TAXONOMY
    # LLM fallback is disabled by default: pure deterministic provenance.
    assert row.classification_method == "rule_based"
    assert row.classification_signals  # evidence trail stored

    offer = session.scalar(select(Offer))
    assert offer is not None
    assert session.scalar(select(func.count()).select_from(OfferStudent)) == 2

    events = session.scalars(select(StudentPlacementEvent)).all()
    assert len(events) == 2
    assert {e.event_type for e in events} <= {"offer", "final_selection"}
    allowed = {
        StudentStatus.REGISTERED,
        StudentStatus.ELIGIBLE,
        StudentStatus.SHORTLISTED,
        StudentStatus.FINAL_SELECTED,
        StudentStatus.OFFERED,
        StudentStatus.REJECTED,
        StudentStatus.DISQUALIFIED,
        StudentStatus.UNKNOWN,
    }
    # Spec: never invent JOINED; lifecycle statuses come from the source.
    assert {e.normalized_status for e in events} <= allowed
    assert all(e.roll_no for e in events)  # student identity = roll_no


def test_shortlist_email_extracts_named_rows(client, session, insert_email):
    insert_email(
        gmail_message_id="gm-shortlist",
        subject=SHORTLIST_SUBJECT,
        body_text=SHORTLIST_BODY,
    )

    stats = _process(client)
    assert stats["by_category"] == {"SHORTLIST": 1}
    assert stats["rows_written"]["shortlist_events"] == 1
    assert stats["rows_written"]["shortlist_students"] == 2

    event = session.scalar(select(ShortlistEvent))
    assert event is not None
    students = session.scalars(select(ShortlistStudent)).all()
    assert {s.roll_no for s in students} == {"21103001", "21103002"}
    # stage enum normalized, raw wording preserved
    assert event.stage
    assert event.stage_raw
    assert len(session.scalars(select(StudentPlacementEvent)).all()) == 2


def test_funnel_email_stores_counts_and_registration_label(
    client, session, insert_email
):
    insert_email(
        gmail_message_id="gm-funnel",
        subject=FUNNEL_SUBJECT,
        body_text=FUNNEL_BODY,
    )

    stats = _process(client)
    # 14-value taxonomy: registration-stage counts are REGISTRATION even
    # though the parser's coarse category is SHORTLIST (hybrid rule).
    assert stats["by_category"] == {"REGISTRATION": 1}
    funnel = session.scalars(select(FunnelCountRow)).all()
    assert [f.count for f in funnel] == [393]
    assert session.scalar(select(func.count()).select_from(ShortlistEvent)) == 1
    # No student list -> no per-student rows (never invent students).
    assert session.scalar(select(func.count()).select_from(ShortlistStudent)) == 0
    assert session.scalar(select(func.count()).select_from(StudentPlacementEvent)) == 0


def test_opportunity_email_webinar_with_link(client, session, insert_email):
    insert_email(
        gmail_message_id="gm-webinar",
        subject=WEBINAR_SUBJECT,
        body_text=WEBINAR_BODY,
    )

    stats = _process(client)
    assert stats["by_category"] == {"WEBINAR": 1}
    opp = session.scalar(select(Opportunity))
    assert opp is not None
    assert opp.event_type == "WEBINAR"
    assert "https://example.com/webinar" in (
        str(opp.links) + (opp.registration_link or "")
    )


def test_per_email_error_isolation(client, session, insert_email, monkeypatch):
    """A crash in one email's parsing never affects its neighbours.

    No natural corpus input reliably crashes the hardened parser, so the
    crash is simulated at the parser boundary (clearly labelled); everything
    around it - status machine, rollback, counters, retry endpoint - is the
    real production path.
    """
    import app.services.processing_service as processing_module

    original = processing_module.extract_email

    def exploding(pipeline_email, attachment_texts):
        if pipeline_email.subject == "Acme Corporation - Final Offers (crashes)":
            raise RuntimeError("simulated parser crash")
        return original(pipeline_email, attachment_texts)

    monkeypatch.setattr(processing_module, "extract_email", exploding)

    insert_email(gmail_message_id="gm-good", subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    insert_email(
        gmail_message_id="gm-broken",
        subject="Acme Corporation - Final Offers (crashes)",
        body_text=OFFER_BODY,
    )

    stats = _process(client)
    assert stats["processed"] == 2
    assert stats["succeeded"] == 1
    assert stats["failed"] == 1

    good = session.scalar(select(Email).where(Email.gmail_message_id == "gm-good"))
    broken = session.scalar(
        select(Email).where(Email.gmail_message_id == "gm-broken")
    )
    assert good.processing_status == EmailStatus.PROCESSED
    assert broken.processing_status == EmailStatus.FAILED
    assert "simulated parser crash" in (broken.error_message or "")
    assert broken.retry_count == 1
    # Only the good email's rows exist (failed run rolled back cleanly).
    assert session.scalar(select(func.count()).select_from(Offer)) == 1
    assert session.scalar(select(func.count()).select_from(StudentPlacementEvent)) == 2

    # The single-message retry endpoint surfaces the failure honestly.
    retry = client.post("/api/gmail/messages/gm-broken/process")
    assert retry.status_code == 200
    assert retry.json()["data"]["status"] == "FAILED"
    assert retry.json()["success"] is False


def test_processing_is_idempotent_across_runs(client, session, insert_email):
    insert_email(gmail_message_id="gm-1", subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    insert_email(
        gmail_message_id="gm-2", subject=SHORTLIST_SUBJECT, body_text=SHORTLIST_BODY
    )
    insert_email(
        gmail_message_id="gm-3", subject=FUNNEL_SUBJECT, body_text=FUNNEL_BODY
    )
    insert_email(
        gmail_message_id="gm-4", subject=WEBINAR_SUBJECT, body_text=WEBINAR_BODY
    )

    first = _process(client)
    assert first["succeeded"] == 4
    counts_run1 = _derived_counts(session)

    # Reset the queue and process everything again (delete-then-rebuild).
    session.execute(
        Email.__table__.update().values(processing_status=EmailStatus.PENDING)
    )
    session.commit()
    second = _process(client)
    assert second["succeeded"] == 4
    counts_run2 = _derived_counts(session)
    assert counts_run1 == counts_run2
    assert counts_run1["offers"] == 1
    assert counts_run1["shortlist_events"] == 2  # named list + funnel event
    assert counts_run1["opportunities"] == 1


def test_stale_processing_status_is_recovered(client, session, insert_email):
    insert_email(
        gmail_message_id="gm-stale",
        subject=OFFER_SUBJECT,
        body_text=OFFER_BODY,
        processing_status=EmailStatus.PROCESSING,  # crash before commit
    )

    stats = _process(client)
    assert stats["total_pending"] == 1
    assert stats["succeeded"] == 1
    row = session.scalar(select(Email).where(Email.gmail_message_id == "gm-stale"))
    assert row.processing_status == EmailStatus.PROCESSED


def test_second_run_reports_zero_pending(client, session, insert_email):
    insert_email(gmail_message_id="gm-once", subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    first = _process(client)
    assert first["total_pending"] == 1
    assert first["succeeded"] == 1

    # Nothing left in the queue: a run with zero pending is a no-op, not an
    # error, and it never rewrites already-processed rows.
    stats = _process(client)
    assert stats["total_pending"] == 0
    assert stats["processed"] == 0
    counts = _derived_counts(session)
    assert counts["offers"] == 1
