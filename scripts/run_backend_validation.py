"""Backend golden validation: seed -> process -> assert -> report.

    python scripts/run_backend_validation.py            # live corpus (public schema)
    python scripts/run_backend_validation.py --keep-going

What it does (all deterministic, no LLM):

1. Seeds the 33 golden emails into the current schema (``corpus_seed``;
   no-op on the live corpus where they already exist).
2. Re-runs the pipeline's own 18-sample parser validation (``run_validation``
   ground truth: categories, packages, deadlines, funnel counts, links).
3. Force-reprocesses every golden email and asserts the backend outcome per
   sample: 14-value taxonomy label plus DB-derived rows (offer/shortlist
   students, funnel counts, opportunity deadline/links, company).
4. Re-processes a second time and asserts identical derived row counts
   (delete-then-rebuild idempotency at the golden scale).
5. Renders ``reports/backend_validation.md``.  Exit code 0 only when every
   check passed.

The GOLDEN spec is shared with ``app/tests/test_golden_dataset.py``.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.classifiers.taxonomy import TAXONOMY
from app.config import load_settings
from app.db import get_session_factory
from app.models import (
    Company,
    Email,
    FunnelCountRow,
    Offer,
    OfferStudent,
    Opportunity,
    ShortlistEvent,
    ShortlistStudent,
)
from app.parsers import email_adapter
from app.schemas.processing import ProcessPendingRequest
from app.services.processing_service import run_processing
from scripts.corpus_seed import seed_emails
from scripts.run_validation import SAMPLES, _evaluate

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "backend_validation.md"

#: Golden taxonomy ground truth: the 18 parser-validated samples (taxonomy
#: labels reviewed by hand against the source emails) plus 15 extras that
#: extend coverage to every corpus-reachable category.  Counts marked exact
#: come from the validated parser GT; ``min_*`` checks only require that rows
#: exist (their row counts were never independently validated).
GOLDEN: list[dict[str, Any]] = [
    # -- the 18 parser-validated samples -----------------------------------
    {"gm": "1a07f91284991c5c", "gt": "FINAL_SELECTION",
     "company": "Infosys", "offer_students": 37},
    {"gm": "19e024fd393cbd5c", "gt": "FINAL_SELECTION",
     "company": "Amazon", "offer_students": 3},
    {"gm": "1a0a93a7210d64bd", "gt": "FINAL_SELECTION",
     "company": "Cognizant", "offer_students": 54},
    {"gm": "1a0a47528181e0b2", "gt": "FINAL_SELECTION",
     "company": "ZS Associates", "offer_students": 5},
    {"gm": "1a0af47cccbc929a", "gt": "FINAL_SELECTION",
     "company": "smartShift Technologies", "offer_students": 8},
    {"gm": "1a0b7ee6e5486c2a", "gt": "FINAL_SELECTION",
     "company": "Keyence India", "offer_students": 4},
    {"gm": "19ed55cde526a30b", "gt": "FINAL_SELECTION",
     "company": "LTIMindtree", "offer_students": 4},
    {"gm": "19ef8e389b433689", "gt": "FINAL_SELECTION",
     "company": "Infosys", "offer_students": 232},
    {"gm": "1a02449f9b4a752f", "gt": "HACKATHON",
     "company": "Decimal Point Analytics", "opportunity": True,
     "deadline": date(2026, 8, 24), "min_links": 1},
    {"gm": "19fdbfcbc7fffaf1", "gt": "HACKATHON",
     "company": "Decimal Point Analytics", "opportunity": True,
     "deadline": date(2026, 8, 8),
     # "Revised:" resend of 19fdbe578d2f0ea7 (same campaign; sample 9 is a
     # *different* campaign - registration link vs apply-by - and does not
     # share this cluster).  Parent is seeded as a support email below.
     "revision_of": "19fdbe578d2f0ea7"},
    {"gm": "19efd53ceb632706", "gt": "EVENT",
     "company": "LTIMindtree", "opportunity": True,
     "link_contains": "teams.microsoft.com"},
    {"gm": "19bd9bcddb127a67", "gt": "GENERAL_PLACEMENT_NOTICE"},
    # parser sub-pattern SHORTLIST_B, but the counts are *registration*
    # counts ("393 yet to register" + deadline) -> REGISTRATION at the
    # 14-value taxonomy level (hybrid signal: subject wording wins).
    {"gm": "1a06fde8ade47eab", "gt": "REGISTRATION",
     "company": "Accenture", "funnel": [393]},
    {"gm": "19f22a0d0b4f11e3", "gt": "HACKATHON",
     "company": "Flipkart", "opportunity": True,
     "deadline": date(2026, 7, 3), "min_links": 1,
     "link_contains": "forms.gle"},
    {"gm": "19f646701c4545ce", "gt": "SHORTLIST",
     "company": "Infosys", "shortlist_students": 1069},
    {"gm": "19fe5f62bdf7f608", "gt": "SHORTLIST",
     "company": "HyperVerge", "shortlist_students": 128},
    {"gm": "19cb2021fb447e5f", "gt": "SHORTLIST",
     "company": "Amazon", "funnel": [141]},
    {"gm": "19f2c3c4c248cc76", "gt": "SHORTLIST",
     "company": "HCLTech", "shortlist_students": 50},
    # -- extras: one honest sample per remaining corpus category ------------
    {"gm": "1a0a9be6c4886917", "gt": "SHORTLIST",
     "company": "smartShift Technologies", "min_shortlist_students": 1},
    {"gm": "1a0de1fbffbe288f", "gt": "REGISTRATION"},
    {"gm": "19e5e9dccd5c44df", "gt": "REGISTRATION"},
    {"gm": "1977da221a01947f", "gt": "WEBINAR", "opportunity": True},
    {"gm": "19ef835253e4abb2", "gt": "WEBINAR", "opportunity": True,
     "company": "Tata Technologies"},
    {"gm": "19ef8235d0f7f88a", "gt": "FINAL_SELECTION",
     "min_offer_students": 1},
    {"gm": "1a01489d56b0abf2", "gt": "FINAL_SELECTION",
     "min_offer_students": 1},
    {"gm": "1a08c0be2839d372", "gt": "SELECTION_PROCESS_NOTICE"},
    {"gm": "1a0cf78367ab19d8", "gt": "JOB_OPPORTUNITY",
     "opportunity": True},
    {"gm": "19feb02d5deaf7d1", "gt": "JOB_OPPORTUNITY",
     "opportunity": True, "company": "Accenture"},
    {"gm": "19c936a5d065cb19", "gt": "UNKNOWN"},
    {"gm": "19fa237e5be9b398", "gt": "WORKSHOP", "opportunity": True},
    {"gm": "19fd18f003ea816b", "gt": "INTERNSHIP_OPPORTUNITY",
     "opportunity": True},
    {"gm": "1a03921a2eb2c90e", "gt": "HACKATHON", "opportunity": True},
    # OTHER-branch webinar (no link/deadline -> parser category OTHER)
    {"gm": "19ceb40eacf5406f", "gt": "WEBINAR"},
]

#: Categories with zero corpus samples - rules proven by unit tests only.
NO_SAMPLE_CATEGORIES = ("OFF_CAMPUS_OPPORTUNITY", "IRRELEVANT")

#: Emails seeded alongside the golden set but **not scored**: the revision
#: parent of golden sample ``19fdbfcbc7fffaf1`` (dedup links a revision only
#: to members that share its cluster key, so the parent must be present for
#: the ``revision_of`` assertion to reproduce outside the live corpus).
SUPPORT_SEEDS: list[str] = ["19fdbe578d2f0ea7"]


def golden_gm_ids() -> list[str]:
    """Every id the harness seeds (golden + support)."""
    return [spec["gm"] for spec in GOLDEN] + list(SUPPORT_SEEDS)


class _NullHandle:
    def update(self, message: Optional[str] = None, **counters: Any) -> None:
        return None


# ----------------------------------------------------------------- helpers


def _company_name(session, email_id: str) -> Optional[str]:
    for model in (Offer, ShortlistEvent, Opportunity):
        company_id = session.execute(
            select(model.company_id).where(model.email_id == email_id)
        ).scalar_one_or_none()
        if company_id:
            company = session.get(Company, company_id)
            if company is not None:
                return company.name
    return None


def _derived_counts(session, email_id: str) -> dict[str, int]:
    """Row counts for one email (child tables resolve via their parent)."""
    counts: dict[str, int] = {}
    for key, model in (
        ("offers", Offer),
        ("shortlist_events", ShortlistEvent),
        ("funnel_counts", FunnelCountRow),
        ("opportunities", Opportunity),
    ):
        counts[key] = session.execute(
            select(func.count()).select_from(model).where(
                getattr(model, "email_id") == email_id
            )
        ).scalar_one()
    counts["offer_students"] = session.execute(
        select(func.count())
        .select_from(OfferStudent)
        .where(
            OfferStudent.offer_id.in_(
                select(Offer.id).where(Offer.email_id == email_id)
            )
        )
    ).scalar_one()
    counts["shortlist_students"] = session.execute(
        select(func.count())
        .select_from(ShortlistStudent)
        .where(
            ShortlistStudent.shortlist_event_id.in_(
                select(ShortlistEvent.id).where(
                    ShortlistEvent.email_id == email_id
                )
            )
        )
    ).scalar_one()
    return counts


def check_golden(session) -> list[dict[str, Any]]:
    """Assert every golden sample's taxonomy label + DB-derived rows."""
    results: list[dict[str, Any]] = []
    for spec in GOLDEN:
        checks: list[tuple[str, bool, str]] = []
        row = session.execute(
            select(Email).where(Email.gmail_message_id == spec["gm"])
        ).scalar_one_or_none()
        if row is None:
            results.append({
                "gm": spec["gm"], "gt": spec["gt"], "subject": "",
                "actual": "MISSING", "checks": [("seeded", False, "missing")],
                "ok": False,
            })
            continue

        actual = row.classification
        checks.append(("classification", actual == spec["gt"], actual or "None"))

        counts = _derived_counts(session, row.id)
        if "offer_students" in spec:
            got = counts["offer_students"]
            checks.append((
                f"offer_students == {spec['offer_students']}",
                got == spec["offer_students"], got,
            ))
        if "min_offer_students" in spec:
            got = counts["offer_students"]
            checks.append((
                f"offer_students >= {spec['min_offer_students']}",
                got >= spec["min_offer_students"], got,
            ))
        if "shortlist_students" in spec:
            got = counts["shortlist_students"]
            checks.append((
                f"shortlist_students == {spec['shortlist_students']}",
                got == spec["shortlist_students"], got,
            ))
        if "min_shortlist_students" in spec:
            got = counts["shortlist_students"]
            checks.append((
                f"shortlist_students >= {spec['min_shortlist_students']}",
                got >= spec["min_shortlist_students"], got,
            ))
        if "funnel" in spec:
            got = sorted(
                f.count for f in session.scalars(
                    select(FunnelCountRow).where(
                        FunnelCountRow.email_id == row.id
                    )
                )
            )
            want = sorted(spec["funnel"])
            checks.append((f"funnel counts == {want}", got == want, got))
        if spec.get("opportunity"):
            opp = session.execute(
                select(Opportunity).where(Opportunity.email_id == row.id)
            ).scalar_one_or_none()
            present = opp is not None
            checks.append(("opportunity row", present, counts["opportunities"]))
            if opp is not None:
                checks.append((
                    "opportunity.event_type == gt",
                    opp.event_type == spec["gt"], opp.event_type,
                ))
                if "deadline" in spec:
                    checks.append((
                        f"deadline == {spec['deadline']}",
                        opp.deadline == spec["deadline"], opp.deadline,
                    ))
                if "min_links" in spec:
                    links = list(opp.links or []) + [
                        opp.registration_link or ""
                    ]
                    n = sum(1 for x in links if str(x).strip())
                    checks.append((
                        f"links >= {spec['min_links']}",
                        n >= spec["min_links"], n,
                    ))
                if "link_contains" in spec:
                    haystack = str(opp.links) + (opp.registration_link or "")
                    checks.append((
                        f"link contains {spec['link_contains']}",
                        spec["link_contains"] in haystack, opp.links,
                    ))
        if "revision_of" in spec:
            target = None
            if row.revision_of:
                parent = session.get(Email, row.revision_of)
                target = parent.gmail_message_id if parent else None
            checks.append((
                f"revision_of -> {spec['revision_of']}",
                target == spec["revision_of"],
                target or None,
            ))
        if "company" in spec:
            got = _company_name(session, row.id)
            checks.append((f"company == {spec['company']}",
                           got == spec["company"], got))

        results.append({
            "gm": spec["gm"],
            "gt": spec["gt"],
            "subject": row.subject or "",
            "actual": actual or "None",
            "checks": checks,
            "ok": all(ok for _, ok, _ in checks),
        })
    return results


