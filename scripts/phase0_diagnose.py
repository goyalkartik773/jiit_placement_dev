"""PHASE 0 - production data-integrity diagnosis (read-only).

    python scripts/phase0_diagnose.py            # full corpus report
    python scripts/phase0_diagnose.py --sample 5 # print 5 concrete email bodies

Question being answered, with evidence from real rows and real email bodies:

    Is every student currently marked FINAL_SELECTED / OFFERED actually a
    student the source email says was *offered* the role - or did a
    shortlist / round-progress / no-show / rejected row slip into the
    "placed" set?

For every ``offer_students`` row we locate the student's own line inside the
source email body, recover the section title that line sits under, and decide
whether that section states a *final offer*.  Nothing is written: the script
only reads ``emails``, ``offers``, ``offer_students``,
``student_placement_events`` and ``job_placed_students``.

It also probes the four suspected failure modes named in the brief:

    A. coarse classifier firing on "selected"/"Congratulations" wording
    B. subject-line rule matching on quoted/forwarded content
    C. extractor defaulting every extracted row to FINAL_SELECTED/OFFERED
    D. dedup/cluster merging a shortlist event into an offer event

Output: ``reports/phase0_diagnosis.md`` + a short stdout summary.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):  # redirected/closed stdout
    pass

# Importing placement_pipeline.config loads the git-ignored .env (env-only
# secrets; the DSN/password are never printed).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg2  # noqa: E402
from psycopg2.extras import RealDictCursor  # noqa: E402

from placement_pipeline.config import PG_DSN  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "phase0_diagnosis_data.md"

# --------------------------------------------------------------------------- #
# What counts as "the email says this student was NOT offered the role"
# --------------------------------------------------------------------------- #

#: Section titles that describe a stage *before* an offer (or a non-outcome).
NON_OFFER_TITLE_RE = re.compile(
    r"pending|await|no\s*shows?|not\s*selected|reject|shortlist|interview\s*(date|schedule)"
    r"|next\s+round|further\s+round|subsequent\s+round|wait\s*list|on\s+hold"
    r"|registrat|eligible|reporting\s+time|assessment|drive\s+labs",
    re.I,
)

#: A per-row status cell that itself denies an offer.
NON_OFFER_STATUS_RE = re.compile(
    r"reject|no[_\s]?show|not\s*selected|not\s*cleared|pending|wait\s*list|on\s+hold"
    r"|shortlist|disqualif|absent",
    re.I,
)

#: A per-row status cell that confirms an offer.
OFFER_STATUS_RE = re.compile(r"select|offer|hire|ppo|chosen|clear(ed)?|convert", re.I)

#: Row/serial cells are not section titles.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.\w{2,}")
_HEADER_RE = re.compile(r"^\s*s\.?\s*no\b", re.I)


def _is_section_title(line: str) -> bool:
    """Heuristic: is this line a section heading rather than a table row?"""
    text = line.strip()
    if not text or len(text) > 140:
        return False
    if _HEADER_RE.match(text):
        return False
    if _EMAIL_RE.search(text):
        return False
    # Real rows start with a serial number ("12 ..." / "12)").
    if re.match(r"^\d{1,4}\s*[.)\-Ã¢â‚¬â€œ]?\s+\S", text) and len(text) > 40:
        return False
    return True


def build_section_map(body: str) -> dict[int, str]:
    """Map a body line number -> the section title that line sits under."""
    lines = body.splitlines()
    # Pass 1: record the line number of every table header.
    headers = [i for i, ln in enumerate(lines) if _HEADER_RE.match(ln)]
    titles: dict[int, str] = {}

    for h in headers:
        # The title is the nearest preceding line that reads like a heading.
        title = ""
        for j in range(h - 1, max(-1, h - 12), -1):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if _HEADER_RE.match(candidate):
                break
            if _is_section_title(candidate):
                title = candidate
                break
        start = h
        titles[start] = title
        # Rows run until the next header or an explicit section heading.
        # A heading is recognised by its trailing colon ("List of Students'
        # status of pending Interviews as on 24 June 2026:") or a bullet
        # marker -- short wrapped fragments ("Noida", "Engineer (Trainee)")
        # must NOT end the table, they belong to the row above them.
        end = len(lines)
        for k in range(h + 1, len(lines)):
            if _HEADER_RE.match(lines[k]):
                end = k
                break
            cand = lines[k].strip()
            if not cand or k <= h + 1:
                continue
            if _is_section_title(cand) and (
                cand.endswith(":")
                or cand.startswith(("·", "-", "* ", "•"))
            ):
                end = k
                break
        for k in range(start, end):
            titles[k] = title
    return titles


def find_student_line(body: str, roll: Optional[str], email_addr: Optional[str],
                      name: Optional[str]) -> Optional[int]:
    """Best-effort: the 0-based line index where this student's row appears."""
    lines = body.splitlines()
    needles: list[str] = []
    if roll:
        needles.append(roll.strip())
    if email_addr and "@" in email_addr:
        needles.append(email_addr.strip().lower())
    for needle in needles:
        low = needle.lower()
        for i, ln in enumerate(lines):
            if low in ln.lower():
                return i
    if name and len(name) >= 6:
        # Whole-name match only, to avoid the first name hitting on its own.
        token = r"\s+".join(re.escape(part) for part in name.split())
        m = re.search(rf"\b{token}\b", body, re.I)
        if m:
            return body[: m.start()].count("\n")
    return None


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #

