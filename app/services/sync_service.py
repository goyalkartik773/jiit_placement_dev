"""Step 1 - ``POST /api/gmail/sync``.

Fetches messages from Gmail (paginated, one ``list:`` query per source
group), decodes them, and inserts them as raw ``PENDING`` rows.

Idempotency: a message is skipped when its ``gmail_message_id`` already
exists (pre-check + unique index backstop), so re-running sync any number
of times inserts nothing new. Crossposts of the same message under several
groups are counted once (``duplicates_skipped``).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.gmail import attachments as attachment_text
from app.gmail.client import GmailClient
from app.gmail.mime import MailMessage, parse_message
from app.models import Email, EmailAttachment, EmailStatus
from app.repositories import email_repo
from app.utils.logging import log_event

log = logging.getLogger("app.sync")


def group_query(group_email: str) -> str:
    """``jiitengg2027@googlegroups.com`` -> ``list:jiitengg2027.googlegroups.com``."""
    return f"list:{group_email.replace('@', '.')}"


_LEGACY_SQL = """
    SELECT a.gmailattachmentid, a.filename, a.mimetype, a.filesize, a.extractedtext
    FROM gmailattachments a
    JOIN gmailmessages m ON m.id = a.sysgmailmessageuuid
    WHERE m.gmailmessageid = :mid
"""


def store_attachments(
    session: Session,
    row: Email,
    mail: MailMessage,
    client: GmailClient,
    settings: Settings,
) -> dict:
    """Attach extracted text: reuse legacy extraction, else download+parse.

    Rows are only *staged*; callers commit the email + its attachments in
    one transaction and merge the returned counters **after** a successful
    commit (failed messages never inflate the stats).
    """
    from sqlalchemy import text

    legacy = session.execute(text(_LEGACY_SQL), {"mid": row.gmail_message_id}).all()
    if legacy:
        for gid, filename, mime, size, extracted in legacy:
            session.add(
                EmailAttachment(
                    email_id=row.id,
                    gmail_attachment_id=gid,
                    filename=filename,
                    mime_type=mime,
                    file_size=size,
                    extracted_text=extracted,
                    method="legacy_copy",
                )
            )
        return {"attachments_legacy_copied": len(legacy)}

    counts = {"attachments_downloaded": 0, "attachments_skipped": 0}
    for att in mail.attachments:
        data = att.data
        method = "inline" if data is not None else "skipped"
        if data is None:
            eligible = (
                att.gmail_attachment_id is not None
                and attachment_text.is_supported(att.filename, att.mime_type)
                and not (att.file_size or 0) > settings.gmail.max_attachment_bytes
            )
            if eligible:
                try:
                    data = client.get_attachment(
                        row.gmail_message_id, att.gmail_attachment_id or ""
                    )
                    method = "downloaded"
                except Exception as exc:
                    log_event(
                        log,
                        "sync.attachment_failed",
                        level=logging.WARNING,
                        message_id=row.gmail_message_id,
                        filename=att.filename,
                        error=type(exc).__name__,
                    )
                    method = "skipped"

        extracted = None
        if data is not None and attachment_text.is_supported(
            att.filename, att.mime_type
        ):
            text_value, kind = attachment_text.extract_text(
                att.filename, att.mime_type, data
            )
            if not kind.startswith("error"):
                extracted = text_value or None
        session.add(
            EmailAttachment(
                email_id=row.id,
                gmail_attachment_id=att.gmail_attachment_id,
                filename=att.filename,
                mime_type=att.mime_type,
                file_size=att.file_size,
                extracted_text=extracted,
                method=method,
            )
        )
        if method in ("inline", "downloaded"):
            counts["attachments_downloaded"] += 1
        else:
            counts["attachments_skipped"] += 1
    return counts


def run_sync(
    *,
    client: GmailClient,
    session: Session,
    handle,
    payload,
    settings: Settings,
) -> dict:
    """Execute one sync run; returns stats for the API response."""
    started = time.perf_counter()
    groups = list(payload.groups or settings.gmail.source_groups)

    if payload.query:
        labelled_queries = [("custom query", payload.query)]
    else:
        labelled_queries = [(g, group_query(g)) for g in groups]

    stats = {
        "total_fetched": 0,
        "new_messages": 0,
        "duplicates_skipped": 0,
        "failed_messages": 0,
        "attachments_legacy_copied": 0,
        "attachments_downloaded": 0,
        "attachments_skipped": 0,
        "groups": [],
    }
    seen: set[str] = set()

    try:
        for label, query in labelled_queries:
            entry = {
                "group": label,
                "listed": 0,
                "new_messages": 0,
                "duplicates_skipped": 0,
                "failed_messages": 0,
            }
            for message_id in client.iter_message_ids(
                query, max_results=payload.max_results
            ):
                if (
                    payload.max_results
                    and stats["total_fetched"] >= payload.max_results
                ):
                    break
                stats["total_fetched"] += 1
                entry["listed"] += 1

                duplicate = message_id in seen
                if not duplicate:
                    seen.add(message_id)
                    try:
                        duplicate = (
                            email_repo.get_by_gmail_message_id(session, message_id)
                            is not None
                        )
                    except Exception:
                        session.rollback()
                        duplicate = True  # cannot verify - never double-insert

                if duplicate:
                    stats["duplicates_skipped"] += 1
                    entry["duplicates_skipped"] += 1
                    continue

                try:
                    raw = client.get_message(message_id)
                    mail = parse_message(
                        raw,
                        source_group_hint=None if payload.query else label,
                    )
                    row = email_repo.insert_mail(session, mail)
                    att_counts = {}
                    if payload.download_attachments and mail.has_attachments:
                        att_counts = store_attachments(
                            session, row, mail, client, settings
                        )
                    session.commit()
                    stats["new_messages"] += 1
                    entry["new_messages"] += 1
                    for key, value in att_counts.items():
                        stats[key] = stats.get(key, 0) + value
                except IntegrityError:
                    # Unique gmail_message_id lost a race: treat as duplicate.
                    session.rollback()
                    stats["duplicates_skipped"] += 1
                    entry["duplicates_skipped"] += 1
                except Exception as exc:
                    # Per-message error isolation: never abort the whole sync.
                    session.rollback()
                    stats["failed_messages"] += 1
                    entry["failed_messages"] += 1
                    log_event(
                        log,
                        "sync.message_failed",
                        level=logging.WARNING,
                        message_id=message_id,
                        error=type(exc).__name__,
                        detail=str(exc)[:300],
                    )

                handle.update(
                    message=f"syncing {label}",
                    total_fetched=stats["total_fetched"],
                    new_messages=stats["new_messages"],
                    duplicates_skipped=stats["duplicates_skipped"],
                    failed_messages=stats["failed_messages"],
                )

            stats["groups"].append(entry)
            handle.update(message=f"finished {label}")
    finally:
        session.close()

    seconds = round(time.perf_counter() - started, 3)
    stats["seconds"] = seconds
    stats["finished_at"] = datetime.now(timezone.utc)
    log_event(
        log,
        "sync.completed",
        seconds=seconds,
        total_fetched=stats["total_fetched"],
        new_messages=stats["new_messages"],
        duplicates_skipped=stats["duplicates_skipped"],
        failed_messages=stats["failed_messages"],
    )
    return stats
