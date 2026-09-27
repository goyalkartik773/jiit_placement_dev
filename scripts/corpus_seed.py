"""Seed specific corpus emails into the *current* schema (search_path).

    python scripts/corpus_seed.py <gmail_message_id> [<gmail_message_id> ...]

Reads each message from ``public.emails`` first (full headers + the
attachment text the sync pipeline already extracted) and falls back to the
legacy ``public.gmailmessages`` corpus when the id only exists there.  Rows
already present in the current schema are skipped, so seeding is idempotent.

Live-only columns are never copied: primary key, ``dedup_of`` / ``revision_of``
FKs pointing at live row ids, classification fields and processing state -
Step 2 re-derives all of them for the current schema.

Used by ``scripts/run_backend_validation.py`` and ``app/tests`` so the golden
validation and the test suite exercise exactly the same code path.
"""

from __future__ import annotations

import sys
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Email, EmailAttachment, EmailStatus

#: Columns re-derived by Step 2 / cluster linking instead of copied.
_DERIVED = {
    "id",
    "dedup_of",
    "revision_of",
    "classification",
    "classification_confidence",
    "classification_signals",
    "classification_method",
    "processing_status",
    "error_message",
    "retry_count",
    "created_at",
    "updated_at",
}


def _present(session: Session, gm: str) -> bool:
    return (
        session.execute(
            text("SELECT 1 FROM emails WHERE gmail_message_id = :gm"), {"gm": gm}
        ).first()
        is not None
    )


def _seed_from_emails(session: Session, gm: str) -> Optional[str]:
    """Rich path: current-schema rows already produced by Step 1 sync."""
    cols = [c.name for c in Email.__table__.columns if c.name not in _DERIVED]
    row = session.execute(
        text(
            "SELECT e.id AS live_id, "
            + ", ".join(f"e.{c}" for c in cols)
            + " FROM public.emails e WHERE e.gmail_message_id = :gm"
        ),
        {"gm": gm},
    ).mappings().first()
    if row is None:
        return None

    data = dict(row)
    live_id = data.pop("live_id")
    data["processing_status"] = EmailStatus.PENDING
    data["classification"] = None
    email = Email(**data)
    session.add(email)
    session.flush()

    attachments = session.execute(
        text(
            "SELECT gmail_attachment_id, filename, mime_type, file_size, "
            "extracted_text, method FROM public.email_attachments "
            "WHERE email_id = :live_id"
        ),
        {"live_id": live_id},
    ).all()
    for gid, filename, mime, size, extracted, method in attachments:
        session.add(
            EmailAttachment(
                email_id=email.id,
                gmail_attachment_id=gid,
                filename=filename,
                mime_type=mime,
                file_size=size,
                extracted_text=extracted,
                method=method or "legacy_copy",
            )
        )
    return "emails"


def _seed_from_legacy(session: Session, gm: str) -> Optional[str]:
    """Fallback: the pre-Android legacy corpus (gmailmessages + attachments)."""
    row = session.execute(
        text("SELECT * FROM public.gmailmessages WHERE gmailmessageid = :gm"),
        {"gm": gm},
    ).mappings().first()
    if row is None:
        return None

    sender_full = row.get("sender") or None
    name, addr = parseaddr(sender_full or "")
    received_raw = row.get("receivedat")
    received_at = None
    if received_raw:
        try:
            received_at = parsedate_to_datetime(received_raw)
        except (TypeError, ValueError):
            received_at = None

    email = Email(
        gmail_message_id=gm,
        thread_id=row.get("gmailthreadid"),
        source_group=row.get("sourcegroup"),
        sender=name or sender_full,
        sender_email=addr or None,
        subject=row.get("subject") or "",
        received_raw=received_raw,
        received_at=received_at,
        body_text=row.get("bodytext") or "",
        body_html=row.get("bodyhtml") or None,
        snippet=row.get("snippet"),
        label_ids=[],
        has_attachments=bool(row.get("hasattachments")),
        processing_status=EmailStatus.PENDING,
    )
    session.add(email)
    session.flush()

    attachments = session.execute(
        text(
            "SELECT a.gmailattachmentid, a.filename, a.mimetype, a.filesize, "
            "a.extractedtext FROM public.gmailattachments a "
            "JOIN public.gmailmessages m ON m.id = a.sysgmailmessageuuid "
            "WHERE m.gmailmessageid = :gm"
        ),
        {"gm": gm},
    ).all()
    for gid, filename, mime, size, extracted in attachments:
        session.add(
            EmailAttachment(
                email_id=email.id,
                gmail_attachment_id=gid,
                filename=filename,
                mime_type=mime,
                file_size=size,
                extracted_text=extracted,
                method="legacy_copy",
            )
        )
    return "gmailmessages"


def seed_emails(gm_ids: list[str], session: Session) -> dict[str, str]:
    """Ensure every id exists in the current schema; one transaction.

    Returns ``{gm_id: present | emails | gmailmessages | missing}``.
    """
    result: dict[str, str] = {}
    for gm in gm_ids:
        if _present(session, gm):
            result[gm] = "present"
            continue
        status = _seed_from_emails(session, gm) or _seed_from_legacy(session, gm)
        result[gm] = status or "missing"
    session.commit()
    return result


def main(argv: list[str]) -> int:
    from app.db import get_session_factory

    if not argv:
        print(__doc__)
        return 2
    session = get_session_factory()()
    try:
        results = seed_emails(argv, session)
        for gm, status in results.items():
            print(f"{gm}  {status}")
        if "missing" in results.values():
            return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