#: Every row that is *currently* recorded as an offer / final selection, joined
#: to the offer row it came from and to the source email body.  Rows with no
#: matching event are not "marked" and are skipped (Phase 0 asks only about
#: students currently on record as FINAL_SELECTED / OFFERED).
#:
#: ``body_clean`` is the quote-stripped body; ``body_text`` is the raw body the
#: parser actually reads (a forwarded/earlier announcement stays in it).  Both
#: are fetched so a row can be located whichever one it came from.
Q_OFFER_ROWS = """
SELECT o.email_id,
       e.subject,
       e.body_clean,
       e.body_text,
       os.roll_no,
       os.name,
       os.email        AS student_email,
       os.status_raw,
       s.normalized_status,
       s.event_type
  FROM student_placement_events s
  JOIN emails e        ON e.id = s.email_id
  JOIN offers o        ON o.email_id = e.id
  JOIN offer_students os ON os.offer_id = o.id AND os.roll_no = s.roll_no
 WHERE s.normalized_status IN ('FINAL_SELECTED', 'OFFERED')
   AND e.classification = 'FINAL_SELECTION'
"""

Q_EVENTS = """
SELECT s.roll_no, s.email_id, s.event_type, s.normalized_status, e.classification
  FROM student_placement_events s
  JOIN emails e ON e.id = s.email_id
 WHERE s.normalized_status IN ('FINAL_SELECTED', 'OFFERED')
"""

Q_CORPUS = """
SELECT id, subject, classification, classification_signals, body_clean,
       dedup_of, revision_of, cluster_key, is_canonical
  FROM emails
"""


def connect():
    return psycopg2.connect(PG_DSN)


