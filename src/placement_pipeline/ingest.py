"""Corpus ingest: PostgreSQL ``gmailmessages`` -> classify -> parse -> SQLite.

Pipeline per message:

1. ``prepare_parts`` splits the body into the sender's current section and
   any ``---------- Forwarded message ----------`` history the sender
   included (headers stripped, reply quotes never parsed).
2. ``classify`` decides OFFER / SHORTLIST / OPPORTUNITY / OTHER.
3. Student tables are parsed from *every* section and from non-image
   attachment ``extractedtext`` (xlsx-only lists), deduplicated by
   roll/email/name.
4. The category parser runs on the current section; the history section is
   parsed too and only fills gaps (current wins, lists are unioned, the
   latest deadline wins). Warnings resolved by history are dropped.
5. SHORTLIST sub-pattern is refined from parsed evidence: rows -> A,
   counts -> B, otherwise the classifier's call stands.
6. ``deduplicate`` links crossposts/revisions; the latest member is
   canonical.

No student-roster identity mapping happens here (step 1 scope).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from placement_pipeline.classifier import classify
from placement_pipeline.company import extract_company
from placement_pipeline.db import connect, save_email, save_extraction, save_meta, stats
from placement_pipeline.dedup import cluster_stats, deduplicate
from placement_pipeline.models import Category, Email, Extraction, SubPattern
from placement_pipeline.normalize import prepare_parts
from placement_pipeline.parse_offer import parse_offer
from placement_pipeline.parse_opportunity import parse_opportunity
from placement_pipeline.parse_shortlist import parse_shortlist
from placement_pipeline.tables import extract_students

#: the xlsx extractor caps ``extractedtext`` at this many characters
ATTACHMENT_TEXT_CAP = 50_000

_PARSER_BY_CATEGORY = {
    Category.OFFER: parse_offer,
    Category.SHORTLIST: parse_shortlist,
    Category.OPPORTUNITY: parse_opportunity,
}

# scalar facts: current section wins, history only fills the gap
_FILL_KEYS = (
    "company_raw", "company", "role", "package_inr", "package_raw",
    "package_basis", "stipend_inr", "status", "venue", "duration",
    "stage", "opportunity_type", "eligibility", "reporting_at",
)
# list facts: unioned, current first
_UNION_KEYS = ("links", "funnel_counts", "event_stages", "team_rules")
# warnings a filled gap makes obsolete
_RESOLVES = {
    "role": "role not stated in body or table",
    "company": "company not identified",
    "opportunity_type": "opportunity type not recognised",
}


@dataclass
class EmailResult:
    extraction: Extraction
    sections: int = 1
    attachment_rows: int = 0


@dataclass
class IngestReport:
    emails: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    students: int = 0
    emails_with_students: int = 0
    funnel_counts: int = 0
    attachment_rows: int = 0
    multi_section_emails: int = 0
    dedup: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "emails": self.emails,
            "by_category": dict(self.by_category),
            "students": self.students,
            "emails_with_students": self.emails_with_students,
            "funnel_counts": self.funnel_counts,
            "attachment_rows": self.attachment_rows,
            "multi_section_emails": self.multi_section_emails,
            "dedup": dict(self.dedup),
            "warnings": dict(self.warnings),
            "seconds": round(self.seconds, 2),
        }


# ------------------------------------------------------------------- postgres


def fetch_emails(limit: Optional[int] = None) -> list[Email]:
    """Read the mail corpus straight from PostgreSQL (no file exports)."""
    import psycopg2

    from placement_pipeline.config import PG_DSN

    conn = psycopg2.connect(PG_DSN)
    try:
        cur = conn.cursor()
        sql = (
            "SELECT id, gmailmessageid, sourcegroup, sender, subject, receivedat,"
            "       bodytext, hasattachments"
            " FROM gmailmessages ORDER BY receivedat"
        )
        if limit:
            sql += " LIMIT %s"
            cur.execute(sql, (limit,))
        else:
            cur.execute(sql)
        emails: list[Email] = []
        for mid, gmid, group, sender, subject, received, body, has_att in cur.fetchall():
            emails.append(
                Email(
                    id=mid,
                    gmail_message_id=gmid or "",
                    source_group=group or "",
                    sender=sender or "",
                    sender_email=_sender_email(sender or ""),
                    subject=subject or "",
                    received_raw=str(received or ""),
                    received_at=_to_naive(received),
                    body_text=body or "",
                    has_attachments=bool(has_att),
                )
            )
        return emails
    finally:
        conn.close()


def fetch_attachment_texts() -> dict[str, list[str]]:
    """Non-image attachment ``extractedtext`` keyed by gmail message id."""
    import psycopg2

    from placement_pipeline.config import PG_DSN

    conn = psycopg2.connect(PG_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT m.gmailmessageid, a.extractedtext
               FROM gmailattachments a
               JOIN gmailmessages m ON m.id = a.sysgmailmessageuuid
               WHERE a.mimetype NOT LIKE 'image/%'
                 AND a.extractedtext IS NOT NULL
                 AND a.extractedtext <> ''
               ORDER BY a.filename"""
        )
        out: dict[str, list[str]] = {}
        for gmid, text in cur.fetchall():
            if text.startswith("[Image attachment:"):
                continue
            out.setdefault(gmid or "", []).append(text)
        return out
    finally:
        conn.close()


