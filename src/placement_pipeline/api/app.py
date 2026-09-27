"""REST API over the SQLite extraction store.

Endpoints (all read-only except ``POST /sync``):

- ``GET  /``                          endpoint index
- ``GET  /companies``                 companies with per-category counts
- ``GET  /companies/{name}/funnel``   funnel counts for one company
- ``GET  /offers``                    canonical offer emails
- ``GET  /offers/summary``            offers aggregated by company
- ``GET  /shortlists``                canonical shortlist emails
- ``GET  /opportunities``             canonical opportunity emails
- ``GET  /students/{roll_no}`         every appearance of one roll number
- ``GET  /emails/{email_id}``         raw email + extraction (manual review)
- ``POST /sync``                      re-ingest the corpus, returns the report

Only canonical (latest) members of a dedup cluster are served, so a
cross-group crosspost never double-counts. The database dependency and the
ingest callable are injectable, so the test-suite never touches PostgreSQL.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable, Iterator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from placement_pipeline.db import connect, get_extraction, stats
from placement_pipeline.ingest import run_ingest

app = FastAPI(
    title="JIIT Placement Pipeline API",
    version="1.0.0",
    description="Deterministic extraction of placement facts from the mail corpus.",
)

MAX_LIMIT = 500
DEFAULT_LIMIT = 50


# ----------------------------------------------------------------- dependencies


def get_db() -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request (schema applied on open)."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_ingester() -> Callable[..., Any]:
    """The ingest callable used by ``POST /sync`` (tests swap this out)."""
    return run_ingest


def _page(limit: int, offset: int, total: int, items: list[dict]) -> dict[str, Any]:
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def _student_count_sql(alias: str = "x") -> str:
    return (
        f"(SELECT COUNT(*) FROM students s WHERE s.email_id = {alias}.email_id)"
    )


def _company_clause(company: Optional[str]) -> tuple[str, list[str]]:
    if not company:
        return "", []
    return " AND x.company = ? COLLATE NOCASE", [company]


def _counts_for(conn: sqlite3.Connection, email_ids: list[str]) -> dict[str, list[dict]]:
    if not email_ids:
        return {}
    marks = ",".join("?" for _ in email_ids)
    out: dict[str, list[dict]] = {}
    for row in conn.execute(
        f"SELECT email_id, stage, count, qualifier FROM funnel_counts"
        f" WHERE email_id IN ({marks}) ORDER BY id",
        email_ids,
    ):
        out.setdefault(row["email_id"], []).append(
            {
                "stage": row["stage"],
                "count": row["count"],
                "qualifier": row["qualifier"],
            }
        )
    return out


def _links_for(conn: sqlite3.Connection, email_ids: list[str]) -> dict[str, list[dict]]:
    if not email_ids:
        return {}
    marks = ",".join("?" for _ in email_ids)
    out: dict[str, list[dict]] = {}
    for row in conn.execute(
        f"SELECT email_id, url, label FROM links WHERE email_id IN ({marks})"
        f" ORDER BY position",
        email_ids,
    ):
        out.setdefault(row["email_id"], []).append(
            {"url": row["url"], "label": row["label"]}
        )
    return out


# ----------------------------------------------------------------------- routes


@app.get("/")
def index() -> dict[str, str]:
    return {
        "name": "JIIT Placement Pipeline API",
        "docs": "/docs",
        "sync": "POST /sync",
    }


@app.get("/companies")
def companies(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Companies seen in canonical extractions, with per-category counts."""
    rows = conn.execute(
        """
        SELECT x.company AS company,
               SUM(CASE WHEN x.category = 'OFFER' THEN 1 ELSE 0 END)      AS offers,
               SUM(CASE WHEN x.category = 'SHORTLIST' THEN 1 ELSE 0 END)  AS shortlists,
               SUM(CASE WHEN x.category = 'OPPORTUNITY' THEN 1 ELSE 0 END) AS opportunities,
               SUM(CASE WHEN x.category = 'OTHER' THEN 1 ELSE 0 END)      AS other,
               COUNT(*) AS emails
        FROM extractions x
        WHERE x.is_canonical = 1 AND x.company IS NOT NULL AND x.company <> ''
        GROUP BY x.company
        ORDER BY x.company COLLATE NOCASE
        """
    ).fetchall()
    items = [
        {
            "company": r["company"],
            "offers": r["offers"],
            "shortlists": r["shortlists"],
            "opportunities": r["opportunities"],
            "other": r["other"],
            "emails": r["emails"],
        }
        for r in rows
    ]
    return _page(len(items), 0, len(items), items)


