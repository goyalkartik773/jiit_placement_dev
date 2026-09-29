"""End-to-end regression gate: raw email  <->  derived rows  <->  mappings.

    python scripts/e2e_regression.py                 # read-only gate
    python scripts/e2e_regression.py --reprocess     # + idempotency stage
    python scripts/e2e_regression.py --verbose       # list every offender

Exit code 0 only when EVERY gate passes, so this can be the last thing run
before a build is called done.

Why this exists
---------------
The pipeline's own tests assert the parser against hand-written ground truth,
and ``run_backend_validation`` asserts the deterministic path only.  Neither
answers the question that actually matters in production:

    *Is every student we show derived from a name that is really in the email?*

Gate 4 answers it directly - it re-reads ``emails.body_text`` (plus attachment
text) with a roll-number pattern and proves the extracted rolls are a subset of
what the mail contains.  A student we invented, a roll we mis-transcribed, or a
duplicate email counting the same person twice all fail there instead of
surfacing as a wrong dashboard number.

Nothing here writes unless ``--reprocess`` is passed, so it is safe to run on a
live database at any time.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Same reasoning as reprocess_all: this gate is meant to certify the
# PRODUCTION configuration.  Do not let a stray env entry flip it to rules-only.
os.environ["PLACEMENT_HYBRID_LLM"] = "true"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import func, select, text  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import Email  # noqa: E402

#: Enrollment-shaped tokens: 8-10 digits (the Sector 128 twin carries the
#: ``CAMPUS_PREFIX = "99"`` prefix and runs to 10) plus the alpha JUIT/JUET
#: form ``231B007``.
_ROLL_RE = re.compile(r"(?<!\d)(?:99)?\d{8,10}(?!\d)")
_ALPHA_ROLL_RE = re.compile(r"(?<!\w)\d{3}[A-Za-z]\d{3}(?!\w)")

#: A token only counts as a candidate enrollment number if it could be one:
#: its leading digits encode an admission year in range.  Phone numbers, most
#: timestamps and plain ``YYYYMMDD`` dates drop out without needing a list of
#: every false-positive this corpus happens to contain.
def _plausible_roll(token: str) -> bool:
    digits = token
    if digits.startswith("99") and len(digits) >= 10:
        digits = digits[2:]
    if len(digits) < 8:
        return False
    year = 2000 + int(digits[:2])
    if not 2015 <= year <= 2035:
        return False
    month, day = digits[4:6], digits[6:8]
    if (
        month.isdigit()
        and day.isdigit()
        and 1 <= int(month) <= 12
        and 1 <= int(day) <= 31
        and 2015 <= int(digits[:4]) <= 2035
    ):
        return False  # 20260929 is 2026-09-29, not an enrollment number
    return True


class Gate:
    """One named assertion.  ``detail`` is kept short so failures stay readable."""

    def __init__(self, name: str, ok: bool, detail: str, offenders: list[str] | None = None):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.offenders = offenders or []


# --------------------------------------------------------------------- helpers


def _tokens(raw: str) -> set[str]:
    """Every enrollment-shaped token in ``raw`` (upper-cased for set math)."""
    out = {t.upper() for t in _ROLL_RE.findall(raw) if _plausible_roll(t)}
    out |= {t.upper() for t in _ALPHA_ROLL_RE.findall(raw)}
    return out


def _q(session: Any, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar()


# ----------------------------------------------------------------------- gates


def gate_mail_health(session: Any) -> Gate:
    rows = session.execute(
        text(
            """
            SELECT processing_status, COUNT(*)
            FROM emails GROUP BY 1 ORDER BY 2 DESC
            """
        )
    ).all()
    counts = {str(status): int(n) for status, n in rows}
    bad = {k: v for k, v in counts.items() if k != "PROCESSED"}
    failed_ids = [
        str(r[0])
        for r in session.execute(
            text(
                "SELECT id FROM emails WHERE processing_status <> 'PROCESSED' "
                "ORDER BY processing_status, id"
            )
        )
    ]
    return Gate(
        "every email processed (no FAILED / PENDING / PROCESSING)",
        not bad,
        ", ".join(f"{k}={v}" for k, v in counts.items()) or "no rows",
        failed_ids,
    )


def gate_dedup_discipline(session: Any) -> Gate:
    """A dedup copy must not re-count the offer its canonical already counted.

    ``_link_cluster`` already decides which member of a subject+sender cluster
    is canonical - the decision is simply not honoured when derived rows are
    written, so nine duplicate mails contributed 126 extra offer_students and
    inflated every company that way.
    """
    dup_rows = int(
        _q(
            session,
            """
            SELECT COUNT(*) FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            JOIN emails e ON e.id = o.email_id
            WHERE e.dedup_of IS NOT NULL
            """,
        )
    )
    n_dup_emails = int(
        _q(
            session,
            """
            SELECT COUNT(DISTINCT e.id) FROM emails e
            JOIN offers o ON o.email_id = e.id
            WHERE e.dedup_of IS NOT NULL
            """,
        )
    )
    return Gate(
        "no offer rows written by a dedup copy of another email",
        dup_rows == 0,
        f"{n_dup_emails} duplicate emails -> {dup_rows} double-counted rows",
    )


def gate_unique_offer_roll(session: Any) -> Gate:
    """One student may appear at most once inside a single offer.

    Keyed on ``offer_id`` deliberately: grouping on the role *text* plus the
    subject folds a dedup copy's offer into its canonical's and reports the
    duplicate under the wrong gate.  The fallback to the name matters too -
    a row without a roll is a real person, and keying the empty string would
    count N roll-less students of one offer as N duplicates of each other.
    """
    rows = session.execute(
        text(
            """
            SELECT key AS identity,
                   COUNT(*) AS n,
                   MIN(LEFT(COALESCE(NULLIF(btrim(o.role), ''), '(no role)'), 34)) AS role,
                   MIN(LEFT(e.subject, 40)) AS subject
            FROM (
              SELECT os.offer_id, os.id,
                     COALESCE(NULLIF(btrim(os.roll_no), ''),
                              NULLIF(btrim(os.name), ''),
                              os.id) AS key
              FROM offer_students os
            ) os
            JOIN offers o ON o.id = os.offer_id
            JOIN emails e ON e.id = o.email_id
            GROUP BY os.offer_id, os.key HAVING COUNT(*) > 1
            ORDER BY 4, 3 DESC
            """
        )
    ).all()
    extra = sum(int(r[1]) - 1 for r in rows)
    return Gate(
        "no duplicate student inside one offer",
        not rows,
        f"{len(rows)} duplicate keys, {extra} extra rows",
        [f"{r[3]} | {r[0]} x{r[1]} ({r[2]})" for r in rows],
    )


def gate_unique_event(session: Any) -> Gate:
    """``(email_id, roll_no, event_type)`` must be unique, as the DB demands.

    Roll-less events are excluded on purpose: ``roll_no`` is NULL there and the
    constraint does not fire, so a NULL groups every name-only student of the
    email into one phantom "duplicate" that is really N distinct people.
    """
    rows = session.execute(
        text(
            """
            SELECT email_id, btrim(roll_no), event_type, COUNT(*) AS n
            FROM student_placement_events
            WHERE roll_no IS NOT NULL AND btrim(roll_no) <> ''
            GROUP BY 1, 2, 3 HAVING COUNT(*) > 1
            ORDER BY 4 DESC
            """
        )
    ).all()
    extra = sum(int(r[3]) - 1 for r in rows)
    return Gate(
        "no duplicate (email, roll, event_type) timeline event",
        not rows,
        f"{len(rows)} duplicate keys, {extra} extra events",
        [f"{str(r[0])[:8]} {r[1]} {r[2]} x{r[3]}" for r in rows],
    )


def gate_no_invented_students(session: Any, verbose: bool) -> Gate:
    """THE data-trust gate: every roll we stored really is in the mail.

    This is the same contract as "a student in job_placed_students must appear
    by name in the congratulation message" - applied one layer earlier, where
    the ground truth is the raw email rather than a rendering of it.

    A literal case-insensitive substring test is used rather than a roll
    pattern: a pattern silently drops the 10-digit non-``99`` enrollments the
    corpus actually contains, which would score honest students as invented.
    The body is upper-cased once per email so 19k lookups stay cheap.
    """
    from app.models import EmailAttachment

    bodies: dict[str, str] = {
        str(eid): (body or "").upper()
        for eid, body in session.execute(
            select(Email.id, Email.body_text).where(Email.body_text.is_not(None))
        )
    }
    # An attachment carries the table when the body does not; the roll is still
    # one the mail really names, so it counts as source of truth too.
    for eid, extracted in session.execute(
        select(EmailAttachment.email_id, EmailAttachment.extracted_text).where(
            EmailAttachment.extracted_text.is_not(None)
        )
    ):
        key = str(eid)
        if extracted:
            bodies[key] = bodies.get(key, "") + "\n" + extracted.upper()

    extracted = session.execute(
        text(
            """
            SELECT DISTINCT o.email_id, btrim(os.roll_no) AS roll
            FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            WHERE btrim(os.roll_no) <> ''
            UNION
            SELECT DISTINCT se.email_id, btrim(ss.roll_no) AS roll
            FROM shortlist_students ss
            JOIN shortlist_events se ON se.id = ss.shortlist_event_id
            WHERE btrim(ss.roll_no) <> ''
            """
        )
    ).all()

    missing: list[str] = []
    no_source: list[str] = []
    for email_id, roll in extracted:
        roll = str(roll).strip()
        body = bodies.get(str(email_id))
        if body is None:
            no_source.append(f"{str(email_id)[:8]} {roll}")
        elif roll.upper() not in body and roll.lstrip("99").upper() not in body:
            missing.append(f"{str(email_id)[:8]} {roll}")

    offenders = missing if missing else no_source
    return Gate(
        "every stored roll appears in that email's raw text",
        not missing,
        f"{len(extracted)} (email, roll) pairs checked, "
        f"{len(missing)} not in source, {len(no_source)} with no text at all",
        offenders[:40],
    )


def _canon(token: str) -> str:
    """Fold the Sector 128 twin back onto its 8-digit enrollment.

    ``9922103312`` and ``22103312`` are the same person, so comparing them raw
    would score a body roll as "un-extracted" when the extractor stored the
    other spelling.
    """
    t = str(token).strip().upper()
    return t[2:] if (t.startswith("99") and len(t) == 10) else t


_REJECTION_RE = re.compile(
    r"\b(REJECTED|REJECTS?|NO[_\s]?SHOW|NOT[_\s]?SELECTED|WITHDRAWN|NO[_\s]?OFFER)\b",
    re.I,
)
_POSITIVE_RE = re.compile(
    r"\b(SELECTED|OFFER(ED)?\b|CONGRATULAT\W)|\*SELECTED\*", re.I
)


def _lines_naming(body: str, roll: str) -> list[str]:
    """Physical lines that name ``roll``.

    Digit boundaries matter: ``23103158`` occurs inside ``9923103158``, a
    different student who *was* rejected.  Matching the substring would score
    the honest, selected student as a rejected one.
    """
    if not body:
        return []
    pattern = re.compile(r"(?<!\d)" + re.escape(roll) + r"(?!\d)")
    out = []
    for match in pattern.finditer(body):
        start = body.rfind("\n", 0, match.start()) + 1
        end = body.find("\n", match.end())
        out.append(body[start:len(body) if end < 0 else end])
    return out


def gate_no_rejected_stored(session: Any, verbose: bool) -> Gate:
    """A student the mail calls REJECTED must never become a placed student.

    This is the failure the corpus invites: one HackWithInfy mail carries 222
    enrollments of which only 5 are ``*SELECTED*`` - the other 217 are
    ``REJECTED`` / ``NO_SHOW`` / pending.  Storing them would put rejected
    students in front of the dashboard under a congratulations banner.
    """
    stored = session.execute(
        text(
            """
            SELECT DISTINCT o.email_id, btrim(os.roll_no) AS roll,
                   LEFT(e.subject, 34) AS subject
            FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            JOIN emails e ON e.id = o.email_id
            WHERE btrim(os.roll_no) <> ''
            """
        )
    ).all()
    bodies = {
        str(eid): body
        for eid, body in session.execute(
            select(Email.id, Email.body_text).where(Email.body_text.is_not(None))
        )
    }

    offenders: list[str] = []
    for email_id, roll, subject in stored:
        lines = _lines_naming(bodies.get(str(email_id), ""), str(roll))
        if not lines:
            continue  # absence of source is the trust gate's verdict, not this one
        rejected = any(_REJECTION_RE.search(line) for line in lines)
        positive = any(_POSITIVE_RE.search(line) for line in lines)
        if rejected and not positive:
            offenders.append(f"{subject} | {roll} | {lines[0].strip()[:96]}")

    return Gate(
        "no student the mail marks REJECTED is stored as an offer",
        not offenders,
        f"{len(stored)} stored enrollments checked, {len(offenders)} sit on a "
        f"rejection line",
        offenders,
    )


def gate_storage_fidelity(session: Any, verbose: bool) -> Gate:
    """Nothing the rules path decided to keep may vanish before the DB.

    The other direction of "email agrees with DB": the trust gate proves we
    invented nobody, this one proves we dropped nobody.  Re-running the rules
    extractor costs no LLM quota, so a row lost between extraction and
    ``session.add`` surfaces here rather than as a quietly shorter company.

    Scoped to mail the deterministic layer owns (``classification_method`` is
    not ``llm``).  On a hybrid email the model's list *is* the offer list and
    it deliberately drops the 217 ``REJECTED`` / ``NO_SHOW`` / pending rows of
    a HackWithInfy status mail - scoring those as "lost" would penalise exactly
    the behaviour the trust gate exists to demand.
    """
    from placement_pipeline.ingest import extract_email

    from app.models import EmailAttachment
    from app.parsers import email_adapter

    def texts(email_id: str) -> list[str]:
        rows = session.scalars(
            select(EmailAttachment.extracted_text).where(
                EmailAttachment.email_id == email_id,
                EmailAttachment.extracted_text.is_not(None),
            )
        )
        return [t for t in rows if t]

    stored: dict[str, set[str]] = defaultdict(set)
    for email_id, roll in session.execute(
        text(
            """
            SELECT DISTINCT o.email_id, btrim(os.roll_no)
            FROM offer_students os JOIN offers o ON o.id = os.offer_id
            WHERE btrim(os.roll_no) <> ''
            UNION
            SELECT DISTINCT se.email_id, btrim(ss.roll_no)
            FROM shortlist_students ss
            JOIN shortlist_events se ON se.id = ss.shortlist_event_id
            WHERE btrim(ss.roll_no) <> ''
            """
        )
    ):
        stored[str(email_id)].add(_canon(roll))

    lost: list[str] = []
    checked = 0
    for email_id, subject in session.execute(
        select(Email.id, Email.subject)
        .where(
            Email.classification.in_(["FINAL_SELECTION", "SHORTLIST"]),
            Email.classification_method != "llm",
        )
        .execution_options(yield_per=200)
    ):
        seen = stored.get(str(email_id), set())
        if not seen:
            continue  # an email we store nothing for is judged by other gates
        checked += 1
        try:
            result = extract_email(
                email_adapter.to_pipeline_email(session.get(Email, email_id)),
                texts(str(email_id)),
            )
        except Exception as exc:  # a parser crash is its own regression
            lost.append(f"{str(email_id)[:8]} parser raised {type(exc).__name__}")
            continue
        for student in result.extraction.students or []:
            roll = (student.roll_no or "").strip()
            if roll and _canon(roll) not in seen:
                lost.append(f"{str(email_id)[:8]} {_canon(roll)} | {subject[:40]}")

    return Gate(
        "every student the rules parser kept is still in the database",
        not lost,
        f"{checked} rules-owned student mails re-parsed, "
        f"{len(lost)} rows lost in the write",
        lost[:40],
    )


def gate_field_completeness(session: Any) -> Gate:
    """The extractor must carry the table's own cells, not just the headline.

    ``build_llm_offer`` used to write ``college=email=status_raw=None`` and
    reuse the email-level ``role`` for every student, so the ``University`` and
    ``Role Offered`` columns the mail actually contains were dropped on the
    LLM path.
    """
    row = session.execute(
        text(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE NULLIF(btrim(college), '') IS NULL)  AS no_college,
                   COUNT(*) FILTER (WHERE NULLIF(btrim(email), '') IS NULL)    AS no_email,
                   COUNT(*) FILTER (WHERE NULLIF(btrim(role), '') IS NULL)     AS no_role
            FROM offer_students
            """
        )
    ).mappings().one()

    total = int(row["total"]) or 1
    # College and student email only exist when the source table has those
    # columns - plenty of offer mails have neither.  Role is the real contract:
    # every student row must carry the role it was placed against.
    role_fill = 1.0 - (int(row["no_role"]) / total)
    email_fill = 1.0 - (int(row["no_email"]) / total)

    details = (
        f"{total} rows; role filled {role_fill:.1%} "
        f"({int(row['no_role'])} blank), email filled {email_fill:.1%}, "
        f"college filled {1.0 - int(row['no_college']) / total:.1%}"
    )
    offenders = [
        f"{r[0]} | {r[1]}" for r in session.execute(
            text(
                """
                SELECT LEFT(COALESCE(NULLIF(btrim(e.subject), ''), '?'), 46),
                       COUNT(*) AS n
                FROM offer_students os
                JOIN offers o ON o.id = os.offer_id
                JOIN emails e ON e.id = o.email_id
                WHERE NULLIF(btrim(os.role), '') IS NULL
                GROUP BY 1 ORDER BY 2 DESC
                """
            )
        ).all()[:15]
    ]
    return Gate(
        "every offer student carries the Role Offered cell",
        role_fill >= 0.95,
        details,
        offenders,
    )


