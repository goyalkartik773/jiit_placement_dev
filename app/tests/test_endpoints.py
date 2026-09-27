"""Read endpoints: response envelope, pagination, filters, 404/422 guards.

End-to-end: sync (fake Gmail) -> process -> GET every documented endpoint
with real derived rows behind them.
"""

from __future__ import annotations

from app.tests.fake_gmail import FakeGmailClient, make_payload
from app.tests.test_processing import (
    FUNNEL_BODY,
    FUNNEL_SUBJECT,
    OFFER_BODY,
    OFFER_SUBJECT,
    WEBINAR_BODY,
    WEBINAR_SUBJECT,
)

GROUP = ["jiitengg2027@googlegroups.com"]


def _message(message_id: str, subject: str, body: str) -> dict:
    return make_payload(
        message_id,
        subject=subject,
        sender="Placement Cell <tpc@jiit.ac.in>",
        body=body,
        group="jiitengg2027",
    )


def _seed_and_process(client, fake_gmail) -> list[dict]:
    messages = [
        _message("gm-offer", OFFER_SUBJECT, OFFER_BODY),
        _message("gm-funnel", FUNNEL_SUBJECT, FUNNEL_BODY),
        _message("gm-webinar", WEBINAR_SUBJECT, WEBINAR_BODY),
    ]
    fake_gmail(FakeGmailClient(messages))
    sync = client.post("/api/gmail/sync", json={"groups": GROUP})
    assert sync.status_code == 200
    process = client.post("/api/gmail/process-pending")
    assert process.status_code == 200
    assert process.json()["data"]["failed"] == 0
    return messages


def _data(response) -> dict:
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert "message" in body
    return body["data"]


def test_health_and_job_status_envelopes(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    for path in ("/api/sync/status", "/api/processing/status"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["state"] in ("idle", "running", "completed", "failed")


def test_message_list_detail_and_guards(client, fake_gmail):
    _seed_and_process(client, fake_gmail)

    listing = _data(client.get("/api/gmail/messages"))
    assert listing["total"] == 3
    assert {item["gmail_message_id"] for item in listing["items"]} == {
        "gm-offer", "gm-funnel", "gm-webinar"
    }

    filtered = _data(client.get(
        "/api/gmail/messages", params={"classification": "FINAL_SELECTION"}
    ))
    assert filtered["total"] == 1
    processed = _data(client.get("/api/gmail/messages", params={"status": "PROCESSED"}))
    assert processed["total"] == 3
    searched = _data(client.get("/api/gmail/messages", params={"q": "Webinar"}))
    assert searched["total"] == 1

    detail = _data(client.get("/api/gmail/messages/gm-offer"))
    assert detail["gmail_message_id"] == "gm-offer"
    assert detail["processing_status"] == "PROCESSED"
    assert detail["classification"] == "FINAL_SELECTION"
    assert detail["classification_signals"]
    assert detail["classification_method"] == "rule_based"

    # 404 guards
    assert client.get("/api/gmail/messages/nope").status_code == 404
    assert client.post("/api/gmail/messages/nope/process").status_code == 404
    # 422 guard (page_size cap)
    assert client.get("/api/gmail/messages", params={"page_size": 101}).status_code == 422
    assert client.get("/api/gmail/messages", params={"page": 0}).status_code == 422


def test_companies_and_funnel_endpoints(client, fake_gmail):
    _seed_and_process(client, fake_gmail)

    listing = _data(client.get("/api/companies"))
    names = {item["name"] for item in listing["items"]}
    assert "Acme Corporation" in names
    assert "Acme Mass Recruitment Drive" in names

    funnel_company = next(
        item for item in listing["items"]
        if item["name"] == "Acme Mass Recruitment Drive"
    )
    funnel = _data(client.get(f"/api/companies/{funnel_company['id']}/funnel"))
    assert funnel["company_name"] == "Acme Mass Recruitment Drive"
    assert [round_["count"] for round_ in funnel["rounds"]] == [393]
    assert funnel["source"]["classification"] == "REGISTRATION"

    assert client.get(
        "/api/companies/does-not-exist/funnel"
    ).status_code == 404


def test_placements_endpoints(client, fake_gmail):
    _seed_and_process(client, fake_gmail)

    timeline = _data(client.get("/api/placements", params={"student_roll": "21103001"}))
    assert timeline["roll_no"] == "21103001"
    assert len(timeline["events"]) == 1
    assert timeline["events"][0]["normalized_status"] in ("FINAL_SELECTED", "OFFERED")
    assert len(timeline["offers"]) == 1
    assert timeline["offers"][0]["students"]

    empty = _data(client.get("/api/placements", params={"student_roll": "99999999"}))
    assert empty["events"] == [] and empty["offers"] == []

    summary = _data(client.get("/api/placements/summary"))
    assert summary["total_offers"] == 1
    assert summary["total_funnel_rows"] == 1
    assert summary["total_opportunities"] == 1
    assert summary["emails_by_status"]["PROCESSED"] == 3

    # 422: student_roll is required
    assert client.get("/api/placements").status_code == 422


def test_opportunities_endpoint(client, fake_gmail):
    _seed_and_process(client, fake_gmail)

    listing = _data(client.get("/api/opportunities"))
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["event_type"] == "WEBINAR"
    assert item["subject"] == WEBINAR_SUBJECT
    assert "https://example.com/webinar" in str(item["links"]) or (
        item["registration_link"] and "example.com" in item["registration_link"]
    )

    upcoming = _data(client.get("/api/opportunities", params={"upcoming": "true"}))
    assert upcoming["total"] == 1
    wrong_type = _data(client.get(
        "/api/opportunities", params={"event_type": "HACKATHON"}
    ))
    assert wrong_type["total"] == 0

    assert client.get(
        "/api/opportunities", params={"page_size": 101}
    ).status_code == 422


def test_processing_endpoint_validation_guards(client, fake_gmail):
    # 422: limit bounds are enforced by the schema
    response = client.post("/api/gmail/process-pending", json={"limit": 0})
    assert response.status_code == 422

    # 404: unknown message id on the single-message endpoint
    assert client.post("/api/gmail/messages/unknown-id/process").status_code == 404