def analyse_offer_rows(cur) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cur.execute(Q_OFFER_ROWS)
    rows = cur.fetchall()
    cache: dict[tuple[str, str], dict[int, str]] = {}
    findings: list[dict[str, Any]] = []

    for r in rows:
        clean = r["body_clean"] or ""
        raw = r["body_text"] or ""
        # Prefer the quote-stripped body; fall back to the raw body, which is
        # where a forwarded/earlier announcement lives and which the parser
        # actually reads.
        line_idx = find_student_line(clean, r["roll_no"], r["student_email"], r["name"])
        body, source = clean, "body_clean"
        if line_idx is None:
            line_idx = find_student_line(raw, r["roll_no"], r["student_email"], r["name"])
            body, source = raw, "body_text"
        cache_key = (r["email_id"], source)
        if cache_key not in cache:
            cache[cache_key] = build_section_map(body)
        title = cache[cache_key].get(line_idx, "") if line_idx is not None else ""
        status_raw = (r["status_raw"] or "").strip()

        # The status cell is the strongest evidence and needs no line lookup.
        if status_raw and NON_OFFER_STATUS_RE.search(status_raw):
            verdict, reason = "WRONG", f"status cell in email says {status_raw!r}"
        elif line_idx is None:
            verdict, reason = "UNLOCATED", "student row not found in body (manual read needed)"
        elif not status_raw and title and NON_OFFER_TITLE_RE.search(title):
            verdict, reason = "WRONG", f"row sits under non-offer section {title!r}"
        else:
            verdict = "OK"
            reason = (f"status cell {status_raw!r}" if status_raw
                      else f"no status cell, section says offer ({title[:50]!r})")

        findings.append(
            {
                "email_id": r["email_id"],
                "subject": r["subject"],
                "roll_no": r["roll_no"],
                "name": r["name"],
                "status_raw": status_raw,
                "section_title": title,
                "line": line_idx,
                "body_source": source,
                "written_status": r["normalized_status"],
                "event_type": r["event_type"],
                "verdict": verdict,
                "reason": reason,
            }
        )

    totals = Counter(f["verdict"] for f in findings)
    return findings, dict(totals)


def only_evidence_counts(cur, findings: list[dict[str, Any]]) -> dict[str, int]:
    """Of the WRONG rows, how many students have no genuine offer elsewhere?"""
    wrong = [f for f in findings if f["verdict"] == "WRONG" and f["roll_no"]]
    if not wrong:
        return {"wrong_rows": 0, "students_only_wrong": 0}
    pairs = {(f["email_id"], f["roll_no"].strip()) for f in wrong}
    cur.execute(
        """
        SELECT DISTINCT s.roll_no, s.email_id
          FROM student_placement_events s
         WHERE s.normalized_status IN ('FINAL_SELECTED', 'OFFERED')
        """
    )
    good: dict[str, set[str]] = defaultdict(set)
    for row in cur.fetchall():
        good[(row["roll_no"] or "").strip()].add(row["email_id"])

    only = 0
    for email_id, roll in pairs:
        others = good.get(roll, set()) - {email_id}
        # Another *offer-bearing* email would be a different source email; the
        # row itself is still wrong here, but the student is only on record
        # because of this row when no other offer source exists.
        if not others:
            only += 1
    return {"wrong_rows": len(pairs), "students_only_wrong": only}