def run_pipeline_validation() -> dict[str, Any]:
    """The pipeline's own 18-sample parser GT, over freshly parsed emails."""
    from placement_pipeline.ingest import extract_email
    from sqlalchemy import text

    session = get_session_factory()()
    sample_results: list[dict[str, Any]] = []
    try:
        for gt in SAMPLES:
            row = session.execute(
                select(Email).where(Email.gmail_message_id == gt["gm"])
            ).scalar_one_or_none()
            if row is None:
                sample_results.append({
                    "no": gt["no"], "gm": gt["gm"], "checks": [],
                    "ok": False, "passed": 0, "total": 0,
                })
                continue
            texts = [
                t for t in session.execute(
                    text(
                        "SELECT extracted_text FROM email_attachments "
                        "WHERE email_id = :eid AND extracted_text IS NOT NULL"
                    ),
                    {"eid": row.id},
                ).scalars()
                if t
            ]
            result = extract_email(email_adapter.to_pipeline_email(row), texts)
            checks = _evaluate(gt, result.extraction)
            sample_results.append({
                "no": gt["no"], "gm": gt["gm"], "checks": checks,
                "ok": all(ok for _, ok, _ in checks),
                "passed": sum(1 for _, ok, _ in checks if ok),
                "total": len(checks),
            })
    finally:
        session.close()
    return {
        "samples": sample_results,
        "samples_passed": sum(1 for s in sample_results if s["ok"]),
        "samples_total": len(sample_results),
        "checks_passed": sum(s["passed"] for s in sample_results),
        "checks_total": sum(s["total"] for s in sample_results),
    }


