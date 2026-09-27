"""Unit tests for the 14-value taxonomy mapping (``classify_taxonomy``).

These cover every taxonomy value - including ``OFF_CAMPUS_OPPORTUNITY`` and
``IRRELEVANT``, which have **zero** samples in the real corpus (documented in
``reports/backend_validation.md``): their rules are proven here, by hand-built
extractions, instead of by golden data.
"""

from __future__ import annotations

import pytest

from app.classifiers.taxonomy import TAXONOMY, classify_taxonomy
from placement_pipeline.models import (
    Category,
    Extraction,
    FunnelCount,
    StudentRow,
)


def _ext(**kwargs) -> Extraction:
    base: dict = {
        "email_id": "ext-1",
        "confidence": 0.5,
        "signals": ["subject:test"],
    }
    base.update(kwargs)
    return Extraction(**base)


def _assert_invariants(result) -> None:
    assert result.category in TAXONOMY
    assert 0.0 < result.confidence <= 1.0
    assert result.method in ("rule_based", "llm", "hybrid")
    assert result.method == "rule_based"  # no LLM in these tests
    assert result.signals  # evidence trail is never empty


def test_offer_maps_to_final_selection():
    result = classify_taxonomy(
        _ext(category=Category.OFFER),
        subject="Acme - Final Offers",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "FINAL_SELECTION"
    assert result.confidence >= 0.9


def test_shortlist_named_table_wins():
    result = classify_taxonomy(
        _ext(
            category=Category.SHORTLIST,
            students=[StudentRow(raw_name="Kartik Goel", roll_no="21103001")],
        ),
        subject="Acme - Shortlisted Students",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "SHORTLIST"
    assert result.confidence >= 0.9


def test_shortlist_funnel_counts_map_to_shortlist():
    result = classify_taxonomy(
        _ext(
            category=Category.SHORTLIST,
            funnel_counts=[FunnelCount(stage="Applied", count=100)],
        ),
        subject="Acme - Selection rounds",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "SHORTLIST"


def test_subject_registration_beats_registration_status_table():
    # "Pending Registration" table lists who hasn't registered - not a
    # selection shortlist (the Amazon-WoW / Accenture pattern).
    result = classify_taxonomy(
        _ext(
            category=Category.SHORTLIST,
            students=[StudentRow(raw_name="A B", roll_no="21103001")],
        ),
        subject="Acme Drive - Pending Registration | Deadline 6 Sep",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "REGISTRATION"


def test_subject_shortlist_word_keeps_shortlist():
    # Both words present: an explicit "Shortlisted Students ..." subject
    # outranks the registration wording (STMicro pattern).
    result = classify_taxonomy(
        _ext(
            category=Category.SHORTLIST,
            students=[StudentRow(raw_name="A B", roll_no="21103001")],
        ),
        subject="Acme - Shortlisted Students + Registration steps",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "SHORTLIST"


def test_process_logistics_without_rows_is_notice():
    result = classify_taxonomy(
        _ext(category=Category.SHORTLIST),
        subject="Acme - Selection Process & Reporting Venue",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "SELECTION_PROCESS_NOTICE"


def test_bare_shortlist_wording_without_rows_stays_shortlist():
    result = classify_taxonomy(
        _ext(category=Category.SHORTLIST),
        subject="Acme Drive Shortlist",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "SHORTLIST"
    assert result.confidence <= 0.8  # honest: evidence rows are missing


def test_hackathon_kind_maps_to_hackathon():
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="hackathon"),
        subject="CodeFest 2026",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "HACKATHON"


def test_off_campus_wording_wins_without_corpus_sample():
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="drive"),
        subject="Acme Off Campus Drive - Apply",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "OFF_CAMPUS_OPPORTUNITY"
    assert result.confidence >= 0.85


def test_webinar_subject_beats_hackathon_kind_without_corpus_sample():
    # Tata InnoVent pattern: parent program is a hackathon, the email
    # announces a webinar.
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="hackathon"),
        subject="InnoVent-27 | Exclusive Webinar on AI at the Edge",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "WEBINAR"


def test_webinar_kind_maps_to_webinar():
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="webinar"),
        subject="NXP Virtual Technical Session",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "WEBINAR"


def test_internship_drive_maps_to_internship():
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="drive"),
        subject="Acme Summer Internship Drive 2027",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "INTERNSHIP_OPPORTUNITY"


def test_hiring_wording_with_company_maps_to_job():
    result = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, company="Acme"),
        subject="Acme - Hiring for Full Time Role from 2027 Batch",
        body="Apply for the drive by 10 AM on 30 Sep 2026.",
    )
    _assert_invariants(result)
    assert result.category == "JOB_OPPORTUNITY"


def test_quiz_and_session_kinds():
    quiz = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="quiz"),
        subject="Acme Tech Quiz",
        body="",
    )
    session = classify_taxonomy(
        _ext(category=Category.OPPORTUNITY, opportunity_type="session"),
        subject="Acme Hands-on Workshop",
        body="",
    )
    _assert_invariants(quiz)
    _assert_invariants(session)
    assert quiz.category == "EVENT"
    assert session.category == "WORKSHOP"


def test_admin_wording_maps_to_general_notice():
    result = classify_taxonomy(
        _ext(category=Category.OTHER),
        subject="Placement Policy - 2027 Graduating Batches",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "GENERAL_PLACEMENT_NOTICE"


def test_registration_subject_in_other_branch():
    result = classify_taxonomy(
        _ext(category=Category.OTHER),
        subject="Register now for the campus drive",
        body="",
    )
    _assert_invariants(result)
    assert result.category == "REGISTRATION"


def test_footer_sized_body_is_irrelevant_without_corpus_sample():
    result = classify_taxonomy(
        _ext(category=Category.OTHER),
        subject="Re:FW: Meeting",
        body="Sent from my iPhone",
    )
    _assert_invariants(result)
    assert result.category == "IRRELEVANT"


def test_neutral_prose_falls_back_to_unknown():
    body = "The quick brown fox jumps over the lazy dog near the riverbank. " * 8
    result = classify_taxonomy(
        _ext(category=Category.OTHER),
        subject="Updates",
        body=body,
    )
    _assert_invariants(result)
    assert result.category == "UNKNOWN"
    assert result.confidence <= 0.5  # never a forced fit


@pytest.mark.parametrize("category", list(Category))
def test_every_parser_category_maps_into_the_14_value_taxonomy(category):
    result = classify_taxonomy(_ext(category=category), subject="x", body="")
    _assert_invariants(result)
    assert result.category in TAXONOMY
