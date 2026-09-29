"""Full corpus reprocess under the PRODUCTION (hybrid) configuration.

    python scripts/reprocess_all.py                # every email, hybrid on
    python scripts/reprocess_all.py --limit 20     # smoke run first
    python scripts/reprocess_all.py --dry-run      # counts only, no writes

Why this exists and not ``run_backend_validation.py``:

``run_backend_validation.py:38`` does ``os.environ.setdefault("PLACEMENT_HYBRID_LLM", "false")``
on purpose - it asserts the deterministic parser's own hand-verified ground
truth, so the LLM must stay off.  The side effect is that every email it
force-processes is left in deterministic mode, which is why the database used
to oscillate between ``991/523`` (deterministic) and ``760/392`` (hybrid).
This script is the other half of the contract: it runs the corpus exactly the
way the live service runs it, with the hybrid layer ON, so a parser fix that
only shows up on the LLM path actually lands in the live data.

Idempotency: ``process_one`` deletes the derived rows for that email and
rebuilds them (``_delete_derived``), so reprocessing can never duplicate
offers / shortlists / events.  ``emails`` and ``email_attachments`` schema is
never touched - this script only flips ``processing_status`` to ``PENDING``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The whole point of this script is the production configuration.  Force it
# BEFORE app.config is imported; ``setdefault`` would lose to a stray "false".
os.environ["PLACEMENT_HYBRID_LLM"] = "true"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import func, select  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    Email,
    Offer,
    OfferStudent,
    Opportunity,
    ShortlistEvent,
    ShortlistStudent,
)
from app.schemas.processing import ProcessPendingRequest  # noqa: E402
from app.services.processing_service import run_processing  # noqa: E402

#: Row totals that a before/after comparison is actually about.
_TABLES: tuple[tuple[str, type], ...] = (
    ("offers", Offer),
    ("offer_students", OfferStudent),
    ("shortlist_events", ShortlistEvent),
    ("shortlist_students", ShortlistStudent),
    ("opportunities", Opportunity),
)


class _NullHandle:
    """Minimal stand-in for JobRunner's handle (no job record, no progress)."""

    def update(self, **kwargs: Any) -> None:
        return None


def _counts(session: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, model in _TABLES:
        out[key] = session.execute(select(func.count()).select_from(model)).scalar_one()
    out["emails"] = session.execute(
        select(func.count()).select_from(Email)
    ).scalar_one()
    out["processed"] = session.execute(
        select(func.count())
        .select_from(Email)
        .where(Email.processing_status == "PROCESSED")
    ).scalar_one()
    return out


def _field_completeness(session: Any) -> dict[str, int]:
    """The extraction bug this run is meant to close out.

    ``college`` / ``email`` / ``status_raw`` were blank on 100 % of
    ``offer_students`` because ``build_llm_offer`` wrote ``None`` for them,
    and ``role`` carried the email-level headline instead of the table's own
    ``Role Offered`` cell.
    """
    from sqlalchemy import text

    row = session.execute(
        text(
            """
            SELECT count(*)                                                    AS total,
                   count(*) FILTER (WHERE college   IS NULL OR btrim(college)   = '') AS college_blank,
                   count(*) FILTER (WHERE email     IS NULL OR btrim(email)     = '') AS email_blank,
                   count(*) FILTER (WHERE status_raw IS NULL OR btrim(status_raw) = '') AS status_blank,
                   count(*) FILTER (WHERE role      IS NULL OR btrim(role)      = '') AS role_blank,
                   count(DISTINCT NULLIF(btrim(role), ''))                     AS distinct_roles,
                   count(DISTINCT NULLIF(btrim(roll_no), ''))                  AS rolls
            FROM offer_students
            """
        )
    ).mappings().one()
    return dict(row)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0,
                    help="reprocess only the N oldest pending emails (0 = all)")
    ap.add_argument("--gm", nargs="*", default=None,
                    help="reprocess only these gmail_message_id values "
                         "(overrides --limit; everything else stays untouched)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the current counts and exit without writing")
    args = ap.parse_args()

    factory = get_session_factory()
    settings = load_settings()

    session = factory()
    try:
        before_counts = _counts(session)
        before_fields = _field_completeness(session)
        pending_now = session.execute(
            select(func.count())
            .select_from(Email)
            .where(Email.processing_status == "PENDING")
        ).scalar_one()
    finally:
        session.close()

    print("== BEFORE ==")
    print("   ", "  ".join(f"{k}={v}" for k, v in before_counts.items()))
    print("   ", "  ".join(f"{k}={v}" for k, v in before_fields.items()))
    print(f"    pending already queued = {pending_now}")
    print(f"    hybrid LLM enabled     = {settings.hybrid.enabled}"
          f"  accounts={len(settings.hybrid.accounts)}")

    if args.dry_run:
        return 0

    # Reset to PENDING - this is the ONLY write this script makes outside the
    # normal pipeline.  ``emails`` schema is untouched.
    from sqlalchemy import update

    session = factory()
    try:
        if args.gm:
            # Accept either identifier: callers reach for the uuid (emails.id)
            # they just read out of a query as often as gmail_message_id.
            criteria = [
                Email.gmail_message_id.in_(args.gm) | Email.id.in_(args.gm)
            ]
        else:
            criteria = [Email.processing_status != "PENDING"]
        session.execute(
            update(Email)
            .where(*criteria)
            .values(processing_status="PENDING", error_message=None)
        )
        session.commit()
        total = session.execute(
            select(func.count()).select_from(Email).where(Email.processing_status == "PENDING")
        ).scalar_one()
    finally:
        session.close()

    print(f"\n-> {total} emails queued as PENDING; running the pipeline (hybrid on) ...")
    started = time.perf_counter()
    stats = run_processing(
        session_factory=factory,
        handle=_NullHandle(),
        payload=ProcessPendingRequest(limit=args.limit or None),
        settings=settings,
    )
    elapsed = time.perf_counter() - started

    print(f"\n== PROCESS RESULT ({elapsed:.1f}s) ==")
    for key in ("total_pending", "processed", "succeeded", "failed",
                "requeued_for_llm_retry"):
        print(f"    {key:24s} {stats.get(key)}")
    print(f"    {'by_category':24s} {stats.get('by_category')}")
    print(f"    {'rows_written':24s} {stats.get('rows_written')}")
    if stats.get("llm"):
        print(f"    {'llm counters':24s} {stats['llm']}")

    session = factory()
    try:
        after_counts = _counts(session)
        after_fields = _field_completeness(session)
    finally:
        session.close()

    print("\n== AFTER ==")
    print("   ", "  ".join(f"{k}={v}" for k, v in after_counts.items()))
    print("   ", "  ".join(f"{k}={v}" for k, v in after_fields.items()))

    print("\n== DELTA ==")
    for key in before_counts:
        d = after_counts[key] - before_counts[key]
        if d:
            print(f"    {key:18s} {before_counts[key]} -> {after_counts[key]}  ({d:+d})")
    for key in before_fields:
        d = (after_fields[key] or 0) - (before_fields[key] or 0)
        print(f"    {key:18s} {before_fields[key]} -> {after_fields[key]}  ({d:+d})")

    return 0 if stats.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