def _sender_email(sender: str) -> str:
    m = re.search(r"<([^>]+)>", sender)
    return (m.group(1) if m else sender).strip().casefold()


def _to_naive(value: Any) -> Optional[datetime]:
    """PG returns tz-aware timestamps; stored dates are naive IST."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


# ------------------------------------------------------------------- parsing


def _union_rows(
    section_rows: list[list[Any]], extra_rows: Iterable[Any] = ()
) -> list[Any]:
    """Dedup the way tables does: roll, else email, else lower-cased name."""
    seen: set[str] = set()
    out: list[Any] = []
    for rows in [*section_rows, list(extra_rows)]:
        for row in rows:
            key = row.roll_no or row.email or (row.raw_name or "").lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


def _parse_other(subject: str, text: str) -> dict[str, Any]:
    """Admin/list mail: company only — absence of a company is expected."""
    raw, company = extract_company(subject, text)
    return {"warnings": [], "company_raw": raw, "company": company}


def _parse_section(category: Category, subject: str, body: str, *, reference, students):
    parser = _PARSER_BY_CATEGORY.get(category)
    if parser is None:
        return _parse_other(subject, body)
    return parser(subject, body, reference=reference, students=students)


def _merge(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Current section wins; history fills gaps. Lists union, deadline latest."""
    merged = dict(primary)
    warnings = list(primary.get("warnings") or [])

    for key in _FILL_KEYS:
        if not merged.get(key) and secondary.get(key):
            merged[key] = secondary[key]

    # the latest stated deadline supersedes the history's older one
    d1, d2 = merged.get("deadline"), secondary.get("deadline")
    if d1 and d2:
        merged["deadline"] = max(d1, d2)
    elif d2:
        merged["deadline"] = d2

    # stale history dates never displace the current section's schedule
    if not merged.get("interview_dates") and secondary.get("interview_dates"):
        merged["interview_dates"] = secondary["interview_dates"]

    for key in _UNION_KEYS:
        primary_list = list(merged.get(key) or [])
        for item in secondary.get(key) or []:
            if item not in primary_list:
                primary_list.append(item)
        merged[key] = primary_list

    for filled_key, warning in _RESOLVES.items():
        if merged.get(filled_key) and warning in warnings:
            warnings.remove(warning)
    if (merged.get("links") or merged.get("deadline")) and (
        "no link and no deadline found" in warnings
    ):
        warnings.remove("no link and no deadline found")

    merged["warnings"] = warnings
    return merged