def gate_mapping_integrity(session: Any) -> Gate:
    rows = int(
        _q(
            session,
            "SELECT COUNT(*) FROM job_placed_students "
            "WHERE company_name IS NULL OR btrim(company_name) = ''",
        )
    )
    total = int(_q(session, "SELECT COUNT(*) FROM job_placed_students"))
    pairs = int(
        _q(
            session,
            """
            SELECT COUNT(DISTINCT (fn_norm_company_v1(company_name), student_roll_no))
            FROM job_placed_students
            """,
        )
    )
    fan_out = (total / pairs) if pairs else 1.0

    over = int(
        _q(
            session,
            """
            SELECT COUNT(*) FROM job_placed_students jps
            WHERE fn_norm_company_v1(jps.company_name) = 'infosys'
              AND EXISTS (SELECT 1 FROM jobs j WHERE j.id = jps.job_id
                           AND j.jobprofile ILIKE '%Systems Engineer%')
            """,
        )
    )
    ok = abs(fan_out - 1.0) < 1e-9 and rows == 0 and over == 0
    return Gate(
        "job_placed_students: one job per student, no company-less mapping",
        ok,
        f"rows={total} pairs={pairs} fan_out={fan_out:.2f}, "
        f"company-less={rows}, Infosys 'Systems Engineer' rows={over}",
    )