def failure_mode_probes(cur) -> dict[str, Any]:
    """Targeted probes for the four failure modes named in the brief."""
    out: dict[str, Any] = {}

    # A. coarse classifier: shortlist-flavoured wording inside OFFER emails and
    #    offer-flavoured wording inside SHORTLIST emails.
    cur.execute(
        r"""
        SELECT classification, count(*)
          FROM emails
         WHERE lower(body_clean) ~ 'selected for the (next|following|subsequent) round'
            OR lower(body_clean) ~ 'students? selected for'
         GROUP BY 1 ORDER BY 2 DESC
        """
    )
    out["body_says_selected_for_next_round"] = {
        r["classification"]: r["count"] for r in cur.fetchall()
    }

    cur.execute(
        r"""
        SELECT classification, count(*) FROM emails
         WHERE lower(subject) ~ 'shortlist|short-listed'
         GROUP BY 1 ORDER BY 2 DESC
        """
    )
    out["subject_says_shortlist"] = {
        r["classification"]: r["count"] for r in cur.fetchall()
    }

    # B. subject rule matching quoted/forwarded content: is the stored subject
    #    ever the quoted one?  (Signals record which rule fired.)
    cur.execute(
        """
        SELECT classification,
               (SELECT string_agg(x, ' + ') FROM json_array_elements_text(classification_signals) x
                 WHERE x LIKE 'parser:%') AS sig,
               count(*)
          FROM emails
         GROUP BY 1, 2
         ORDER BY 3 DESC
        """
    )
    out["rules_by_classification"] = [tuple(r.values()) for r in cur.fetchall()]

    # C. extractor defaulting: rows whose status cell denies an offer but that
    #    were written as offered/final_selected.
    cur.execute(
        r"""
        SELECT os.status_raw, s.normalized_status, count(*)
          FROM student_placement_events s
          JOIN offers o        ON o.email_id = s.email_id
          JOIN offer_students os ON os.offer_id = o.id AND os.roll_no = s.roll_no
         WHERE s.event_type IN ('offer', 'final_selection')
           AND os.status_raw ~* 'reject|no[_ ]?show|pending|waitlist|shortlist|not selected'
         GROUP BY 1, 2 ORDER BY 3 DESC
        """
    )
    out["status_cell_denies_offer"] = cur.fetchall()

    # D. dedup/cluster: same student+company where a shortlist source and an
    #    offer source disagree, and whether non-canonical copies both wrote.
    cur.execute(
        """
        SELECT count(*) FILTER (WHERE dedup_of IS NOT NULL),
               count(*) FILTER (WHERE revision_of IS NOT NULL),
               count(*) FILTER (WHERE is_canonical = false)
          FROM emails
        """
    )
    out["dedup_revision_noncanonical"] = list(cur.fetchall()[0].values())

    cur.execute(
        """
        SELECT count(*) FROM (
          SELECT s.roll_no, o.company_id
            FROM student_placement_events s
            JOIN offers o ON o.email_id = s.email_id
           WHERE s.normalized_status IN ('FINAL_SELECTED','OFFERED')
           GROUP BY 1, 2
          HAVING bool_or(s.event_type = 'final_selection')
             AND bool_or(s.event_type = 'offer')
        ) t
        """
    )
    out["students_with_both_event_types"] = list(cur.fetchall()[0].values())[0]

    # Non-canonical duplicate copies that produced their own offer rows.
    cur.execute(
        """
        SELECT count(*) FROM emails e
         WHERE e.is_canonical = false
           AND e.classification = 'FINAL_SELECTION'
           AND EXISTS (SELECT 1 FROM offers o WHERE o.email_id = e.id)
        """
    )
    out["noncanonical_emails_with_offer_rows"] = list(cur.fetchall()[0].values())[0]

    # Production surface: mappings the college UI shows as "placed".
    cur.execute(
        """
        SELECT count(*) FROM job_placed_students
        """
    )
    out["job_placed_students_total"] = list(cur.fetchall()[0].values())[0]

    # Mappings built from a row whose status cell denies an offer, or from a
    # row of the known pending-interview tables.
    cur.execute(
        r"""
        SELECT count(*) FROM job_placed_students j
         WHERE EXISTS (SELECT 1 FROM offer_students os
                        WHERE trim(os.roll_no) = j.student_roll_no
                          AND os.status_raw ~* 'reject|no[_ ]?show')
        """
    )
    out["mappings_from_denied_status"] = list(cur.fetchall()[0].values())[0]

    # Marked events that do not join back to the offer row they came from.
    cur.execute(
        """
        SELECT count(*) FROM student_placement_events s
          LEFT JOIN offers o ON o.email_id = s.email_id
          LEFT JOIN offer_students os ON os.offer_id = o.id AND os.roll_no = s.roll_no
         WHERE s.normalized_status IN ('FINAL_SELECTED','OFFERED')
           AND os.roll_no IS NULL
        """
    )
    out["marked_events_without_offer_row"] = list(cur.fetchall()[0].values())[0]

    # Dedup detail: students whose final_selection event came from a
    # non-canonical / revision copy of a message (route D candidates).
    cur.execute(
        """
        SELECT count(DISTINCT s.roll_no)
          FROM student_placement_events s
          JOIN emails e ON e.id = s.email_id
         WHERE s.normalized_status IN ('FINAL_SELECTED','OFFERED')
           AND (e.is_canonical = false OR e.dedup_of IS NOT NULL OR e.revision_of IS NOT NULL)
        """
    )
    out["marked_students_from_noncanonical_copy"] = list(cur.fetchall()[0].values())[0]
    return out


