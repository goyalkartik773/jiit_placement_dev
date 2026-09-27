"""Validate the pipeline against 18 hand-labelled corpus emails.

The ground truth below was written once by reading each labelled message
in full; every expectation is a fact a human verified (category, company,
row counts, packages, deadlines, interview dates, funnel counts, links).

The script reads the labelled messages straight from PostgreSQL (via
``config``, so the DSN/password comes from the environment or the
git-ignored ``.env`` — never from source), runs them through the exact
``extract_email`` path the ingest uses, prints per-check results with
per-category accuracy, and writes ``reports/validation.md``.

Exit code 0 when every check passes, 1 otherwise (CI-friendly).
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # redirected/closed stdout
    pass

from placement_pipeline.ingest import (  # noqa: E402
    extract_email,
    fetch_attachment_texts,
    fetch_emails,
)

# ------------------------------------------------------------------ ground truth
# gm: gmail_message_id | cat: category | sub: sub-pattern | rows: student rows
# Values marked "accepted" reflect corpus quirks kept deliberately (the raw
# subject/company spelling is preserved in *_raw fields).

SAMPLES: list[dict[str, Any]] = [
    {
        "no": 1, "gm": "1a07f91284991c5c",
        "subject": "Infosys Niche Roles (SP & DSE) ... - Offers",
        "cat": "OFFER", "company": "Infosys", "rows": 37,
        "pkg": [2100000, 1600000, 1000000, 625000],
    },
    {
        "no": 2, "gm": "19e024fd393cbd5c",
        "subject": "Amazon - SDE intern (six months July-Dec 2026) ... - Offers",
        "cat": "OFFER", "company": "Amazon", "rows": 3,
        "pkg": 4638000, "stipend": 110000, "status": "extended",
    },
    {
        "no": 3, "gm": "1a0a93a7210d64bd",
        "subject": "Cognizant Mass Recruitment Drive ... - Final Offers",
        "cat": "OFFER", "company": "Cognizant", "rows": 54,
        "pkg": 400000, "role": "GenC", "status_ne": "withdrawn",
    },
    {
        "no": 4, "gm": "1a0a47528181e0b2",
        "subject": "ZS Associates-Pre Placement Offer From Batch 2027",
        "cat": "OFFER", "company": "ZS Associates", "rows": 5,
        "pkg": 1420600, "deadline": date(2026, 9, 15),
        "role": "Decision Analytics Associate (DAA) & Business Technology "
                "Solutions Associate (BTSA)",
    },
    {
        "no": 5, "gm": "1a0af47cccbc929a",
        "subject": "smartShift Technologies - Hiring Interns ... - Offers",
        "cat": "OFFER", "company": "smartShift Technologies", "rows": 8,
        "pkg": 500000, "stipend": 30000,
    },
    {
        "no": 6, "gm": "1a0b7ee6e5486c2a",
        "subject": "Keyence India - Hiring for Full Time Role ... - Offers",
        "cat": "OFFER", "company": "Keyence India", "rows": 4,
        "pkg": [604000, 730000], "role": "Consulting Sales Engineer",
        "reporting": (2027, 6),
    },
    {
        "no": 7, "gm": "19ed55cde526a30b",
        "subject": "Notification Regarding LTIMindtree (LTM) 2026 Batch Offers",
        "cat": "OFFER", "company": "LTIMindtree", "rows": 4,
        "status": "withdrawn",
    },
    {
        # company reads "Infosys" while raw keeps "HackWithInfy 2026" (alias)
        "no": 8, "gm": "19ef8e389b433689",
        "subject": "HackWithInfy 2026 - Batch 2027 - Selection Status",
        "cat": "OFFER", "company": "Infosys", "raw_has": "HackWithInfy",
        "rows": 232, "role_ne": "NO_SHOW NA",
    },
    {
        "no": 9, "gm": "1a02449f9b4a752f",
        "subject": "Decimal Point Analytics - DPA Vivechana 2026 - Register before 24 Aug",
        "cat": "OPPORTUNITY", "company": "Decimal Point Analytics", "rows": 0,
        "deadline": date(2026, 8, 24), "type": "hackathon",
        "interview_empty": True, "min_links": 1, "elig_nonempty": True,
    },
    {
        "no": 10, "gm": "19fdbfcbc7fffaf1",
        "subject": "Revised: DPA Vivechana 2026 - Apply by 11:00 AM, 08 August 2026",
        "cat": "OPPORTUNITY", "company": "Decimal Point Analytics", "rows": 0,
        "deadline": date(2026, 8, 8), "type": "hackathon",
        "elig_nonempty": True,
    },
    {
        "no": 11, "gm": "19efd53ceb632706",
        "subject": "Reminder: LTIMindtree Guest Lecture ... (25 June, 4:00 PM)",
        "cat": "OPPORTUNITY", "company": "LTIMindtree", "rows": 0,
        "type": "session", "link_contains": "teams.microsoft.com",
        "interview": [datetime(2026, 6, 25, 16, 0)],
        "elig": "Students of 2027 Graduating Batches",
    },
    {
        "no": 12, "gm": "19bd9bcddb127a67",
        "subject": "Placement Policy - 2027 Graduating Batches",
        "cat": "OTHER", "company_none": True, "deadline_none": True,
        "rows": 0,
    },
    {
        "no": 13, "gm": "1a06fde8ade47eab",
        "subject": "Accenture-Mass Recruitment Drive ... Deadline 10 PM on 6 Sep 2026",
        "cat": "SHORTLIST", "sub": "SHORTLIST_B", "company": "Accenture",
        "rows": 0, "counts": [393], "deadline": date(2026, 9, 6),
    },
    {
        # accepted quirk: GRiD contest classifies as contest | hackathon
        "no": 14, "gm": "19f22a0d0b4f11e3",
        "subject": 'Flipkart GRiD 8.0 "Prompt the Future" - Apply by 05 PM, 03 July 2026',
        "cat": "OPPORTUNITY", "company": "Flipkart", "rows": 0,
        "deadline": date(2026, 7, 3), "type": ["hackathon", "contest"],
        "link_contains": "forms.gle",
    },
    {
        "no": 15, "gm": "19f646701c4545ce",
        "subject": "Infosys - Registered Students List Rcvd from Infosys - IMP",
        "cat": "SHORTLIST", "sub": "SHORTLIST_A", "company": "Infosys",
        "rows": 1069,
        "interview": [datetime(2026, 8, 17), datetime(2026, 8, 18)],
    },
    {
        "no": 16, "gm": "19fe5f62bdf7f608",
        "subject": "HyperVerge - Shortlisted Students ... Report by 8:30 AM, 10 Aug 2026",
        "cat": "SHORTLIST", "sub": "SHORTLIST_A", "company": "HyperVerge",
        "rows": 128, "interview": [datetime(2026, 8, 10, 8, 30)],
    },
    {
        "no": 17, "gm": "19cb2021fb447e5f",
        "subject": "Amazon - Shortlist from Online Test ... Interviews 11 & 12 March 2026",
        "cat": "SHORTLIST", "sub": "SHORTLIST_B", "company": "Amazon",
        "rows": 0, "counts": [141],
        "interview": [datetime(2026, 3, 11), datetime(2026, 3, 12)],
    },
    {
        "no": 18, "gm": "19f2c3c4c248cc76",
        "subject": "HCLTech AMPlified: The AI Challenge - Shortlist - IMP",
        "cat": "SHORTLIST", "sub": "SHORTLIST_A", "company": "HCLTech",
        "rows": 50,
    },
]


# ------------------------------------------------------------------ evaluation

def _evaluate(gt: dict[str, Any], ext: Any) -> list[tuple[str, bool, str]]:
    """Run every expectation a sample declares; returns (check, ok, observed)."""
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, observed: Any = "") -> None:
        checks.append((name, bool(ok), str(observed)))

    add("category", ext.category.value == gt["cat"], ext.category.value)

    if "sub" in gt:
        sub = ext.sub_pattern.value if ext.sub_pattern else None
        add(f"sub_pattern == {gt['sub']}", sub == gt["sub"], sub)

    if "company" in gt:
        add(f"company == {gt['company']}", ext.company == gt["company"], ext.company)
    if gt.get("company_none"):
        add("company is none", ext.company is None, ext.company)
    if "raw_has" in gt:
        raw = ext.company_raw or ""
        add(f"company_raw has {gt['raw_has']!r}", gt["raw_has"] in raw, raw)

    if "rows" in gt:
        add(f"rows == {gt['rows']}", len(ext.students) == gt["rows"],
            len(ext.students))

    if "pkg" in gt:
        allowed = gt["pkg"] if isinstance(gt["pkg"], (list, tuple, set)) else [gt["pkg"]]
        add(f"package in {sorted(allowed)}", ext.package_inr in allowed,
            ext.package_inr)
    if "stipend" in gt:
        add(f"stipend == {gt['stipend']}", ext.stipend_inr == gt["stipend"],
            ext.stipend_inr)
    if "status" in gt:
        add(f"status == {gt['status']}", ext.status == gt["status"], ext.status)
    if "status_ne" in gt:
        add(f"status != {gt['status_ne']}", ext.status != gt["status_ne"],
            ext.status)
    if "role" in gt:
        add(f"role == {gt['role']!r}", ext.role == gt["role"], ext.role)
    if "role_ne" in gt:
        add(f"role != {gt['role_ne']!r}", ext.role != gt["role_ne"], ext.role)

    if "deadline" in gt:
        add(f"deadline == {gt['deadline']}", ext.deadline == gt["deadline"],
            ext.deadline)
    if gt.get("deadline_none"):
        add("deadline is none", ext.deadline is None, ext.deadline)

    have = {f.when for f in ext.interview_dates}
    if gt.get("interview_empty"):
        add("no schedule dates", not have, sorted(str(h) for h in have))
    if "interview" in gt:
        missing = [str(d) for d in gt["interview"] if d not in have]
        add("interview/reporting dates present", not missing,
            f"missing={missing} have={sorted(str(h) for h in have)}")
    if "reporting" in gt:
        ra = ext.reporting_at
        ok = ra is not None and (ra.year, ra.month) == tuple(gt["reporting"])
        add(f"reporting {gt['reporting'][0]}-{gt['reporting'][1]:02d}", ok, ra)

    if "counts" in gt:
        got = sorted({f.count for f in ext.funnel_counts})
        add(f"funnel counts contain {gt['counts']}",
            set(gt["counts"]) <= set(got), got)

    if "link_contains" in gt:
        urls = [lnk.url for lnk in ext.links]
        add(f"link has {gt['link_contains']!r}",
            any(gt["link_contains"] in u for u in urls), urls)
    if "min_links" in gt:
        add(f"links >= {gt['min_links']}", len(ext.links) >= gt["min_links"],
            len(ext.links))

    if "type" in gt:
        allowed = gt["type"] if isinstance(gt["type"], (list, set)) else [gt["type"]]
        add(f"type in {allowed}", ext.opportunity_type in allowed,
            ext.opportunity_type)
    if "elig" in gt:
        add("eligibility", ext.eligibility == gt["elig"], ext.eligibility)
    if gt.get("elig_nonempty"):
        add("eligibility/team rules present",
            bool(ext.eligibility) or bool(ext.team_rules),
            f"elig={bool(ext.eligibility)} team_rules={len(ext.team_rules)}")

    return checks


# ------------------------------------------------------------------ reporting

def _render(results: list[dict[str, Any]]) -> str:
    """Markdown report: per-sample table, failed checks, category accuracy."""
    lines = [
        "# Validation report — 18 hand-labelled corpus emails",
        "",
        "Generated by `scripts/run_validation.py` (deterministic: same corpus,",
        "same numbers). Ground truth was written by reading each message once;",
        "every expectation below is a fact a human verified.",
        "",
        "| # | category | subject (truncated) | checks | result |",
        "|---|----------|--------------------|--------|--------|",
    ]
    for r in results:
        passed = sum(1 for _, ok, _ in r["checks"] if ok)
        total = len(r["checks"])
        verdict = "PASS" if passed == total else f"FAIL ({total - passed} failed)"
        subject = r["gt"]["subject"]
        if len(subject) > 58:
            subject = subject[:55] + "..."
        lines.append(
            f"| {r['gt']['no']} | {r['gt']['cat']} | {subject} "
            f"| {passed}/{total} | {verdict} |"
        )

    failures = [
        (r["gt"], name, observed)
        for r in results
        for name, ok, observed in r["checks"]
        if not ok
    ]
    lines += ["", "## Failed checks", ""]
    if failures:
        for gt, name, observed in failures:
            lines.append(f"- **#{gt['no']}** `{name}` — observed: `{observed}`")
    else:
        lines.append("None — every check passed.")

    lines += ["", "## Accuracy by category", "",
              "| category | samples | passed | accuracy | checks passed |",
              "|----------|---------|--------|----------|---------------|"]
    cats: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        cats.setdefault(r["gt"]["cat"], []).append(r)
    total_samples = total_ok = total_checks = total_checks_ok = 0
    for cat in ("OFFER", "SHORTLIST", "OPPORTUNITY", "OTHER"):
        rs = cats.get(cat, [])
        ok = sum(
            1 for r in rs if all(ok for _, ok, _ in r["checks"])
        )
        checks = sum(len(r["checks"]) for r in rs)
        checks_ok = sum(
            1 for r in rs for _, ok, _ in r["checks"] if ok
        )
        acc = f"{100 * ok / len(rs):.1f}%" if rs else "n/a"
        lines.append(f"| {cat} | {len(rs)} | {ok} | {acc} "
                     f"| {checks_ok}/{checks} |")
        total_samples += len(rs)
        total_ok += ok
        total_checks += checks
        total_checks_ok += checks_ok
    acc = f"{100 * total_ok / total_samples:.1f}%" if total_samples else "n/a"
    lines.append(f"| **TOTAL** | **{total_samples}** | **{total_ok}** "
                 f"| **{acc}** | **{total_checks_ok}/{total_checks}** |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(f"Loading corpus from PostgreSQL ...")
    try:
        emails = fetch_emails()
        attachments = fetch_attachment_texts()
    except Exception as exc:  # predictable error, no traceback spam
        print(f"ERROR: cannot read the corpus ({exc.__class__.__name__}: {exc})",
              file=sys.stderr)
        print("Check PLACEMENT_PG_DSN / PLACEMENT_PG_PASSWORD (or .env).",
              file=sys.stderr)
        return 2

    by_gm = {e.gmail_message_id: e for e in emails}
    results: list[dict[str, Any]] = []
    for gt in SAMPLES:
        email = by_gm.get(gt["gm"])
        if email is None:
            results.append({
                "gt": gt,
                "checks": [("message found in corpus", False, gt["gm"])],
            })
            continue
        ext = extract_email(
            email, attachments.get(email.gmail_message_id, ())
        ).extraction
        results.append({"gt": gt, "checks": _evaluate(gt, ext)})

    report = _render(results)
    out = Path(__file__).resolve().parents[1] / "reports" / "validation.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    # console summary
    for r in results:
        bad = [(n, o) for n, ok, o in r["checks"] if not ok]
        mark = "ok" if not bad else f"{len(bad)} FAILED"
        print(f"#{r['gt']['no']:>2} {r['gt']['cat']:<11} "
              f"{len(r['checks']) - len(bad)}/{len(r['checks'])} {mark}")
        for name, observed in bad:
            print(f"      - {name}: observed {observed}")
    ok_samples = sum(1 for r in results
                     if all(ok for _, ok, _ in r["checks"]))
    checks = sum(len(r["checks"]) for r in results)
    checks_ok = sum(1 for r in results for _, ok, _ in r["checks"] if ok)
    print(f"\nSamples passed: {ok_samples}/{len(results)}  "
          f"Checks passed: {checks_ok}/{checks}")
    print(f"Report written to {out}")
    return 0 if ok_samples == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
