"""Step 1 - POST /api/gmail/sync: idempotency, dedup, isolation, quota.

Every test drives the real endpoint against a FakeGmailClient (no network,
no credentials): the full flow MIME decode -> dedup -> PostgreSQL runs.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Email, EmailAttachment, EmailStatus
from app.tests.fake_gmail import FakeGmailClient, make_payload, make_xlsx

GROUPS = ["jiitengg2027@googlegroups.com", "jiitintgt2027@googlegroups.com"]


def _message(
    message_id: str,
    *,
    subject: str = "Test subject",
    group: str = "jiitengg2027",
    **kwargs,
) -> dict:
    return make_payload(
        message_id,
        subject=subject,
        sender="Placement Cell <tpc@jiit.ac.in>",
        body="Body of " + message_id,
        group=group,
        **kwargs,
    )


def _post_sync(client, payload: dict | None = None):
    return client.post("/api/gmail/sync", json=payload or {"groups": GROUPS})


def test_sync_inserts_pending_rows_and_is_idempotent(client, fake_gmail, session):
    fake_gmail(FakeGmailClient([
        _message("gm-1", subject="Acme - Offers"),
        _message("gm-2", subject="Acme - Shortlist"),
    ]))

    first = _post_sync(client)
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["new_messages"] == 2
    assert data["duplicates_skipped"] == 0
    assert data["failed_messages"] == 0
    assert data["errors"] == []

    rows = session.scalars(select(Email)).all()
    assert len(rows) == 2
    # Step 1 output is raw + PENDING (Step 2 does the classification).
    assert {r.processing_status for r in rows} == {EmailStatus.PENDING}
    assert all(r.classification is None for r in rows)
    # Headers decoded from MIME: source group from List-Id, aware timestamp.
    for row in rows:
        assert row.source_group == "jiitengg2027"
        assert row.received_at is not None and row.received_at.tzinfo is not None
        assert row.subject in ("Acme - Offers", "Acme - Shortlist")

    # Re-run: every message is a duplicate; nothing new is written.
    second = _post_sync(client)
    assert second.status_code == 200
    data2 = second.json()["data"]
    assert data2["new_messages"] == 0
    assert data2["duplicates_skipped"] == 2
    assert session.execute(select(func.count()).select_from(Email)).scalar_one() == 2

    status = client.get("/api/sync/status").json()["data"]
    assert status["state"] == "completed"


def test_sync_crosspost_of_same_message_counted_once(client, fake_gmail, session):
    # The same message id returned by two different groups' queries.
    fake_gmail(FakeGmailClient(
        [_message("gm-x", subject="Cross-posted notice")],
        groups={
            "jiitengg2027": ["gm-x"],
            "jiitintgt2027": ["gm-x"],
        },
    ))

    response = _post_sync(client)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_fetched"] == 2
    assert data["new_messages"] == 1
    assert data["duplicates_skipped"] == 1
    assert session.execute(select(func.count()).select_from(Email)).scalar_one() == 1


def test_sync_per_message_failure_is_isolated_and_resumable(
    client, fake_gmail, session
):
    messages = [_message("gm-a"), _message("gm-b"), _message("gm-c")]
    fake_gmail(FakeGmailClient(messages, fail_get_ids=frozenset({"gm-b"})))

    first = _post_sync(client)
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["new_messages"] == 2
    assert data["failed_messages"] == 1

    stored = {r.gmail_message_id for r in session.scalars(select(Email))}
    assert stored == {"gm-a", "gm-c"}

    # Re-run without the failure: the failed message resumes, others dedup.
    fake_gmail(FakeGmailClient(messages))
    second = _post_sync(client)
    data2 = second.json()["data"]
    assert data2["new_messages"] == 1
    assert data2["duplicates_skipped"] == 2
    assert data2["failed_messages"] == 0
    stored = {r.gmail_message_id for r in session.scalars(select(Email))}
    assert stored == {"gm-a", "gm-b", "gm-c"}


def test_sync_quota_abort_keeps_committed_rows(client, fake_gmail, session):
    fake_gmail(FakeGmailClient(
        [_message("gm-1"), _message("gm-2"), _message("gm-3")],
        groups={
            "jiitengg2027": ["gm-1", "gm-2"],
            "jiitintgt2027": ["gm-3"],
        },
        fail_list_after=1,  # second group's listing raises (quota window)
    ))

    response = _post_sync(client, {"groups": GROUPS})
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["new_messages"] == 2  # committed rows kept
    assert len(data["errors"]) == 1
    assert "re-run" in body["message"]
    assert session.execute(select(func.count()).select_from(Email)).scalar_one() == 2

    # A re-run resumes idempotently from where the aborted run stopped.
    fake_gmail(FakeGmailClient(
        [_message("gm-1"), _message("gm-2"), _message("gm-3")],
        groups={
            "jiitengg2027": ["gm-1", "gm-2"],
            "jiitintgt2027": ["gm-3"],
        },
    ))
    resumed = _post_sync(client, {"groups": GROUPS}).json()["data"]
    assert resumed["new_messages"] == 1
    assert resumed["duplicates_skipped"] == 2
    assert resumed["errors"] == []
    stored = {r.gmail_message_id for r in session.scalars(select(Email))}
    assert stored == {"gm-1", "gm-2", "gm-3"}


def test_sync_extracts_attachment_text(client, fake_gmail, session):
    xlsx_bytes = make_xlsx([
        ["Roll No", "Name"],
        ["21103001", "Kartik Goel"],
    ])
    inline = make_payload(
        "gm-inline",
        subject="Attached list",
        sender="Placement Cell <tpc@jiit.ac.in>",
        body="Please find attached the list.",
        attachments=[
            {"filename": "notes.txt", "mime_type": "text/plain",
             "data": b"inline note text"},
        ],
    )
    download = make_payload(
        "gm-download",
        subject="Attached sheet",
        sender="Placement Cell <tpc@jiit.ac.in>",
        body="Attached sheet for download.",
        attachments=[
            {"filename": "students.xlsx",
             "mime_type": "application/vnd.openxmlformats-officedocument."
                          "spreadsheetml.sheet",
             "attachment_id": "att-42"},
        ],
    )
    fake_gmail(FakeGmailClient(
        [inline, download],
        attachment_bytes={("gm-download", "att-42"): xlsx_bytes},
    ))

    response = _post_sync(client, {"download_attachments": True})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["new_messages"] == 2
    assert data["attachments_downloaded"] >= 1

    rows = {
        (a.filename, a.method, a.extracted_text)
        for a in session.scalars(select(EmailAttachment))
    }
    methods = {m for _, m, _ in rows}
    assert "inline" in methods and "downloaded" in methods
    texts = [t for _, _, t in rows if t]
    assert any("inline note text" in t for t in texts)
    assert any("21103001" in t for t in texts)  # xlsx parsed to pipe text


def test_sync_request_validation_and_status(client):
    # 422: max_results must be >= 1
    response = client.post("/api/gmail/sync", json={"max_results": 0})
    assert response.status_code == 422
    # status endpoint answers even before any run
    status = client.get("/api/sync/status")
    assert status.status_code == 200
    assert status.json()["data"]["state"] in ("idle", "running", "completed")