@app.get("/companies/{name}/funnel")
def company_funnel(name: str, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """Every funnel count extracted for one company (canonical emails only)."""
    found = conn.execute(
        "SELECT company FROM extractions"
        " WHERE is_canonical = 1 AND company = ? COLLATE NOCASE LIMIT 1",
        (name,),
    ).fetchone()
    if not found:
        raise HTTPException(status_code=404, detail=f"unknown company: {name}")
    rows = conn.execute(
        """
        SELECT x.email_id, m.subject, m.received_at,
               f.stage, f.count, f.qualifier, f.sentence
        FROM extractions x
        JOIN emails m ON m.id = x.email_id
        JOIN funnel_counts f ON f.email_id = x.email_id
        WHERE x.is_canonical = 1 AND x.company = ? COLLATE NOCASE
        ORDER BY m.received_at, f.id
        """,
        (name,),
    ).fetchall()
    return {
        "company": found["company"],
        "counts": [
            {
                "email_id": r["email_id"],
                "subject": r["subject"],
                "received_at": r["received_at"],
                "stage": r["stage"],
                "count": r["count"],
                "qualifier": r["qualifier"],
                "sentence": r["sentence"],
            }
            for r in rows
        ],
    }


@app.get("/offers")
def offers(
    company: Optional[str] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    extra, params = _company_clause(company)
    where = "x.category = 'OFFER' AND x.is_canonical = 1" + extra
    total = conn.execute(
        f"SELECT COUNT(*) FROM extractions x WHERE {where}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT x.*, m.subject, m.received_at, m.source_group,
               {_student_count_sql()} AS student_count
        FROM extractions x
        JOIN emails m ON m.id = x.email_id
        WHERE {where}
        ORDER BY m.received_at DESC, x.email_id
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    items = [
        {
            "email_id": r["email_id"],
            "company": r["company"],
            "company_raw": r["company_raw"],
            "role": r["role"],
            "status": r["status"],
            "package_inr": r["package_inr"],
            "package_raw": r["package_raw"],
            "package_basis": r["package_basis"],
            "stipend_inr": r["stipend_inr"],
            "deadline": r["deadline"],
            "venue": r["venue"],
            "duration": r["duration"],
            "students": r["student_count"],
            "subject": r["subject"],
            "received_at": r["received_at"],
            "source_group": r["source_group"],
            "warnings": json.loads(r["warnings"]),
        }
        for r in rows
    ]
    return _page(limit, offset, total, items)


@app.get("/offers/summary")
def offers_summary(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """One row per company: offer counts, package range, roles, students."""
    rows = conn.execute(
        f"""
        SELECT x.company, x.role, x.package_inr,
               {_student_count_sql()} AS student_count
        FROM extractions x
        WHERE x.category = 'OFFER' AND x.is_canonical = 1
          AND x.company IS NOT NULL AND x.company <> ''
        """
    ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = grouped.setdefault(
            r["company"],
            {
                "company": r["company"],
                "offers": 0,
                "students": 0,
                "package_min_inr": None,
                "package_max_inr": None,
                "roles": [],
            },
        )
        g["offers"] += 1
        g["students"] += r["student_count"]
        pkg = r["package_inr"]
        if pkg is not None:
            if g["package_min_inr"] is None or pkg < g["package_min_inr"]:
                g["package_min_inr"] = pkg
            if g["package_max_inr"] is None or pkg > g["package_max_inr"]:
                g["package_max_inr"] = pkg
        if r["role"] and r["role"] not in g["roles"]:
            g["roles"].append(r["role"])
    items = sorted(
        grouped.values(), key=lambda g: (-g["offers"], g["company"].lower())
    )
    return _page(len(items), 0, len(items), items)


@app.get("/shortlists")
def shortlists(
    company: Optional[str] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    extra, params = _company_clause(company)
    where = "x.category = 'SHORTLIST' AND x.is_canonical = 1" + extra
    total = conn.execute(
        f"SELECT COUNT(*) FROM extractions x WHERE {where}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT x.*, m.subject, m.received_at, m.source_group,
               {_student_count_sql()} AS student_count
        FROM extractions x
        JOIN emails m ON m.id = x.email_id
        WHERE {where}
        ORDER BY m.received_at DESC, x.email_id
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    counts = _counts_for(conn, [r["email_id"] for r in rows])
    items = [
        {
            "email_id": r["email_id"],
            "company": r["company"],
            "company_raw": r["company_raw"],
            "stage": r["stage"],
            "sub_pattern": r["sub_pattern"],
            "students": r["student_count"],
            "counts": counts.get(r["email_id"], []),
            "deadline": r["deadline"],
            "subject": r["subject"],
            "received_at": r["received_at"],
            "source_group": r["source_group"],
            "warnings": json.loads(r["warnings"]),
        }
        for r in rows
    ]
    return _page(limit, offset, total, items)


@app.get("/opportunities")
def opportunities(
    company: Optional[str] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    extra, params = _company_clause(company)
    where = "x.category = 'OPPORTUNITY' AND x.is_canonical = 1" + extra
    total = conn.execute(
        f"SELECT COUNT(*) FROM extractions x WHERE {where}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT x.*, m.subject, m.received_at, m.source_group,
               {_student_count_sql()} AS student_count
        FROM extractions x
        JOIN emails m ON m.id = x.email_id
        WHERE {where}
        ORDER BY m.received_at DESC, x.email_id
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    links = _links_for(conn, [r["email_id"] for r in rows])
    items = [
        {
            "email_id": r["email_id"],
            "company": r["company"],
            "company_raw": r["company_raw"],
            "opportunity_type": r["opportunity_type"],
            "deadline": r["deadline"],
            "eligibility": r["eligibility"],
            "links": links.get(r["email_id"], []),
            "students": r["student_count"],
            "subject": r["subject"],
            "received_at": r["received_at"],
            "source_group": r["source_group"],
            "warnings": json.loads(r["warnings"]),
        }
        for r in rows
    ]
    return _page(limit, offset, total, items)


@app.get("/students/{roll_no}")
def student(roll_no: str, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """Every canonical email listing this roll number (no identity mapping)."""
    rows = conn.execute(
        """
        SELECT s.roll_no, s.raw_name, s.name, s.branch, s.program, s.email,
               s.role AS row_role, s.status AS row_status,
               x.category, x.company, x.role AS offer_role, x.status AS offer_status,
               m.id AS email_id, m.subject, m.received_at, m.source_group
        FROM students s
        JOIN extractions x ON x.email_id = s.email_id
        JOIN emails m ON m.id = s.email_id
        WHERE s.roll_no = ? COLLATE NOCASE AND x.is_canonical = 1
        ORDER BY m.received_at, s.position
        """,
        (roll_no,),
    ).fetchall()
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"no rows for roll number: {roll_no}"
        )
    return {
        "roll_no": rows[0]["roll_no"],
        "appearances": [
            {
                "email_id": r["email_id"],
                "category": r["category"],
                "company": r["company"],
                "name": r["name"],
                "raw_name": r["raw_name"],
                "branch": r["branch"],
                "program": r["program"],
                "email": r["email"],
                "row_role": r["row_role"],
                "row_status": r["row_status"],
                "offer_role": r["offer_role"],
                "offer_status": r["offer_status"],
                "subject": r["subject"],
                "received_at": r["received_at"],
                "source_group": r["source_group"],
            }
            for r in rows
        ],
    }


@app.get("/emails/{email_id}")
def email(email_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """Raw email plus its extraction — how OTHER fallbacks get reviewed."""
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"unknown email id: {email_id}")
    ext = get_extraction(conn, email_id)
    return {
        "id": row["id"],
        "gmail_message_id": row["gmail_message_id"],
        "source_group": row["source_group"],
        "sender": row["sender"],
        "subject": row["subject"],
        "received_at": row["received_at"],
        "has_attachments": bool(row["has_attachments"]),
        "body_text": row["body_text"],
        "extraction": ext.model_dump(mode="json") if ext else None,
    }


@app.post("/sync")
def sync(
    limit: Optional[int] = Query(None, ge=1),
    ingester: Callable[..., Any] = Depends(get_ingester),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Re-ingest the corpus (deterministic, idempotent) and report counters."""
    report = ingester(limit=limit)
    return {"report": report.as_dict(), "storage": stats(conn)}