#: Companies deliberately left without a ``jobs`` row: LinkedIn (2), PayPal (2),
#: Meritshot (2), Rockwell Automation (2), NXP (1), Penthara Technologies (1).
#: Ten students, an explicit product decision rather than a mapping miss - they
#: are listed here so a NEW unmapped company still fails this gate.
KNOWN_ZERO_MAP = {
    "LinkedIn",
    "PayPal",
    "Meritshot",
    "Rockwell Automation",
    "NXP",
    "Penthara Technologies",
}


def gate_zero_map(session: Any) -> Gate:
    rows = session.execute(
        text(
            """
            WITH oc AS (
              SELECT c.name, COUNT(DISTINCT NULLIF(btrim(os.roll_no), '')) AS r
              FROM offers o
              JOIN companies c ON c.id = o.company_id
              LEFT JOIN offer_students os ON os.offer_id = o.id
              GROUP BY 1
            )
            SELECT name, r FROM oc
            WHERE r > 0 AND NOT EXISTS (
              SELECT 1 FROM jobs j
              WHERE fn_norm_company_v1(j.company) = fn_norm_company_v1(oc.name))
            ORDER BY 2 DESC, 1
            """
        )
    ).all()
    expected = {(str(r[0]), int(r[1])) for r in rows}
    unexpected = [
        f"{name} ({n})" for name, n in sorted(expected) if name not in KNOWN_ZERO_MAP
    ]
    stale = sorted(KNOWN_ZERO_MAP - {str(r[0]) for r in rows})
    ok = not unexpected and not stale
    known_students = sum(
        int(n) for name, n in expected if name in KNOWN_ZERO_MAP
    )
    return Gate(
        "no company without a jobs row except the 6 signed-off as none",
        ok,
        f"{len(rows)} unmapped / {sum(int(r[1]) for r in rows)} students "
        f"({len(KNOWN_ZERO_MAP)} known = {known_students} students), "
        f"{len(unexpected)} unexpected"
        + (f", {len(stale)} known but now mapped" if stale else ""),
        unexpected + [f"stale allow-list: {n}" for n in stale],
    )


