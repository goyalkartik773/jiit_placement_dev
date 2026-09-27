"""API integration tests over a temporary SQLite store (never PostgreSQL)."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from placement_pipeline.api.app import app, get_db, get_ingester
from placement_pipeline.db import connect
from placement_pipeline.ingest import run_ingest
from placement_pipeline.models import Email

# ---------------------------------------------------------------- fixtures --


def _email(eid: str, subject: str, body: str, at: datetime) -> Email:
    return Email(
        id=eid,
        gmail_message_id=f"gm-{eid}",
        source_group="jiitengg2027",
        sender="Anita Marwaha <anitamarwaha.tnp@gmail.com>",
        sender_email="anitamarwaha.tnp@gmail.com",
        subject=subject,
        received_raw=str(at),
        received_at=at,
        body_text=body,
    )


OFFER = _email(
    "amz",
    "Amazon - SDE intern hiring - Batch 2027 - Offers",
    "The following students have been offered by Amazon.\n"
    "1 22803009 HARLEEN KAUR CSE harleen@gmail.com\n\n"
    "*Job Role*: SDE Intern\n\n*Total Compensation*: INR 10,00,000\n"
    "\nLast date to revert: 25 May 2026\n",
    datetime(2026, 5, 20, 9, 0),
)
COUNTS = _email(
    "cnt",
    "Infosys Drive Update",
    "A total of 141 students cleared the online assessment and have been "
    "shortlisted for the next round. 1068 eligible students have not yet "
    "registered for the placement process.\n",
    datetime(2026, 5, 21, 10, 0),
)
LIST = _email(
    "lst",
    "Infosys - List of Shortlisted Students for Round 1",
    "The following students have been shortlisted for the interview process.\n"
    "1 22803012 ADITI VERMA CSE aditi@x.com\n",
    datetime(2026, 5, 22, 11, 0),
)
OPPORTUNITY = _email(
    "grp",
    "Flipkart GRiD 6.0 Campus Hackathon - Register by 25 May 2026",
    "Registrations are open for the hackathon. Register at "
    "https://grid.flipkart.com and hurry, last date to register is "
    "25 May 2026.\n",
    datetime(2026, 5, 23, 12, 0),
)
FIXTURES = [OFFER, COUNTS, LIST, OPPORTUNITY]


@pytest.fixture()
def client(tmp_path: Path):
    db = tmp_path / "api.sqlite3"
    run_ingest(db, emails=FIXTURES, attachments={})

    def override_db():
        conn = connect(db)
        try:
            yield conn
        finally:
            conn.close()

    def override_ingester(**_kwargs):
        return run_ingest(db, emails=FIXTURES, attachments={})

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ingester] = lambda: override_ingester
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------- endpoints


def test_index_points_at_docs(client: TestClient):
    body = client.get("/").json()
    assert body["docs"] == "/docs"


def test_companies_counts(client: TestClient):
    items = {c["company"]: c for c in client.get("/companies").json()["items"]}
    assert items["Amazon"]["offers"] == 1
    assert items["Amazon"]["shortlists"] == 0
    assert items["Infosys"]["shortlists"] == 2
    assert items["Flipkart"]["opportunities"] == 1


def test_company_funnel_counts(client: TestClient):
    body = client.get("/companies/infosys/funnel").json()
    assert body["company"] == "Infosys"
    got = {(c["count"], c["stage"]) for c in body["counts"]}
    assert (141, "cleared") in got
    assert (1068, "not yet registered") in got


def test_company_funnel_unknown_company_404(client: TestClient):
    resp = client.get("/companies/Acme%20Corp/funnel")
    assert resp.status_code == 404
    assert "Acme Corp" in resp.json()["detail"]


def test_offers_list_and_filter(client: TestClient):
    body = client.get("/offers").json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["company"] == "Amazon"
    assert item["role"] == "SDE Intern"
    assert item["package_inr"] == 1_000_000
    assert item["package_basis"] == "total"
    assert item["students"] == 1
    assert item["deadline"] == "2026-05-25"

    filtered = client.get("/offers", params={"company": "amazon"}).json()
    assert filtered["total"] == 1
    assert client.get("/offers", params={"company": "Zopsmart"}).json()["total"] == 0


def test_offers_summary_by_company(client: TestClient):
    items = {i["company"]: i for i in client.get("/offers/summary").json()["items"]}
    amazon = items["Amazon"]
    assert amazon["offers"] == 1
    assert amazon["students"] == 1
    assert amazon["package_min_inr"] == amazon["package_max_inr"] == 1_000_000
    assert amazon["roles"] == ["SDE Intern"]


def test_shortlists_list_carries_rows_and_counts(client: TestClient):
    body = client.get("/shortlists").json()
    assert body["total"] == 2
    by_email = {i["email_id"]: i for i in body["items"]}
    assert by_email["cnt"]["sub_pattern"] == "SHORTLIST_B"
    assert by_email["cnt"]["counts"][0]["count"] in (141, 1068)
    assert by_email["lst"]["sub_pattern"] == "SHORTLIST_A"
    assert by_email["lst"]["students"] == 1
    assert by_email["lst"]["company"] == "Infosys"


def test_opportunities_list_carries_links(client: TestClient):
    body = client.get("/opportunities").json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["company"] == "Flipkart"
    assert item["opportunity_type"] == "hackathon"
    assert item["deadline"] == "2026-05-25"
    assert any("grid.flipkart.com" in link["url"] for link in item["links"])


def test_student_lookup_and_404(client: TestClient):
    body = client.get("/students/22803009").json()
    assert body["roll_no"] == "22803009"
    first = body["appearances"][0]
    assert first["category"] == "OFFER"
    assert first["company"] == "Amazon"
    assert first["name"] == "Harleen Kaur"

    missing = client.get("/students/99999999")
    assert missing.status_code == 404


def test_email_detail_for_manual_review(client: TestClient):
    body = client.get("/emails/amz").json()
    assert "offered by Amazon" in body["body_text"]
    assert body["extraction"]["category"] == "OFFER"
    assert body["extraction"]["is_canonical"] is True

    assert client.get("/emails/nope").status_code == 404


def test_sync_returns_report_and_storage(client: TestClient):
    resp = client.post("/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["emails"] == 4
    assert body["report"]["by_category"]["OFFER"] == 1
    assert body["storage"]["emails"] == 4
    assert body["storage"]["students"] == 2
    assert body["storage"]["canonical"] == 4
