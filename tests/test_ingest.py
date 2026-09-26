"""Ingest + storage tests (PostgreSQL is injected away)."""

from datetime import date, datetime
from pathlib import Path

from placement_pipeline.db import connect, get_extraction, save_email, save_extraction, stats
from placement_pipeline.dedup import deduplicate
from placement_pipeline.ingest import extract_email, run_ingest
from placement_pipeline.models import Category, Email, SubPattern

# ---------------------------------------------------------------- fixtures --


def _email(
    eid: str,
    subject: str,
    body: str,
    *,
    group: str = "jiitengg2027",
    at: datetime = datetime(2026, 5, 20, 9, 0),
) -> Email:
    return Email(
        id=eid,
        gmail_message_id=f"gm-{eid}",
        source_group=group,
        sender="Anita Marwaha <anitamarwaha.tnp@gmail.com>",
        sender_email="anitamarwaha.tnp@gmail.com",
        subject=subject,
        received_raw=str(at),
        received_at=at,
        body_text=body,
    )


OFFER_SUBJECT = "Amazon - SDE intern hiring - Batch 2027 - Offers"
OFFER_BODY = """\
*Congratulations!*

The following students have been offered by Amazon.

1 22803009 HARLEEN KAUR CSE harleen@gmail.com

*Job Role*: SDE Intern

*Total Compensation*: INR 10,00,000

Last date to revert: 25 May 2026
"""

FORWARDED_OFFER = """\
Congrats to all. Details below.

---------- Forwarded message ---------
From: tnp@example.com
Date: Mon, 6 Jul 2026 at 9:00 AM
Subject: Acme Corp - Offers
To: <grp@googlegroups.com>

Following students have been offered by Acme Corp.

1 23103001 ANSH SHARMA CSE ans@x.com

*Job Role*: Software Engineer

Salary Package: INR 6.00 Lakhs
"""

COUNTS_SUBJECT = "Infosys Drive Update"
COUNTS_BODY = (
    "A total of 141 students cleared the online assessment and have been "
    "shortlisted for the next round. 1068 eligible students have not yet "
    "registered for the placement process.\n"
)

LIST_SUBJECT = "Y Corp - List of Shortlisted Students for Round 1"
LIST_BODY = "The list of students is attached herewith for the process.\n"
ATTACHMENT_TABLE = (
    "S.NO | Roll No | Name | Email\n"
    "1 | 23103005 | PRIYA NAIR | priya@x.com\n"
)


# ------------------------------------------------------------- extract_email


def test_extract_offer_email():
    result = extract_email(_email("e1", OFFER_SUBJECT, OFFER_BODY))
    ext = result.extraction
    assert ext.category is Category.OFFER
    assert ext.company == "Amazon"
    assert ext.role == "SDE Intern"
    assert ext.package_inr == 1_000_000
    assert ext.package_basis == "total"
    assert ext.status == "extended"
    assert ext.deadline == date(2026, 5, 25)
    assert [s.roll_no for s in ext.students] == ["22803009"]
    assert ext.is_canonical is True


def test_history_fills_gaps_and_resolves_warnings():
    result = extract_email(_email("e2", "Acme Corp - Offers", FORWARDED_OFFER))
    ext = result.extraction
    assert result.sections == 2
    # current section alone would have neither role nor package
    assert ext.role == "Software Engineer"
    assert ext.package_inr == 600_000
    assert ext.status == "extended"
    assert "role not stated in body or table" not in ext.warnings
    # rows from the forwarded section are parsed too
    assert [s.roll_no for s in ext.students] == ["23103001"]


def test_subpattern_refined_to_funnel_counts():
    ext = extract_email(_email("e3", COUNTS_SUBJECT, COUNTS_BODY)).extraction
    assert ext.category is Category.SHORTLIST
    assert ext.sub_pattern is SubPattern.FUNNEL_COUNTS
    assert {(f.count, f.stage) for f in ext.funnel_counts} >= {
        (141, "cleared"),
        (1068, "not yet registered"),
    }


def test_subpattern_refined_to_named_list_from_rows():
    ext = extract_email(_email("e4", LIST_SUBJECT, LIST_BODY)).extraction
    assert ext.category is Category.SHORTLIST
    assert ext.students == []  # body has no table
    assert ext.sub_pattern is not SubPattern.FUNNEL_COUNTS  # classifier's call