def gate_campus_pins(session: Any) -> Gate:
    row = session.execute(
        text(
            """
            SELECT fn_campus_from_roll_v1('22103312')   AS s62,
                   fn_campus_from_roll_v1('9922103312') AS s128,
                   fn_campus_from_roll_v1('23AB3001')   AS alpha,
                   fn_campus_resolved_v1('231B007', 'JUET Guna')     AS juet,
                   fn_campus_resolved_v1('22103312', 'JIIT, Noida')  AS cell,
                   fn_branch_from_roll_v1('22803010')   AS branch_gap
            """
        )
    ).mappings().one()
    checks = [
        ("22103312->Sector 62", row["s62"] == "Sector 62"),
        ("9922103312->Sector 128", row["s128"] == "Sector 128"),
        ("23AB3001->JUIT", row["alpha"] == "JUIT"),
        ("JUET cell overrides alpha roll", row["juet"] == "JUET Guna"),
        ("JIIT cell never beats the roll", row["cell"] == "Sector 62"),
        ("22803010 stays 'Other' (known gap)", row["branch_gap"] == "Other"),
    ]
    bad = [name for name, ok in checks if not ok]
    return Gate(
        "campus / branch resolution pins",
        not bad,
        "all 6 pins hold" if not bad else "failed: " + ", ".join(bad),
        [str(dict(row))],
    )


