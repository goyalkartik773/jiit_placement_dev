"""Golden dataset end-to-end: seed 33 real corpus emails -> process via the
public API -> assert taxonomy labels + DB-derived rows -> prove idempotency.

Ground truth lives in ``scripts/run_backend_validation.py`` (shared spec);
the pipeline's own 18-sample parser GT is asserted there as well.
"""

from __future__ import annotations

from sqlalchemy import func, select, update

from app.models import Email, EmailStatus
from scripts.corpus_seed import seed_emails
from scripts.run_backend_validation import (
    GOLDEN,
    check_golden,
    golden_gm_ids,
    golden_row_totals,
)


def _failures(results) -> list[str]:
    out: list[str] = []
    for g in results:
        if not g["ok"]:
            detail = "; ".join(
                f"{name}: observed={obs!r}"
                for name, ok, obs in g["checks"]
                if not ok
            )
            out.append(f"{g['gm']} (gt={g['gt']}): {detail}")
    return out


def test_golden_dataset(client, session):
    seeded = seed_emails(golden_gm_ids(), session)
    missing = [gm for gm, status in seeded.items() if status == "missing"]
    assert not missing, f"golden emails absent from corpus: {missing}"

    response = client.post("/api/gmail/process-pending")
    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats["total_pending"] == len(golden_gm_ids())
    assert stats["succeeded"] == len(golden_gm_ids())
    assert stats["failed"] == 0

    session.expire_all()  # rows were written by the API's own session
    results = check_golden(session)
    assert len(results) == len(GOLDEN)
    failures = _failures(results)
    assert not failures, "golden mismatches:\n" + "\n".join(failures)

    # Every seeded email finished in a terminal success state.
    not_done = session.execute(
        select(func.count())
        .select_from(Email)
        .where(Email.gmail_message_id.in_(golden_gm_ids()))
        .where(Email.processing_status != EmailStatus.PROCESSED)
    ).scalar_one()
    assert not_done == 0


def test_golden_reprocess_is_idempotent(client, session):
    seeded = seed_emails(golden_gm_ids(), session)
    assert all(status != "missing" for status in seeded.values())

    first = client.post("/api/gmail/process-pending").json()["data"]
    assert first["succeeded"] == len(golden_gm_ids())
    totals_run1 = golden_row_totals()

    # Delete-then-rebuild: process the same emails once more.
    session.execute(
        update(Email).values(
            processing_status=EmailStatus.PENDING, error_message=None
        )
    )
    session.commit()
    second = client.post("/api/gmail/process-pending").json()["data"]
    assert second["succeeded"] == len(golden_gm_ids())
    assert second["failed"] == 0
    totals_run2 = golden_row_totals()
    assert totals_run1 == totals_run2, (
        f"row totals drifted: {totals_run1} != {totals_run2}"
    )

    # And a third run with nothing pending is a clean no-op.
    third = client.post("/api/gmail/process-pending").json()["data"]
    assert third["total_pending"] == 0
    assert golden_row_totals() == totals_run2