def write_report(findings: list[dict[str, Any]], totals: dict[str, int],
                 only_ev: dict[str, int], probes: dict[str, Any]) -> str:
    by_email: dict[str, dict[str, Any]] = {}
    for f in findings:
        bucket = by_email.setdefault(
            f["email_id"],
            {"subject": f["subject"], "wrong": [], "ok": 0},
        )
        if f["verdict"] == "WRONG":
            bucket["wrong"].append(f)
        else:
            bucket["ok"] += 1

    bad = {k: v for k, v in by_email.items() if v["wrong"]}
    lines: list[str] = []
    add = lines.append

    add("# Phase 0 - diagnosis: `FINAL_SELECTED` / `OFFERED` vs the source email")
    add("")
    add("Read-only cross-check of every `offer_students` row that feeds a "
        "`FINAL_SELECTED` / `OFFERED` event, matched back to the student's own "
        "line inside the real email body.")
    add("")
    add("## Headline numbers")
    add("")
    add(f"- offer rows examined (source email classified `FINAL_SELECTION`): **{len(findings)}**")
    add(f"- rows the source email really does present as an offer: **{totals.get('OK', 0)}**")
    add(f"- rows wrongly presented as an offer: **{totals.get('WRONG', 0)}** "
        f"({(totals.get('WRONG', 0) / max(len(findings), 1)) * 100:.1f}%)")
    add(f"- distinct students whose *only* `FINAL_SELECTED`/`OFFERED` evidence is "
        f"such a wrong row: **{only_ev.get('students_only_wrong', 0)}**")
    add(f"- `job_placed_students` rows served to the college UI today: "
        f"**{probes.get('job_placed_students_total', 0)}**")
    add("")
    add("## Confirmed misclassifications by failure mode")
    add("")
    add("| # | Failure mode | Rows | Notes |")
    add("|---|---|---|---|")
    mode_counts: Counter[str] = Counter()
    for f in findings:
        if f["verdict"] != "WRONG":
            continue
        if f["status_raw"]:
            mode_counts["C: status cell denies offer, row still defaulted to "
                        "FINAL_SELECTED/OFFERED"] += 1
        else:
            mode_counts["C: row from a non-offer section (pending/round-progress "
                        "table) has no status cell and defaulted to FINAL_SELECTED"] += 1
    for i, (mode, n) in enumerate(mode_counts.most_common(), start=1):
        add(f"| {i} | {mode} | {n} | see per-email table below |")
    add("")
    add("## Affected source emails")
    add("")
    add("| Email | Subject | Wrong rows | OK rows |")
    add("|---|---|---|---|")
    for email_id, b in sorted(bad.items(), key=lambda kv: -len(kv[1]["wrong"])):
        subject = (b["subject"] or "").replace("\n", " ")[:90]
        add(f"| `{email_id[:12]}` | {subject} | {len(b['wrong'])} | {b['ok']} |")
    add("")
    add("## Failure-mode probes (corpus-wide)")
    add("")
    add(f"- body says \"selected for the next round\" / \"students selected for\", "
        f"by classification: `{probes['body_says_selected_for_next_round']}`")
    add(f"- subject says shortlist, by classification: `{probes['subject_says_shortlist']}`")
    add("- per-row status cells that deny an offer, and what the pipeline wrote:")
    add("")
    add("| Status cell in email | Written as | Rows |")
    add("|---|---|---|")
    for row in probes["status_cell_denies_offer"]:
        add(f"| `{row['status_raw']}` | `{row['normalized_status']}` | {row['count']} |")
    add("")
    add(f"- emails with `dedup_of`/`revision_of`/non-canonical: "
        f"`{probes['dedup_revision_noncanonical']}` "
        f"(non-canonical emails holding offer rows: "
        f"{probes['noncanonical_emails_with_offer_rows']})")
    add(f"- students holding both a `final_selection` and an `offer` event for the "
        f"same company (dedup merge candidates): "
        f"`{probes['students_with_both_event_types']}`")
    add(f"- marked students whose evidence came from a non-canonical / dedup / "
        f"revision copy of a message: "
        f"`{probes['marked_students_from_noncanonical_copy']}`")
    add(f"- marked events that no longer join back to an `offer_students` row: "
        f"`{probes['marked_events_without_offer_row']}`")
    add(f"- `job_placed_students` mappings built from a row whose status cell "
        f"denies an offer (REJECTED / NO_SHOW): "
        f"`{probes['mappings_from_denied_status']}`")
    add("")
    add("### Classification rules that fired, by classification")
    add("")
    add("| Classification | Rule | Emails |")
    add("|---|---|---|")
    for cls, sig, n in probes["rules_by_classification"]:
        add(f"| {cls} | {sig or '-'} | {n} |")
    add("")
    add("## Sample of wrongly-marked students")
    add("")
    add("| Roll | Name | Written as | Status cell in email | Section title | Email |")
    add("|---|---|---|---|---|---|")
    for f in [x for x in findings if x["verdict"] == "WRONG"][:40]:
        add(f"| {f['roll_no'] or '-'} | {(f['name'] or '-')[:24]} | "
            f"{f['written_status']} | {f['status_raw'] or '(none)'} | "
            f"{(f['section_title'] or '-')[:60]} | `{f['email_id'][:12]}` |")
    add("")
    add("_Generated by `scripts/phase0_diagnose.py` (read-only)._")
    add("")

    text = "\n".join(lines)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0,
                    help="print N wrongly-marked rows with their body context")
    args = ap.parse_args()

    conn = connect()
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    findings, totals = analyse_offer_rows(cur)
    only_ev = only_evidence_counts(cur, findings)
    probes = failure_mode_probes(cur)
    write_report(findings, totals, only_ev, probes)

    print(f"offer rows examined : {len(findings)}")
    print(f"  OK (real offer)   : {totals.get('OK', 0)}")
    print(f"  WRONG             : {totals.get('WRONG', 0)}")
    print(f"  student row not located in body (needs manual read): "
          f"{totals.get('UNLOCATED', 0)}")
    print(f"  students whose only FINAL_SELECTED/OFFERED evidence is a wrong row: "
          f"{only_ev.get('students_only_wrong', 0)}")
    print(f"job_placed_students served today: {probes['job_placed_students_total']}")
    print(f"report -> {REPORT_PATH}")

    if args.sample:
        print("\n--- sample wrong rows with body context ---")
        body_cache: dict[str, str] = {}
        for f in [x for x in findings if x["verdict"] == "WRONG"][: args.sample]:
            if f["email_id"] not in body_cache:
                cur.execute("SELECT body_clean FROM emails WHERE id=%s", (f["email_id"],))
                body_cache[f["email_id"]] = cur.fetchone()["body_clean"] or ""
            body = body_cache[f["email_id"]].splitlines()
            lo = max(0, (f["line"] or 0) - 6)
            hi = min(len(body), (f["line"] or 0) + 2)
            print(f"\n### {f['name']} ({f['roll_no']}) - {f['subject'][:70]}")
            print(f"    verdict: {f['reason']}")
            for i in range(lo, hi):
                mark = ">>" if i == f["line"] else "  "
                print(f"  {mark} {i + 1}: {body[i][:120]}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
