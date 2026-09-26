"""SQLite storage for the ingest: schema, save/load, honest stats.

One row per message in ``emails``; everything parsed lands in ``extractions``
(one per email) with children (``students``, ``funnel_counts``, ``links``,
``date_facts``) keyed by ``email_id``. Re-ingesting an email replaces its
extraction atomically (idempotent).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from placement_pipeline.config import SQLITE_PATH
from placement_pipeline.models import (
    Category,
    DateFact,
    Email,
    Extraction,
    FunnelCount,
    Link,
    StudentRow,
    SubPattern,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id                TEXT PRIMARY KEY,
    gmail_message_id  TEXT NOT NULL,
    source_group      TEXT,
    sender            TEXT,
    sender_email      TEXT,
    subject           TEXT NOT NULL,
    received_raw      TEXT,
    received_at       TEXT,
    body_text         TEXT NOT NULL,
    has_attachments   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS extractions (
    email_id         TEXT PRIMARY KEY REFERENCES emails(id) ON DELETE CASCADE,
    category         TEXT NOT NULL,
    sub_pattern      TEXT,
    confidence       REAL NOT NULL DEFAULT 0,
    signals          TEXT NOT NULL DEFAULT '[]',
    company_raw      TEXT,
    company          TEXT,
    role             TEXT,
    package_inr      INTEGER,
    package_raw      TEXT,
    package_basis    TEXT,
    stipend_inr      INTEGER,
    duration         TEXT,
    status           TEXT,
    deadline         TEXT,
    reporting_at     TEXT,
    venue            TEXT,
    stage            TEXT,
    opportunity_type TEXT,
    eligibility      TEXT,
    is_canonical     INTEGER NOT NULL DEFAULT 1,
    dedup_of         TEXT,
    revision_of      TEXT,
    warnings         TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS students (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    serial   INTEGER,
    roll_no  TEXT,
    raw_name TEXT,
    name     TEXT,
    branch   TEXT,
    program  TEXT,
    college  TEXT,
    email    TEXT,
    role     TEXT,
    status   TEXT,
    section  TEXT
);

CREATE TABLE IF NOT EXISTS funnel_counts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id  TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    stage     TEXT NOT NULL,
    count     INTEGER NOT NULL,
    qualifier TEXT NOT NULL DEFAULT '',
    sentence  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS links (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    url      TEXT NOT NULL,
    label    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS date_facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id    TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    occurred_at TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'mention',
    raw         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ingest_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extractions_category   ON extractions(category);
CREATE INDEX IF NOT EXISTS idx_extractions_company    ON extractions(company);
CREATE INDEX IF NOT EXISTS idx_extractions_canonical  ON extractions(is_canonical);
CREATE INDEX IF NOT EXISTS idx_students_roll          ON students(roll_no);
CREATE INDEX IF NOT EXISTS idx_students_email         ON students(email);
CREATE INDEX IF NOT EXISTS idx_funnel_email           ON funnel_counts(email_id);
"""