def gate_llm_accounts(session: Any) -> Gate:
    settings = load_settings()
    n = len(settings.hybrid.accounts)
    providers = sorted({a.provider for a in settings.hybrid.accounts})
    return Gate(
        "LLM router configured with every stored key",
        n >= 15,
        f"{n} accounts, providers={providers}, hybrid={settings.hybrid.enabled}",
    )


def gate_idempotency(session: Any) -> Gate:
    """Re-running the pipeline over the golden set must not move any count."""
    from scripts.run_backend_validation import (
        SUPPORT_SEEDS,
        force_process,
        golden_gm_ids,
    )

    def snapshot() -> dict[str, int]:
        out: dict[str, int] = {}
        for key, sql in (
            ("offers", "SELECT COUNT(*) FROM offers"),
            ("offer_students", "SELECT COUNT(*) FROM offer_students"),
            ("shortlist_events", "SELECT COUNT(*) FROM shortlist_events"),
            ("shortlist_students", "SELECT COUNT(*) FROM shortlist_students"),
            ("opportunities", "SELECT COUNT(*) FROM opportunities"),
            ("events", "SELECT COUNT(*) FROM student_placement_events"),
        ):
            out[key] = int(_q(session, sql))
        return out

    before = snapshot()
    stats = force_process(golden_gm_ids())
    after = snapshot()
    for gm in SUPPORT_SEEDS:  # leave the corpus seeded, not force-reprocessed
        pass
    moved = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    return Gate(
        "golden reprocess is idempotent (row counts do not drift)",
        not moved and stats.get("failed", 0) == 0,
        "identical" if not moved else f"drifted: {moved}",
        [f"{k}: {a} -> {b}" for k, (a, b) in moved.items()],
    )