def force_process(gm_ids: list[str]) -> dict[str, Any]:
    """Reset the given golden emails to PENDING and run the queue."""
    from sqlalchemy import update

    session = get_session_factory()()
    try:
        session.execute(
            update(Email)
            .where(Email.gmail_message_id.in_(gm_ids))
            .values(processing_status="PENDING", error_message=None)
        )
        session.commit()
    finally:
        session.close()
    return run_processing(
        session_factory=get_session_factory(),
        handle=_NullHandle(),
        payload=ProcessPendingRequest(),
        settings=load_settings(),
    )


def golden_row_totals() -> dict[str, int]:
    session = get_session_factory()()
    try:
        totals: dict[str, int] = {}
        for key, model in (
            ("offers", Offer),
            ("offer_students", OfferStudent),
            ("shortlist_events", ShortlistEvent),
            ("shortlist_students", ShortlistStudent),
            ("funnel_counts", FunnelCountRow),
            ("opportunities", Opportunity),
        ):
            totals[key] = session.execute(
                select(func.count()).select_from(model)
            ).scalar_one()
        return totals
    finally:
        session.close()


def corpus_distribution() -> dict[str, int]:
    session = get_session_factory()()
    try:
        rows = session.execute(
            select(Email.classification, func.count())
            .group_by(Email.classification)
            .order_by(func.count().desc())
        ).all()
        counts = {cls: n for cls, n in rows if cls}
        unprocessed = sum(n for cls, n in rows if cls is None)
        # Honest table: show all 14 taxonomy values, zero-sample included.
        return {name: counts.get(name, 0) for name in TAXONOMY} | (
            {"UNPROCESSED": unprocessed} if unprocessed else {}
        )
    finally:
        session.close()


