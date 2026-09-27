"""Hybrid pipeline wiring: the LLM is authoritative for offer candidates.

Uses the real parser + real session; only the router is faked (no network).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

import app.services.processing_service as processing
from app.config import load_settings
from app.llm import LLMResult, LLMUnavailable
from app.llm.schema import FinalSelectionExtraction
from app.models import (
    EmailStatus,
    Offer,
    OfferStudent,
    ShortlistEvent,
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

FINAL_PAYLOAD = {
    "email_type": "FINAL_SELECTION",
    "company": "Acme Corporation",
    "role": "SDE",
    "stipend": None,
    "ctc_total": 650000,
    "location": "Noida",
    "students": [
        {"roll_number": "21103001", "name": "Kartik Goel", "program": "B.Tech", "branch": "CSE"}
    ],
    "evidence": "The following students ... have been selected for full time roles.",
    "confidence": 0.91,
}

NOT_FINAL_PAYLOAD = {
    "email_type": "NOT_FINAL_SELECTION",
    "company": None,
    "role": None,
    "stipend": None,
    "ctc_total": None,
    "location": None,
    "students": [],
    "evidence": "This email describes a shortlist, not a final offer.",
    "confidence": 0.86,
}


class _FakeService:
    """Stands in for ``app.llm.router.LLMService``."""

    def __init__(self, payload, *, account="gemini_1", failed_over=False):
        self.extraction = FinalSelectionExtraction.model_validate(payload)
        self.calls = 0

    def extract(self, *, subject: str, body: str) -> LLMResult:
        self.calls += 1
        return LLMResult(
            extraction=self.extraction,
            account_label="gemini_1",
            provider="gemini",
            failed_over=False,
            latency_ms=12,
        )


class _NeverCalled:
    def extract(self, *, subject: str, body: str):
        raise AssertionError("the LLM must not be called for a non-candidate")


class _AlwaysDown:
    def extract(self, *, subject: str, body: str):
        raise LLMUnavailable("gemini_1: quota; groq_1: auth; deepseek_1: auth")


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _events(session, status: str) -> list[StudentPlacementEvent]:
    return list(
        session.scalars(
            select(StudentPlacementEvent).where(
                StudentPlacementEvent.normalized_status == status
            )
        )
    )


def _placed(session) -> list[StudentPlacementEvent]:
    """Every event that means "this student is placed here"."""
    return list(
        session.scalars(
            select(StudentPlacementEvent).where(
                StudentPlacementEvent.normalized_status.in_(
                    [StudentStatus.FINAL_SELECTED, StudentStatus.OFFERED]
                )
            )
        )
    )


# --------------------------------------------------------------------------- #


def test_llm_not_final_selection_suppresses_the_false_offer(
    session, insert_email, hybrid_enabled, monkeypatch
):
    """The Phase 0 bug in one assertion: rules say offer, model says no."""
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    service = _FakeService(NOT_FINAL_PAYLOAD)
    monkeypatch.setattr(processing, "get_service", lambda cfg: service)

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["status"] == EmailStatus.PROCESSED
    assert service.calls == 1

    # no offer row, no placed record
    assert _count(session, Offer) == 0
    assert _count(session, OfferStudent) == 0
    assert _placed(session) == []

    session.refresh(row)
    assert row.classification == "UNKNOWN"  # not FINAL_SELECTION anymore
    assert row.classification_method == "llm"
    signals = " | ".join(row.classification_signals)
    assert "det:category=FINAL_SELECTION" in signals
    assert "det:offer_rows=2" in signals  # audit: what the rules wanted
    assert "llm:email_type=NOT_FINAL_SELECTION" in signals
    assert "llm:overrides_deterministic=suppresses_offers" in signals


def test_llm_final_selection_writes_only_the_students_the_model_named(
    session, insert_email, hybrid_enabled, monkeypatch
):
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    service = _FakeService(FINAL_PAYLOAD)  # model named 1 of the 2 rows
    monkeypatch.setattr(processing, "get_service", lambda cfg: service)

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["status"] == EmailStatus.PROCESSED
    assert outcome["rows_written"]["offers"] == 1
    assert outcome["rows_written"]["offer_students"] == 1

    offer = session.scalar(select(Offer))
    assert offer.method == "llm"
    assert offer.confidence == pytest.approx(0.91)
    assert offer.evidence and "shortlisted" not in offer.evidence.lower()
    assert offer.ctc_total == 650000

    rolls = {
        s.roll_no
        for s in session.scalars(
            select(OfferStudent).where(OfferStudent.offer_id == offer.id)
        )
    }
    assert rolls == {"21103001"}

    placed = _placed(session)
    assert [e.roll_no for e in placed] == ["21103001"]
    assert placed[0].method == "llm"

    session.refresh(row)
    assert row.classification == "FINAL_SELECTION"
    assert row.classification_method == "llm"
    signals = " | ".join(row.classification_signals)
    assert "llm:agrees_with_deterministic" not in signals
    assert "llm:overrides_deterministic=row_count (2 -> 1)" in signals


def test_low_confidence_is_accepted_and_flagged_not_blocked(
    session, insert_email, hybrid_enabled, monkeypatch
):
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    payload = {**FINAL_PAYLOAD, "confidence": 0.31}
    monkeypatch.setattr(
        processing, "get_service", lambda cfg: _FakeService(payload)
    )

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["status"] == EmailStatus.PROCESSED
    assert outcome["rows_written"]["offer_students"] == 1  # write not blocked

    session.refresh(row)
    signals = " | ".join(row.classification_signals)
    assert "llm:low_confidence=true" in signals
    assert "llm:confidence=0.31" in signals


def test_uncertain_verdict_suppresses_records_but_keeps_the_rule_label(
    session, insert_email, hybrid_enabled, monkeypatch
):
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    payload = {**NOT_FINAL_PAYLOAD, "email_type": "UNCERTAIN"}
    monkeypatch.setattr(
        processing, "get_service", lambda cfg: _FakeService(payload)
    )

    processing.process_one(session, row.id, load_settings())

    assert _count(session, Offer) == 0
    assert _placed(session) == []
    session.refresh(row)
    # UNCERTAIN must not overwrite the deterministic label, only the records
    assert row.classification == "FINAL_SELECTION"
    assert row.classification_method == "llm"


def test_llm_unavailable_keeps_deterministic_rows_and_requeues(
    session, insert_email, hybrid_enabled, monkeypatch
):
    """Failover exhausted: deterministic result kept, marked, retried next run."""
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    monkeypatch.setattr(processing, "get_service", lambda cfg: _AlwaysDown())

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["requeued"] is True
    assert outcome["status"] == EmailStatus.PENDING  # queued for retry

    assert _count(session, Offer) == 1
    assert _count(session, OfferStudent) == 2  # deterministic rows survive
    assert len(_placed(session)) == 2

    session.refresh(row)
    assert row.processing_status == EmailStatus.PENDING
    assert row.retry_count == 1
    assert row.classification_method == "rule_based_fallback"
    signals = " | ".join(row.classification_signals)
    assert "method=rule_based_fallback" in signals
    assert "llm:unavailable=" in signals
    assert "det:offer_rows=2" in signals  # audit still stored


def test_non_candidate_emails_never_reach_the_llm(
    session, insert_email, hybrid_enabled, monkeypatch
):
    row = insert_email(subject=SHORTLIST_SUBJECT, body_text=SHORTLIST_BODY)
    monkeypatch.setattr(processing, "get_service", lambda cfg: _NeverCalled())

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["status"] == EmailStatus.PROCESSED
    assert outcome["method"] == "rule_based"

    assert _count(session, ShortlistEvent) == 1
    assert _count(session, Offer) == 0
    shortlisted = _events(session, StudentStatus.SHORTLISTED)
    assert len(shortlisted) == 2
    assert all(e.method == "rule_based" for e in shortlisted)

    session.refresh(row)
    assert row.classification == "SHORTLIST"
    assert row.classification_method == "rule_based"
    assert "llm:email_type" not in " ".join(row.classification_signals)


def test_hybrid_disabled_keeps_the_deterministic_path_untouched(
    session, insert_email, monkeypatch
):
    """No PLACEMENT_HYBRID_LLM -> identical behaviour to the old pipeline."""
    monkeypatch.setenv("PLACEMENT_HYBRID_LLM", "false")
    row = insert_email(subject=OFFER_SUBJECT, body_text=OFFER_BODY)
    monkeypatch.setattr(processing, "get_service", lambda cfg: _NeverCalled())

    outcome = processing.process_one(session, row.id, load_settings())
    assert outcome["status"] == EmailStatus.PROCESSED
    assert outcome["method"] == "rule_based"
    assert _count(session, OfferStudent) == 2

    session.refresh(row)
    assert row.classification == "FINAL_SELECTION"
    assert row.classification_method == "rule_based"
    # taxonomy confidence is untouched when the hybrid layer is off
    assert row.classification_confidence >= 0.9
    assert "llm:" not in " ".join(row.classification_signals)