def extract_email(
    email: Email, attachment_texts: Iterable[str] = ()
) -> EmailResult:
    """Classify + parse one email into an :class:`Extraction`."""
    sections = prepare_parts(email.body_text)
    classification = classify(email.subject, email.body_text)
    category = classification.category

    section_rows: list[list[Any]] = []
    table_warnings: list[str] = []
    for part in sections:
        result = extract_students(part)
        section_rows.append(result.rows)
        table_warnings.extend(result.warnings)

    att_texts = [t for t in attachment_texts if t]
    att_rows: list[Any] = []
    for text in att_texts:
        att_rows.extend(extract_students(text).rows)
    students = _union_rows(section_rows, att_rows)
    attachment_added = len(students) - len(_union_rows(section_rows))

    reference = email.received_at
    fields = _parse_section(
        category, email.subject, sections[0], reference=reference, students=students
    )
    if len(sections) > 1:
        history = _parse_section(
            category, email.subject, sections[1], reference=reference, students=[]
        )
        fields = _merge(fields, history)

    ext = Extraction(
        email_id=email.id,
        category=category,
        sub_pattern=classification.sub_pattern,
        confidence=classification.confidence,
        signals=list(classification.signals),
        students=students,
    )
    for key, value in fields.items():
        if key == "warnings":
            continue
        if value is not None and hasattr(ext, key):
            setattr(ext, key, value)

    ext.funnel_counts = fields.get("funnel_counts") or []
    ext.links = fields.get("links") or []
    ext.interview_dates = fields.get("interview_dates") or []
    ext.team_rules = fields.get("team_rules") or []
    ext.event_stages = fields.get("event_stages") or []
    ext.warnings = list(fields.get("warnings") or [])
    ext.warnings.extend(w for w in table_warnings if w not in ext.warnings)

    if attachment_added and any(len(t) >= ATTACHMENT_TEXT_CAP for t in att_texts):
        ext.warnings.append("attachment text truncated at 50000 chars")

    _refine_sub_pattern(ext)
    return EmailResult(
        extraction=ext,
        sections=len(sections),
        attachment_rows=attachment_added,
    )


def _refine_sub_pattern(ext: Extraction) -> None:
    """SHORTLIST A/B decided by parsed evidence, not only by wording."""
    if ext.category is not Category.SHORTLIST:
        return
    if ext.students:
        ext.sub_pattern = SubPattern.NAMED_LIST
    elif ext.funnel_counts:
        ext.sub_pattern = SubPattern.FUNNEL_COUNTS
    # else: neither found — keep the classifier's call for manual review


# ---------------------------------------------------------------------- run


def run_ingest(
    db_path: Optional[Any] = None,
    *,
    limit: Optional[int] = None,
    emails: Optional[list[Email]] = None,
    attachments: Optional[dict[str, list[str]]] = None,
) -> IngestReport:
    """Full ingest into SQLite; deterministic and idempotent.

    ``emails``/``attachments`` may be injected for tests (no PostgreSQL).
    """
    started = time.perf_counter()
    if emails is None:
        emails = fetch_emails(limit=limit)
    if attachments is None:
        attachments = fetch_attachment_texts()

    decisions = deduplicate(emails)
    dedup_counts = cluster_stats(emails)

    by_category: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    students_total = 0
    emails_with_students = 0
    funnel_total = 0
    attachment_rows = 0
    multi_section = 0

    conn = connect(db_path)
    try:
        with conn:  # one transaction — all or nothing
            for email in emails:
                result = extract_email(email, attachments.get(email.gmail_message_id, ()))
                ext = result.extraction
                decision = decisions[email.id]
                ext.is_canonical = decision.is_canonical
                ext.dedup_of = decision.dedup_of
                ext.revision_of = decision.revision_of

                save_email(conn, email)
                save_extraction(conn, ext)

                by_category[ext.category.value] += 1
                students_total += len(ext.students)
                emails_with_students += bool(ext.students)
                funnel_total += len(ext.funnel_counts)
                attachment_rows += result.attachment_rows
                multi_section += result.sections > 1
                warnings.update(ext.warnings)
            save_meta(
                conn,
                {
                    "last_ingest_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                    "emails": len(emails),
                },
            )
    finally:
        conn.close()

    return IngestReport(
        emails=len(emails),
        by_category=dict(by_category),
        students=students_total,
        emails_with_students=emails_with_students,
        funnel_counts=funnel_total,
        attachment_rows=attachment_rows,
        multi_section_emails=multi_section,
        dedup=dict(dedup_counts),
        warnings={k: v for k, v in warnings.most_common()},
        seconds=time.perf_counter() - started,
    )


def storage_stats(db_path: Optional[Any] = None) -> dict[str, int]:
    conn = connect(db_path)
    try:
        return stats(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Ingest the placement mail corpus")
    parser.add_argument("--limit", type=int, default=None, help="only the first N messages")
    parser.add_argument("--db", default=None, help="SQLite path (default from config)")
    args = parser.parse_args()

    report = run_ingest(args.db, limit=args.limit)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    print(json.dumps(storage_stats(args.db), indent=2, ensure_ascii=False))