def connect(path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open (and create) the SQLite database with schema applied."""
    target = Path(path) if path else SQLITE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


# --------------------------------------------------------------- serialization


def _iso(value: Optional[datetime | date]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return value.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def save_email(conn: sqlite3.Connection, email: Email) -> None:
    conn.execute(
        """INSERT INTO emails
               (id, gmail_message_id, source_group, sender, sender_email, subject,
                received_raw, received_at, body_text, has_attachments)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               gmail_message_id = excluded.gmail_message_id,
               source_group     = excluded.source_group,
               sender           = excluded.sender,
               sender_email     = excluded.sender_email,
               subject          = excluded.subject,
               received_raw     = excluded.received_raw,
               received_at      = excluded.received_at,
               body_text        = excluded.body_text,
               has_attachments  = excluded.has_attachments""",
        (
            email.id,
            email.gmail_message_id,
            email.source_group,
            email.sender,
            email.sender_email,
            email.subject,
            email.received_raw,
            _iso(email.received_at),
            email.body_text,
            int(email.has_attachments),
        ),
    )


def save_extraction(conn: sqlite3.Connection, ext: Extraction) -> None:
    """Upsert an extraction with all children (replaces any previous rows)."""
    conn.execute("DELETE FROM extractions WHERE email_id = ?", (ext.email_id,))
    # children hang off emails(id), so they must be cleared explicitly
    for table in ("students", "funnel_counts", "links", "date_facts"):
        conn.execute(f"DELETE FROM {table} WHERE email_id = ?", (ext.email_id,))
    conn.execute(
        """INSERT INTO extractions
               (email_id, category, sub_pattern, confidence, signals,
                company_raw, company, role, package_inr, package_raw,
                package_basis, stipend_inr, duration, status, deadline,
                reporting_at, venue, stage, opportunity_type, eligibility,
                is_canonical, dedup_of, revision_of, warnings)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?)""",
        (
            ext.email_id,
            ext.category.value,
            ext.sub_pattern.value if ext.sub_pattern else None,
            ext.confidence,
            _json(ext.signals),
            ext.company_raw,
            ext.company,
            ext.role,
            ext.package_inr,
            ext.package_raw,
            ext.package_basis,
            ext.stipend_inr,
            ext.duration,
            ext.status,
            _iso(ext.deadline),
            _iso(ext.reporting_at),
            ext.venue,
            ext.stage,
            ext.opportunity_type,
            ext.eligibility,
            int(ext.is_canonical),
            ext.dedup_of,
            ext.revision_of,
            _json(ext.warnings),
        ),
    )
    conn.executemany(
        """INSERT INTO students
               (email_id, position, serial, roll_no, raw_name, name, branch,
                program, college, email, role, status, section)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                ext.email_id,
                pos,
                s.serial,
                s.roll_no,
                s.raw_name,
                s.name,
                s.branch,
                s.program,
                s.college,
                s.email,
                s.role,
                s.status,
                s.section,
            )
            for pos, s in enumerate(ext.students)
        ],
    )
    conn.executemany(
        """INSERT INTO funnel_counts (email_id, stage, count, qualifier, sentence)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (ext.email_id, f.stage, f.count, f.qualifier, f.sentence)
            for f in ext.funnel_counts
        ],
    )
    conn.executemany(
        """INSERT INTO links (email_id, position, url, label)
           VALUES (?, ?, ?, ?)""",
        [
            (ext.email_id, pos, l.url, l.label)
            for pos, l in enumerate(ext.links)
        ],
    )
    conn.executemany(
        """INSERT INTO date_facts (email_id, occurred_at, role, raw)
           VALUES (?, ?, ?, ?)""",
        [
            (ext.email_id, _iso(f.when), f.role, f.raw)
            for f in ext.interview_dates
        ],
    )


def save_meta(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    conn.executemany(
        """INSERT INTO ingest_meta (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        [(k, str(v)) for k, v in values.items()],
    )


# ------------------------------------------------------------------- loading


def _load_children(conn: sqlite3.Connection, email_id: str) -> dict[str, list[Any]]:
    students = [
        StudentRow(
            serial=r["serial"],
            roll_no=r["roll_no"],
            raw_name=r["raw_name"],
            name=r["name"],
            branch=r["branch"],
            program=r["program"],
            college=r["college"],
            email=r["email"],
            role=r["role"],
            status=r["status"],
            section=r["section"],
        )
        for r in conn.execute(
            "SELECT * FROM students WHERE email_id = ? ORDER BY position", (email_id,)
        )
    ]
    funnel = [
        FunnelCount(
            stage=r["stage"], count=r["count"],
            qualifier=r["qualifier"], sentence=r["sentence"],
        )
        for r in conn.execute(
            "SELECT * FROM funnel_counts WHERE email_id = ? ORDER BY id", (email_id,)
        )
    ]
    links = [
        Link(url=r["url"], label=r["label"])
        for r in conn.execute(
            "SELECT * FROM links WHERE email_id = ? ORDER BY position", (email_id,)
        )
    ]
    dates = [
        DateFact(when=datetime.fromisoformat(r["occurred_at"]), role=r["role"], raw=r["raw"])
        for r in conn.execute(
            "SELECT * FROM date_facts WHERE email_id = ? ORDER BY id", (email_id,)
        )
    ]
    return {"students": students, "funnel_counts": funnel, "links": links, "dates": dates}


def row_to_extraction(conn: sqlite3.Connection, row: sqlite3.Row) -> Extraction:
    children = _load_children(conn, row["email_id"])
    deadline = datetime.fromisoformat(row["deadline"]).date() if row["deadline"] else None
    reporting = datetime.fromisoformat(row["reporting_at"]) if row["reporting_at"] else None
    return Extraction(
        email_id=row["email_id"],
        category=Category(row["category"]),
        sub_pattern=SubPattern(row["sub_pattern"]) if row["sub_pattern"] else None,
        confidence=row["confidence"],
        signals=json.loads(row["signals"]),
        company_raw=row["company_raw"],
        company=row["company"],
        role=row["role"],
        package_inr=row["package_inr"],
        package_raw=row["package_raw"],
        package_basis=row["package_basis"],
        stipend_inr=row["stipend_inr"],
        duration=row["duration"],
        status=row["status"],
        deadline=deadline,
        interview_dates=children["dates"],
        reporting_at=reporting,
        venue=row["venue"],
        stage=row["stage"],
        opportunity_type=row["opportunity_type"],
        links=children["links"],
        eligibility=row["eligibility"],
        students=children["students"],
        funnel_counts=children["funnel_counts"],
        is_canonical=bool(row["is_canonical"]),
        dedup_of=row["dedup_of"],
        revision_of=row["revision_of"],
        warnings=json.loads(row["warnings"]),
    )


def get_extraction(conn: sqlite3.Connection, email_id: str) -> Optional[Extraction]:
    row = conn.execute(
        "SELECT * FROM extractions WHERE email_id = ?", (email_id,)
    ).fetchone()
    return row_to_extraction(conn, row) if row else None


def iter_extractions(
    conn: sqlite3.Connection,
    *,
    category: Optional[str] = None,
    canonical_only: bool = True,
    company: Optional[str] = None,
) -> Iterable[Extraction]:
    sql = "SELECT * FROM extractions WHERE 1=1"
    params: list[Any] = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if canonical_only:
        sql += " AND is_canonical = 1"
    if company:
        sql += " AND company = ?"
        params.append(company)
    sql += " ORDER BY email_id"
    for row in conn.execute(sql, params):
        yield row_to_extraction(conn, row)


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Storage counters (honest, computed from what is actually stored)."""
    def one(sql: str, *params: Any) -> int:
        return int(conn.execute(sql, params).fetchone()[0])

    return {
        "emails": one("SELECT count(*) FROM emails"),
        "extractions": one("SELECT count(*) FROM extractions"),
        "canonical": one("SELECT count(*) FROM extractions WHERE is_canonical = 1"),
        "students": one("SELECT count(*) FROM students"),
        "students_with_roll": one(
            "SELECT count(*) FROM students WHERE roll_no IS NOT NULL AND roll_no <> ''"
        ),
        "funnel_counts": one("SELECT count(*) FROM funnel_counts"),
        "links": one("SELECT count(*) FROM links"),
        "date_facts": one("SELECT count(*) FROM date_facts"),
        "offers": one(
            "SELECT count(*) FROM extractions WHERE category = 'OFFER' AND is_canonical = 1"
        ),
        "shortlists": one(
            "SELECT count(*) FROM extractions WHERE category = 'SHORTLIST' AND is_canonical = 1"
        ),
        "opportunities": one(
            "SELECT count(*) FROM extractions WHERE category = 'OPPORTUNITY' AND is_canonical = 1"
        ),
        "other": one(
            "SELECT count(*) FROM extractions WHERE category = 'OTHER' AND is_canonical = 1"
        ),
    }