def test_attachment_text_supplies_rows_when_body_has_none():
    email = _email("e5", LIST_SUBJECT, LIST_BODY)
    result = extract_email(email, [ATTACHMENT_TABLE])
    ext = result.extraction
    assert [s.roll_no for s in ext.students] == ["23103005"]
    assert ext.students[0].raw_name == "PRIYA NAIR"
    assert ext.students[0].name == "Priya Nair"  # normalized, raw preserved
    assert result.attachment_rows == 1
    # parsed evidence (rows present) promotes the shortlist to pattern A
    assert ext.sub_pattern is SubPattern.NAMED_LIST


def test_attachment_rows_dedup_against_body_rows():
    body = LIST_BODY + "\n1 23103005 PRIYA NAIR CSE priya@x.com\n"
    result = extract_email(_email("e6", LIST_SUBJECT, body), [ATTACHMENT_TABLE])
    assert len(result.extraction.students) == 1
    assert result.attachment_rows == 0


def test_truncated_attachment_text_is_flagged():
    big = "x" * 50_000 + "\n1 | 23103005 | PRIYA NAIR | priya@x.com"
    result = extract_email(_email("e7", LIST_SUBJECT, LIST_BODY), [big])
    assert "attachment text truncated at 50000 chars" in result.extraction.warnings


def test_other_category_parses_students_without_forcing_company():
    body = "Students are requested to submit the form.\n1 23103008 RIA DAS CSE ria@x.com\n"
    ext = extract_email(_email("e8", "Submit forms by 10 AM, 02 Aug, 2026", body)).extraction
    assert ext.category is Category.OTHER
    assert [s.roll_no for s in ext.students] == ["23103008"]
    # admin mail: no company is expected, not a warning
    assert ext.warnings == []


# ------------------------------------------------------------------ database


def test_storage_roundtrip(tmp_path: Path):
    ext = extract_email(_email("e1", OFFER_SUBJECT, OFFER_BODY)).extraction
    conn = connect(tmp_path / "t.sqlite3")
    with conn:
        save_email(conn, _email("e1", OFFER_SUBJECT, OFFER_BODY))
        save_extraction(conn, ext)
    loaded = get_extraction(conn, "e1")
    conn.close()

    assert loaded is not None
    assert loaded.category is Category.OFFER
    assert loaded.company == "Amazon"
    assert loaded.role == "SDE Intern"
    assert loaded.package_inr == 1_000_000
    assert loaded.deadline == date(2026, 5, 25)
    assert [s.roll_no for s in loaded.students] == ["22803009"]
    assert loaded.warnings == ext.warnings


def test_reingest_replaces_children_idempotently(tmp_path: Path):
    db = tmp_path / "t.sqlite3"
    email = _email("e1", OFFER_SUBJECT, OFFER_BODY)

    run_ingest(db, emails=[email], attachments={})
    first = stats(connect(db))

    run_ingest(db, emails=[email], attachments={})
    conn = connect(db)
    second = stats(conn)
    conn.close()

    assert first == second
    assert second["emails"] == 1
    assert second["students"] == 1


# -------------------------------------------------------------------- run


def test_run_ingest_dedup_and_report(tmp_path: Path):
    original = _email("a", LIST_SUBJECT, LIST_BODY, at=datetime(2026, 3, 1, 10, 0))
    crosspost = _email(
        "b", LIST_SUBJECT, LIST_BODY,
        group="jiitmtech2027", at=datetime(2026, 3, 1, 10, 5),
    )
    revised = _email(
        "c", f"Revised: {LIST_SUBJECT}", LIST_BODY, at=datetime(2026, 3, 1, 11, 0),
    )
    db = tmp_path / "t.sqlite3"
    report = run_ingest(db, emails=[original, crosspost, revised], attachments={})

    assert report.emails == 3
    assert report.by_category["SHORTLIST"] == 3
    assert report.dedup["canonical"] == 1
    assert report.dedup["deduped"] == 2
    assert report.dedup["revisions"] == 1

    conn = connect(db)
    assert stats(conn)["emails"] == 3
    assert stats(conn)["canonical"] == 1
    a = get_extraction(conn, "a")
    c = get_extraction(conn, "c")
    conn.close()

    assert a.is_canonical is False and a.dedup_of == "c"
    assert c.is_canonical is True and c.revision_of == "b"


def test_run_ingest_reports_section_and_warning_counters(tmp_path: Path):
    emails = [
        _email("x1", OFFER_SUBJECT, OFFER_BODY),
        _email("x2", "Acme Corp - Offers", FORWARDED_OFFER),
    ]
    report = run_ingest(tmp_path / "t.sqlite3", emails=emails, attachments={})
    assert report.multi_section_emails == 1
    assert report.students == 2
    assert report.emails_with_students == 2
    assert report.seconds >= 0