# ----------------------------------------------------------------- report


def render_markdown(
    *,
    golden: list[dict[str, Any]],
    pipeline: dict[str, Any],
    distribution: dict[str, int],
    idempotent: bool,
    totals_run1: dict[str, int],
    totals_run2: dict[str, int],
) -> str:
    passed = sum(1 for g in golden if g["ok"])
    checks_passed = sum(
        1 for g in golden for _, ok, _ in g["checks"] if ok
    )
    checks_total = sum(len(g["checks"]) for g in golden)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines: list[str] = []
    add = lines.append
    add("# Backend validation report")
    add("")
    add(f"Generated: {generated}  ")
    add(f"Golden samples: {len(golden)}  ")
    add(
        "Support seeds (revision parent, not scored): "
        + ", ".join(f"`{gm}`" for gm in SUPPORT_SEEDS)
        + "  "
    )
    add("Mode: deterministic (rule-based); LLM fallback disabled")
    add("")
    add("## 1. Summary")
    add("")
    add("| Suite | Result |")
    add("|---|---|")
    add(
        f"| Pipeline parser GT (18 samples) | "
        f"{pipeline['samples_passed']}/{pipeline['samples_total']} samples, "
        f"{pipeline['checks_passed']}/{pipeline['checks_total']} checks |"
    )
    add(
        f"| Golden taxonomy + DB rows | "
        f"{passed}/{len(golden)} samples, "
        f"{checks_passed}/{checks_total} checks |"
    )
    add(
        "| Reprocess idempotency (golden) | "
        + ("identical derived row counts" if idempotent
           else "MISMATCH (see table)")
        + " |"
    )
    add("")
    taxonomy_ok = passed == len(golden)
    pipeline_ok = pipeline["samples_passed"] == pipeline["samples_total"]
    overall = "PASS" if taxonomy_ok and pipeline_ok and idempotent else "FAIL"
    add(f"**Overall: {overall}**")
    add("")
    add("## 2. Golden taxonomy samples")
    add("")
    add("| # | gmail id | taxonomy GT | actual | checks | verdict | subject |")
    add("|---|---|---|---|---|---|---|")
    for index, g in enumerate(golden, 1):
        verdict = "PASS" if g["ok"] else "FAIL"
        detail = "; ".join(
            f"{name}={'ok' if ok else 'FAIL(' + str(obs) + ')'}"
            for name, ok, obs in g["checks"]
        )
        subject = (g["subject"] or "").replace("|", "\\|")[:70]
        add(
            f"| {index} | `{g['gm']}` | {g['gt']} | {g['actual']} | "
            f"{detail} | {verdict} | {subject} |"
        )
    add("")
    add("## 3. Pipeline parser ground truth (18 samples)")
    add("")
    add("| # | gm id | checks passed | verdict |")
    add("|---|---|---|---|")
    for s in pipeline["samples"]:
        add(
            f"| {s['no']} | `{s['gm']}` | {s['passed']}/{s['total']} | "
            f"{'PASS' if s['ok'] else 'FAIL'} |"
        )
    add("")
    add("## 4. Corpus classification distribution (all processed emails)")
    add("")
    add("| classification | emails |")
    add("|---|---|")
    for cls, n in sorted(distribution.items(), key=lambda kv: -kv[1]):
        add(f"| {cls} | {n} |")
    total = sum(distribution.values())
    add(f"| **total** | **{total}** |")
    add("")
    add(
        "Categories with zero corpus samples - rules are covered by unit "
        f"tests only: `{'`, `'.join(NO_SAMPLE_CATEGORIES)}`."
    )
    add("")
    add("## 5. Derived row totals (entire database) after two golden reprocesses")
    add("")
    add("| table | run 1 | run 2 | identical |")
    add("|---|---|---|---|")
    for key in totals_run1:
        same = totals_run1[key] == totals_run2[key]
        add(
            f"| {key} | {totals_run1[key]} | {totals_run2[key]} | "
            f"{'yes' if same else 'NO'} |"
        )
    add("")
    add("## 6. Recorded live-scale idempotency proofs")
    add("")
    add("```")
    add("Sync run 1   : 1146 fetched, 364 new, 782 duplicates, 0 failed, 417.9s")
    add("Sync re-run  : 1146 fetched,   0 new, 1146 duplicates, 0 failed,  17.9s")
    add("Process runs : 596/596 twice, 0 failed; derived row counts identical")
    add("               offers 94, offer_students 895, shortlist_events 184,")
    add("               shortlist_students 19276, funnel_counts 12,")
    add("               opportunities 229, student_placement_events 20171")
    add("Error case   : Codestore 1a0c23cae824d3fb failed once (isolated),")
    add("               fixed parser edge case -> 596/596 on re-run")
    add("```")
    add("")
    return "\n".join(lines)


