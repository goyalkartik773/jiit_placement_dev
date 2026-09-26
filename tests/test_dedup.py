"""Dedup rules pinned to corpus patterns (crossposts, revisions, reminders)."""

from datetime import datetime, timedelta

from placement_pipeline.dedup import cluster_key, cluster_stats, deduplicate
from placement_pipeline.models import Email

BASE = datetime(2026, 6, 1, 10, 0)


def _email(
    eid: str,
    subject: str,
    *,
    sender: str = "T&P Cell <tnp@example.com>",
    sender_email: str = "tnp@example.com",
    group: str = "jiitengg2027",
    at: datetime = BASE,
    mid: str = "",
) -> Email:
    return Email(
        id=eid,
        gmail_message_id=mid or eid,
        source_group=group,
        sender=sender,
        sender_email=sender_email,
        subject=subject,
        received_raw="Mon, 1 Jun 2026 10:00:00 +0530",
        received_at=at,
        body_text="body",
    )


def test_cross_group_crosspost_shares_one_cluster():
    a = _email("a", "ZS Associates - List of shortlisted students", group="jiitengg2027")
    b = _email(
        "b",
        "ZS Associates - List of shortlisted students",
        group="jiitmtech2027",
        at=BASE + timedelta(minutes=3),
        mid="different-gmail-id",
    )
    assert cluster_key(a.subject, a.sender_email) == cluster_key(
        b.subject, b.sender_email
    )
    out = deduplicate([a, b])
    assert out["a"].is_canonical is False and out["a"].dedup_of == "b"
    assert out["b"].is_canonical is True


def test_forward_prefix_joins_the_original_cluster():
    a = _email("a", "Hyperdart - Final Shortlist for Aptitude Test")
    b = _email(
        "b",
        "Fwd: Hyperdart - Final Shortlist for Aptitude Test",
        at=BASE + timedelta(hours=1),
    )
    out = deduplicate([a, b])
    assert out["a"].dedup_of == "b"
    assert out["b"].revision_of is None


def test_revision_supersedes_original_and_links_it():
    original = _email("o", "Decimal Point Analytics - DPA Vivechana 2026")
    revised = _email(
        "r",
        "Revised: Decimal Point Analytics - DPA Vivechana 2026",
        at=BASE + timedelta(days=2),
    )
    out = deduplicate([original, revised])
    # same cluster, latest (the revision) is canonical
    assert out["r"].is_canonical is True
    assert out["r"].revision_of == "o"
    assert out["o"].is_canonical is False
    assert out["o"].dedup_of == "r"


def test_revision_without_original_stays_canonical_and_unlinked():
    revised = _email("r", "Correction: Accenture - Registration Email")
    out = deduplicate([revised])
    assert out["r"].is_canonical is True
    assert out["r"].revision_of is None


def test_reminder_keeps_its_own_cluster():
    original = _email("o", "Amazon WoW Program - Complete Registration")
    reminder = _email(
        "m",
        "Reminder: Amazon WoW Program - Complete Registration",
        at=BASE + timedelta(days=1),
    )
    out = deduplicate([original, reminder])
    # distinct clusters: both canonical, neither deduped into the other
    assert out["o"].is_canonical is True
    assert out["m"].is_canonical is True
    assert out["o"].dedup_of is None and out["m"].dedup_of is None
    # a crosspost of the reminder joins the *reminder* cluster
    cross = _email(
        "c",
        "Fwd: Reminder: Amazon WoW Program - Complete Registration",
        at=BASE + timedelta(days=1, minutes=5),
        group="jiitmtech2027",
    )
    out2 = deduplicate([original, reminder, cross])
    assert out2["m"].dedup_of == "c"
    assert out2["o"].is_canonical is True


def test_different_sender_never_shares_a_cluster():
    a = _email("a", "Infosys - Niche Roles Hiring Drive")
    b = _email(
        "b",
        "Infosys - Niche Roles Hiring Drive",
        sender="Anita <anita@example.com>",
        sender_email="anita@example.com",
        at=BASE + timedelta(minutes=1),
    )
    out = deduplicate([a, b])
    assert out["a"].is_canonical and out["b"].is_canonical


def test_canonical_selection_falls_back_to_raw_date_then_id():
    no_at_a = _email("aaa", "Same Subject Here")
    no_at_a.received_at = None
    no_at_b = _email("bbb", "Same Subject Here")
    no_at_b.received_at = None
    no_at_b.received_raw = "Tue, 2 Jun 2026 10:00:00 +0530"
    out = deduplicate([no_at_b, no_at_a])  # input order must not matter
    assert out["bbb"].is_canonical is True
    assert out["aaa"].dedup_of == "bbb"


def test_cluster_stats_counters_are_honest():
    emails = [
        _email("a", "X - Offers"),
        _email("b", "Fwd: X - Offers", at=BASE + timedelta(hours=1)),
        _email("c", "Y - Registration"),
        _email("d", "Reminder: Y - Registration", at=BASE + timedelta(days=1)),
        _email("e", "Revised: X - Offers", at=BASE + timedelta(days=2)),
    ]
    stats = cluster_stats(emails)
    assert stats == {
        "emails": 5,
        "clusters": 3,          # X (a,b,e), Y, reminder-Y
        "multi_member_clusters": 1,
        "canonical": 3,
        "deduped": 2,
        "revisions": 1,
    }