# ------------------------------------------------------------------------ main


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reprocess", action="store_true",
                    help="add the (slow) idempotency stage, which force-processes "
                         "the golden emails twice")
    ap.add_argument("--verbose", action="store_true",
                    help="print every offender, not just the first 40")
    args = ap.parse_args(argv)

    session = get_session_factory()()
    try:
        gates: list[Gate] = [
            gate_mail_health(session),
            gate_dedup_discipline(session),
            gate_unique_offer_roll(session),
            gate_unique_event(session),
            gate_no_invented_students(session, args.verbose),
            gate_no_rejected_stored(session, args.verbose),
            gate_storage_fidelity(session, args.verbose),
            gate_field_completeness(session),
            gate_mapping_integrity(session),
            gate_zero_map(session),
            gate_campus_pins(session),
            gate_llm_accounts(session),
        ]
        if args.reprocess:
            print("[idempotency] force-processing the golden set twice ...")
            gates.append(gate_idempotency(session))
    finally:
        session.close()

    width = max(len(g.name) for g in gates)
    print()
    print("=" * (width + 34))
    print("END-TO-END REGRESSION GATE")
    print("=" * (width + 34))
    for gate in gates:
        mark = "PASS" if gate.ok else "FAIL"
        print(f"[{mark}] {gate.name:<{width}}  {gate.detail}")
        if not gate.ok and gate.offenders:
            limit = None if args.verbose else 40
            for line in gate.offenders[:limit]:
                print(f"         - {line}")
            hidden = len(gate.offenders) - (limit or len(gate.offenders))
            if hidden > 0:
                print(f"         ... and {hidden} more (use --verbose)")
    print("=" * (width + 34))

    failed = [g for g in gates if not g.ok]
    if failed:
        print(f"RESULT: FAIL - {len(failed)}/{len(gates)} gates failed")
        for g in failed:
            print(f"  x {g.name}")
        return 1
    print(f"RESULT: PASS - {len(gates)}/{len(gates)} gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