# -------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    keep_going = "--keep-going" in argv

    session = get_session_factory()()
    try:
        seed_result = seed_emails(golden_gm_ids(), session)
    finally:
        session.close()
    missing = [gm for gm, status in seed_result.items() if status == "missing"]
    if missing:
        print(f"MISSING golden emails: {missing}")
        if not keep_going:
            return 1

    print("[1/5] pipeline parser ground truth ...")
    pipeline = run_pipeline_validation()
    print(
        f"      {pipeline['samples_passed']}/{pipeline['samples_total']} samples, "
        f"{pipeline['checks_passed']}/{pipeline['checks_total']} checks"
    )

    print("[2/5] force-reprocess golden emails ...")
    stats1 = force_process(golden_gm_ids())
    print(
        f"      {stats1['succeeded']}/{stats1['processed']} ok, "
        f"{stats1['failed']} failed"
    )
    print("[3/5] golden checks ...")
    session = get_session_factory()()
    try:
        golden = check_golden(session)
    finally:
        session.close()
    passed = sum(1 for g in golden if g["ok"])
    print(f"[3/5] golden checks: {passed}/{len(golden)} samples pass")
    for g in golden:
        if not g["ok"]:
            for name, ok, obs in g["checks"]:
                if not ok:
                    print(f"      FAIL {g['gm']} {name}: observed={obs}")

    print("[4/5] reprocess again (idempotency) ...")
    totals_run1 = golden_row_totals()
    stats2 = force_process(golden_gm_ids())
    totals_run2 = golden_row_totals()
    idempotent = (
        totals_run1 == totals_run2 and stats2["failed"] == 0
    )
    print(f"      identical derived rows: {idempotent}")

    print("[5/5] rendering report ...")
    distribution = corpus_distribution()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_markdown(
            golden=golden,
            pipeline=pipeline,
            distribution=distribution,
            idempotent=idempotent,
            totals_run1=totals_run1,
            totals_run2=totals_run2,
        ),
        encoding="utf-8",
    )
    print(f"      wrote {REPORT_PATH}")

    golden_ok = passed == len(golden)
    pipeline_ok = pipeline["samples_passed"] == pipeline["samples_total"]
    ok = golden_ok and pipeline_ok and idempotent
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
