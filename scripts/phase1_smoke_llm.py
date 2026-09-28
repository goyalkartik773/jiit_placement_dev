"""Phase 1 smoke test - real LLM verdicts, no database writes.

    python scripts/phase1_smoke_llm.py                     # the two bug emails
    python scripts/phase1_smoke_llm.py --limit 8           # first N candidates
    python scripts/phase1_smoke_llm.py --gm 1a07f91284991c5c --gm ...

Prints, per email: what the **deterministic** extractor would have written
(``det:``) next to what the **LLM** returned (``llm:``), so a disagreement is
visible before any row is committed.  Reads the corpus from ``public.emails``
(read-only) - it never touches derived tables.

Keys come from ``.env`` via :func:`app.config.load_llm_config`; account labels
(``gemini_2``) are printed, key values never are.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.classifiers.taxonomy import classify_taxonomy, is_final_selection_candidate
from app.config import load_llm_config, load_settings
from app.db import get_session_factory
from app.extractors.llm_offers import deterministic_statuses
from app.llm import LLMUnavailable, get_service, reset_service
from app.models import Email
from app.parsers import email_adapter
from placement_pipeline.ingest import extract_email
from placement_pipeline.models import Category

#: The two emails Phase 0 proved were being written wrong.
BUG_EMAILS = (
    "f179d24d5b1542d18bb44e7eb20bfe3a",  # HackWithInfy 24 Jun: 198 pending + 10 no-show
    "1a056bcec001b045",                  # HackWithInfy 31 Aug: 10 no-show
)


def _load(args, session):
    ids = args.gm or ([] if args.all else BUG_EMAILS)
    if ids:
        rows = list(
            session.scalars(
                select(Email).where(
                    (Email.id.in_(ids)) | (Email.gmail_message_id.in_(ids))
                )
            )
        )
    else:
        rows = list(session.scalars(select(Email)))
    return rows


def _candidates(rows, limit: int | None):
    out = []
    for row in rows:
        try:
            result = extract_email(email_adapter.to_pipeline_email(row))
            ext = result.extraction
            taxonomy = classify_taxonomy(ext, subject=row.subject, body=row.body_text)
            if is_final_selection_candidate(
                ext, taxonomy.category, subject=row.subject, body=row.body_text
            ):
                out.append((row, ext, taxonomy))
        except Exception as exc:  # a broken email must not stop the smoke run
            print(f"  ! parse failed for {row.gmail_message_id}: {type(exc).__name__}")
    out.sort(key=lambda item: item[0].gmail_message_id)
    if limit:
        out = out[:limit]
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gm", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--all", action="store_true", help="every candidate email, not just the bug ones"
    )
    args = parser.parse_args(argv)

    cfg = load_llm_config()
    if not cfg.enabled:
        print("PLACEMENT_HYBRID_LLM is false - nothing to smoke test.")
        return 1
    print(f"accounts: {', '.join(a.label for a in cfg.accounts)}")
    print(f"models  : {cfg.models}")

    settings = load_settings()
    session = get_session_factory()()
    try:
        rows = _load(args, session)
        candidates = _candidates(rows, args.limit or None)
    finally:
        session.close()

    print(f"\ncandidate emails: {len(candidates)}\n")

    service = get_service(settings.hybrid)
    verdicts: dict[str, int] = {}
    disagreements = 0
    failures = 0
    try:
        for row, ext, taxonomy in candidates:
            det_statuses = deterministic_statuses(ext, row.subject)
            det_rows = len(ext.students) if ext.category == Category.OFFER else 0
            try:
                call = service.extract(subject=row.subject, body=row.body_text)
            except LLMUnavailable as exc:
                failures += 1
                print(f"--- {row.gmail_message_id}  {row.subject[:70]}")
                print(f"    det : {taxonomy.category} rows={det_rows} {det_statuses}")
                print(f"    llm : UNAVAILABLE {exc.reason[:160]}")
                continue

            ext_l = call.extraction
            verdicts[ext_l.email_type] = verdicts.get(ext_l.email_type, 0) + 1
            det_final = sum(
                det_statuses.get(s, 0)
                for s in ("FINAL_SELECTED", "OFFERED")
            )
            if bool(det_final) != bool(ext_l.is_final()) or (
                ext_l.is_final() and len(ext_l.students) != det_rows
            ):
                disagreements += 1

            print(f"--- {row.gmail_message_id}  {row.subject[:70]}")
            print(
                f"    det : {taxonomy.category} rows={det_rows} {det_statuses}"
                f"  [{ext.category.name}]"
            )
            print(
                f"    llm : {ext_l.email_type} students={len(ext_l.students)}"
                f" conf={ext_l.confidence:.2f}"
                f" account={call.account_label}"
                f"{' failover' if call.failed_over else ''}"
            )
            if ext_l.evidence:
                print(f"          evidence: {ext_l.evidence[:170]}")
    finally:
        reset_service()

    print("\n=== summary ===")
    print(f"  verdicts            : {verdicts}")
    print(f"  deterministic-vs-LLM disagreements: {disagreements}")
    print(f"  LLM unavailable     : {failures}")
    print(f"  router stats        : {service.stats.as_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
