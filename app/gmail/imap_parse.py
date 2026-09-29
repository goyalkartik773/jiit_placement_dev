"""IMAP ``RFC822`` literal -> the same ``MailMessage`` the Gmail-API parser makes.

The Gmail REST client is gone; the *shape* downstream code consumes is not.
``sync_service.run_sync`` still calls ``parse_message(raw, source_group_hint=)``
- :func:`app.gmail.mime.parse_message` dispatches here when ``raw`` is not a
dict, so that call site never changed.

Identity mapping (proven live by ``scripts/probe_imap_identity.py``, 6/6):

* ``X-GM-MSGID`` is a **decimal** 64-bit int; ``emails.gmail_message_id`` holds
  its **hex** form - exactly what the Gmail REST API returns.  ``format(int(x),
  'x')`` is the entire mapping, so the unique index keeps deduping on the same
  key: zero migration, zero duplicates.
* ``X-GM-THRID`` -> ``thread_id``.  ``INTERNALDATE`` -> ``received_at``.
* ``X-GM-LABELS`` uses Gmail IMAP spellings (``\\Important``) while the REST API
  uses ``IMPORTANT``; labels are normalized back to the REST form so the stored
  ``label_ids`` stay consistent with the 596 existing rows (``UNREAD`` is derived
  from ``FLAGS`` because IMAP keeps it as a flag, not a label).
* ``snippet`` has no IMAP equivalent - synthesized from the first ~200
  characters of the plain-text body.
* ``gmail_attachment_id`` does not exist in IMAP; a stable synthetic id
  ``part:{sha1(filename|size|content-id)}`` is used instead.

Google Groups deliver a *forwarded* message, so the real ``Date:``/``From:``
can live in the body.  Those regexes are applied **defensively only** - as a
fallback when the corresponding header is missing - so no normal message's
``sender``/``cluster_key``/``received_at`` changes versus the Gmail-API parse.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from app.gmail.mime import (
    MailAttachment,
    MailMessage,
    _decode_header,
    _source_group,
    html_to_text,
)

#: ``snippet`` length (Gmail's own snippet is ~100-120 chars; spec says ~200).
SNIPPET_CHARS = 200

#: ``IMAP INTERNALDATE`` is fixed-format and locale independent; parsed by hand
#: so a non-English locale cannot break it.
_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}
_RE_IMAP_DT = re.compile(
    r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4})$"
)

#: Gmail IMAP system-label spelling -> Gmail REST API ``labelIds`` spelling.
_LABEL_MAP = {
    "\\Inbox": "INBOX",
    "\\Important": "IMPORTANT",
    "\\Starred": "STARRED",
    "\\Draft": "DRAFT",
    "\\Trash": "TRASH",
    "\\Junk": "SPAM",
    "\\Sent": "SENT",
    "\\Muted": "MUTED",
    "\\All": "ALL",
}

#: Fetch-response metadata (INTERNALDATE / FLAGS / X-GM-* live *outside* the
#: RFC822 literal, so they have to be pulled out of the IMAP response line).
_RE_INTERNALDATE = re.compile(r'INTERNALDATE\s+"([^"]+)"')
_RE_FLAGS = re.compile(r"\bFLAGS\s+\(([^)]*)\)")
_RE_LABELS = re.compile(r"X-GM-LABELS\s+\(([^)]*)\)")
_RE_UID = re.compile(r"\bUID\s+(\d+)")
_RE_MSGID = re.compile(r"\bX-GM-MSGID\s+(\d+)")
#: ``X-GM-THRID`` -> ``thread_id`` (also decimal, also converted to hex).
_RE_THRID = re.compile(r"\bX-GM-THRID\s+(\d+)")

#: Forwarded-message headers embedded in the body by Google Groups.
_RE_FWD_DATE = (
    re.compile(r"Date:\s*([^\n\r]+?)(?:\s*\n|\s*\r|\s*Subject:|$)", re.I),
    re.compile(r"Date:\s*(.+?)(?:<br>|Subject:|To:|$)", re.I),
)
_RE_FWD_FROM = re.compile(r"^From:\s*(.+?)$", re.I | re.M)
_RE_FORWARDED_MARK = re.compile(
    r"-+\s*Forwarded message\s*-+|Begin forwarded message|\bFwd:|\bFW:", re.I
)

_MONTH_NAMES = {v: k.capitalize() for k, v in _MONTHS.items()}


# --------------------------------------------------------------------- types


@dataclass
class ImapRawMessage:
    """One ``UID FETCH ... BODY.PEEK[]`` result: metadata + RFC822 literal.

    This is what :meth:`app.gmail.imap_client.ImapClient.get_message` returns
    and what :func:`app.gmail.mime.parse_message` dispatches on.
    """

    msg: Message
    uid: str = ""
    internaldate: Optional[datetime] = None
    flags: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    #: Set by the client so parse-time attachment limits need no settings call.
    max_attachment_bytes: Optional[int] = None


# ------------------------------------------------------------------- helpers


def attachment_part_id(
    filename: Optional[str],
    file_size: Optional[int],
    content_id: Optional[str],
) -> str:
    """Stable synthetic attachment id (IMAP has no ``attachmentId``).

    Deterministic across re-syncs of the same message: id comes from the
    part's own content, never from a counter or a timestamp.
    """
    raw = f"{filename or ''}|{'' if file_size is None else file_size}|{content_id or ''}"
    return "part:" + hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


def parse_internaldate(value: Optional[str]) -> Optional[datetime]:
    """``26-Sep-2026 06:20:56 +0000`` -> aware UTC datetime (locale safe)."""
    if not value:
        return None
    match = _RE_IMAP_DT.match(value.strip())
    if not match:
        return None
    day, mon, year, hour, minute, second, offset = match.groups()
    month = _MONTHS.get(mon.lower())
    if month is None:
        return None
    sign = 1 if offset[0] == "+" else -1
    tz = timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5])))
    try:
        return datetime(
            int(year), month, int(day), int(hour), int(minute), int(second), tzinfo=tz
        )
    except ValueError:
        return None


def _paren_items(inner: str) -> tuple[str, ...]:
    """``("\\Important" \\Seen)`` -> ``('\\\\Important', '\\\\Seen')``."""
    items: list[str] = []
    for quoted, bare in re.findall(r'"((?:[^"\\]|\\.)*)"|(\S+)', inner or ""):
        value = quoted if quoted else bare
        if not value:
            continue
        items.append(value.replace('\\"', '"').replace("\\\\", "\\"))
    return tuple(items)


def normalize_labels(
    x_gm_labels: tuple[str, ...] | list[str], flags: tuple[str, ...] | list[str]
) -> list[str]:
    """Gmail IMAP label/flag spellings -> REST API ``labelIds`` spellings.

    IMAP reports ``\\Important`` (label) and keeps unreadness in ``FLAGS``
    (``\\Seen``), whereas the REST API reports ``IMPORTANT`` and a separate
    ``UNREAD`` entry.  Mapping both keeps ``emails.label_ids`` consistent with
    the rows ingested through the Gmail API.
    """
    out: list[str] = []
    for label in x_gm_labels:
        mapped = _LABEL_MAP.get(label)
        if mapped is None:
            mapped = label[1:].upper() if label.startswith("\\") else label
        if mapped and mapped not in out:
            out.append(mapped)
    if "\\Seen" not in flags and "UNREAD" not in out:
        out.insert(0, "UNREAD")
    return out


def _max_attachment_bytes(override: Optional[int]) -> int:
    if override is not None:
        return override
    try:
        from app.config import load_settings

        return load_settings().gmail.max_attachment_bytes
    except Exception:  # config unavailable (bare test) -> documented default
        return int(os.environ.get("GMAIL_MAX_ATTACHMENT_BYTES", str(5 * 1024 * 1024)))


# ------------------------------------------------------------- fetch parsing


def from_fetch(
    uid: str,
    metadata: bytes | str,
    literal: bytes | str | None,
) -> ImapRawMessage:
    """Build an :class:`ImapRawMessage` from one imaplib FETCH tuple.

    imaplib hands back ``(b'<metadata> BODY[] {n}', b'<literal>')``; the
    metadata line is the only place ``INTERNALDATE``/``FLAGS``/``X-GM-*`` live.
    """
    meta = (
        metadata.decode("utf-8", "replace")
        if isinstance(metadata, bytes)
        else str(metadata or "")
    )
    if isinstance(literal, bytes):
        raw = literal
    elif isinstance(literal, str):
        raw = literal.encode("utf-8", "replace")
    else:
        raw = b""

    internal = _RE_INTERNALDATE.search(meta)
    flags = _RE_FLAGS.search(meta)
    labels = _RE_LABELS.search(meta)
    uid_m = _RE_UID.search(meta)
    msgid = _RE_MSGID.search(meta)
    thrid = _RE_THRID.search(meta)

    message_id = uid
    if msgid:
        # Decimal X-GM-MSGID -> hex form stored in emails.gmail_message_id.
        message_id = format(int(msgid.group(1)), "x")

    message = message_from_bytes(raw)
    if msgid:
        # Stash the resolved id so parse_imap_message() does not re-derive it.
        # Without X-GM-EXT-1 there is no id here at all: ImapClient.get_message
        # supplies ``imap:{uidvalidity}:{uid}`` explicitly instead.
        setattr(message, "_gmail_hex_id", message_id)
    if thrid:
        setattr(message, "_gmail_thread_hex_id", format(int(thrid.group(1)), "x"))

    return ImapRawMessage(
        msg=message,
        uid=(uid_m.group(1) if uid_m else uid),
        internaldate=parse_internaldate(internal.group(1) if internal else None),
        flags=_paren_items(flags.group(1) if flags else ""),
        labels=_paren_items(labels.group(1) if labels else ""),
    )


def raw_message_id(metadata: bytes | str) -> Optional[str]:
    """Decimal ``X-GM-MSGID`` -> hex id, or ``None`` when the item is absent."""
    meta = (
        metadata.decode("utf-8", "replace")
        if isinstance(metadata, bytes)
        else str(metadata or "")
    )
    match = _RE_MSGID.search(meta)
    if not match:
        return None
    return format(int(match.group(1)), "x")


# ------------------------------------------------------------------- headers


def _headers(msg: Message) -> dict[str, str]:
    """Lower-cased header map; repeated headers (to/cc) comma-joined."""
    out: dict[str, str] = {}
    for name, value in msg.items():
        key = str(name or "").strip().lower()
        if not key:
            continue
        decoded = _decode_header(str(value).strip()) or ""
        if key in out and key in ("to", "cc", "bcc", "received"):
            out[key] = f"{out[key]}, {decoded}"
        else:
            out.setdefault(key, decoded)
    return out


# --------------------------------------------------------------------- parts


def _payload_bytes(part: Message) -> bytes:
    data = part.get_payload(decode=True)
    if data is not None:
        return data
    payload = part.get_payload()
    if isinstance(payload, str):
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.encode(charset, "replace")
        except LookupError:
            return payload.encode("utf-8", "replace")
    return b""


def _is_attachment(part: Message, filename: Optional[str]) -> bool:
    """Mirror the Gmail-API walk: a filename (or attachment disposition) wins."""
    if filename:
        return True
    disposition = (part.get_content_disposition() or "").lower()
    return disposition == "attachment"


def _decode_text(data: bytes, charset: Optional[str]) -> str:
    for encoding in (charset or "utf-8", "utf-8", "cp1252", "latin-1"):
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _snippet(text: str) -> str:
    flat = re.sub(r"\s+", " ", text or "").strip()
    return flat[:SNIPPET_CHARS]


def _forwarded_date(body: str) -> Optional[str]:
    """Original ``Date:`` from a Google Groups forwarded body, raw string."""
    if not body or not _RE_FORWARDED_MARK.search(body):
        return None
    for pattern in _RE_FWD_DATE:
        match = pattern.search(body)
        if match:
            value = match.group(1).strip().rstrip(",")
            value = re.sub(r"<[^>]+>", "", value).strip()
            value = re.sub(r"\s*(Subject|To)\s*:.*$", "", value, flags=re.I).strip()
            if value:
                return value
    return None


def _forwarded_sender(body: str) -> Optional[str]:
    """Original ``From:`` from a forwarded body, or ``None``."""
    if not body or not _RE_FORWARDED_MARK.search(body):
        return None
    match = _RE_FWD_FROM.search(body)
    return match.group(1).strip().rstrip(",") if match else None


def _parse_flexible_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    cleaned = re.sub(r"\s+", " ", value).strip()
    for fmt in ("%d %b %Y %H:%M:%S", "%d %b %Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------- parse


def parse_imap_message(
    raw: ImapRawMessage | Message,
    *,
    source_group_hint: Optional[str] = None,
    max_attachment_bytes: Optional[int] = None,
) -> MailMessage:
    """Decode one IMAP message into the shared :class:`MailMessage`."""
    if isinstance(raw, ImapRawMessage):
        msg = raw.msg
        internaldate = raw.internaldate
        flags = raw.flags
        labels = raw.labels
        limit = (
            max_attachment_bytes
            if max_attachment_bytes is not None
            else raw.max_attachment_bytes
        )
        message_id = format_from_msgid(msg) or ""
    else:
        msg = raw
        internaldate = None
        flags = ()
        labels = ()
        limit = max_attachment_bytes
        message_id = ""

    headers = _headers(msg)
    group_name, group_email = _source_group(headers, source_group_hint)

    full, email_addr = parseaddr(headers.get("from", "") or "")
    sender = _decode_header(full) or None
    sender_email = email_addr or None

    plains: list[str] = []
    htmls: list[str] = []
    atts: list[MailAttachment] = []
    limit_bytes = _max_attachment_bytes(limit)

    for part in msg.walk():
        if part.is_multipart():
            continue
        mime = part.get_content_type() or ""
        filename = part.get_filename()
        if _is_attachment(part, filename):
            data = _payload_bytes(part)
            size = len(data)
            content_id = part.get("Content-ID")
            keep = size <= limit_bytes
            atts.append(
                MailAttachment(
                    gmail_attachment_id=attachment_part_id(filename, size, content_id),
                    filename=filename,
                    mime_type=mime or None,
                    file_size=size,
                    # Parse-time size gate: over the limit the bytes are dropped
                    # immediately, so store_attachments() records ``skipped``.
                    data=data if keep else None,
                )
            )
            continue
        if mime not in ("text/plain", "text/html"):
            continue
        text = _decode_text(_payload_bytes(part), part.get_content_charset())
        (htmls if mime == "text/html" else plains).append(text)

    # A file with no filename but an attachment disposition still counts; a
    # plain text part that happens to carry a filename went through the branch
    # above, exactly like the Gmail-API walk.
    body_text = "\n".join(p for p in plains if p).strip()
    body_html = "\n".join(h for h in htmls if h).strip() or None
    if not body_text and body_html:
        body_text = html_to_text(body_html)

    date_raw = headers.get("date")
    fwd_date = _forwarded_date(body_text)
    fwd_from = _forwarded_sender(body_text)

    # Defensive only: Google Groups may deliver a forwarded body, so the real
    # Date/From can be *inside* the message.  Used solely when the header that
    # the Gmail-API parse relied on is missing - normal messages therefore get
    # byte-identical values either way.
    if not sender and fwd_from:
        fwd_full, fwd_addr = parseaddr(fwd_from)
        sender = _decode_header(fwd_full) or None
        sender_email = fwd_addr or sender_email

    received_at = internaldate or _parse_flexible_date(date_raw) or _parse_flexible_date(
        fwd_date
    )
    received_raw = date_raw or fwd_date

    if not message_id:
        # Non-Gmail IMAP: no X-GM-MSGID, so identity falls back to the RFC
        # Message-ID header (documented caveat - see imap_client docstring).
        message_id = headers.get("message-id", "").strip() or ""

    return MailMessage(
        gmail_message_id=message_id,
        thread_id=getattr(msg, "_gmail_thread_hex_id", None),
        message_id_header=headers.get("message-id"),
        in_reply_to=headers.get("in-reply-to"),
        source_group=group_name,
        source_group_email=group_email,
        sender=sender,
        sender_email=sender_email,
        recipient=headers.get("to"),
        cc=headers.get("cc"),
        subject=_decode_header(headers.get("subject", "")) or "",
        received_raw=received_raw,
        received_at=received_at,
        body_text=body_text,
        body_html=body_html,
        snippet=_snippet(body_text),
        label_ids=normalize_labels(labels, flags),
        has_attachments=bool(atts),
        attachments=atts,
    )


def format_from_msgid(msg: Message) -> Optional[str]:
    """Hex id from ``X-GM-MSGID`` when the caller stashed it on the message.

    :func:`from_fetch` writes the resolved hex id into a private attribute so
    the parser does not have to re-derive it; absent for a bare ``Message``.
    """
    value = getattr(msg, "_gmail_hex_id", None)
    return str(value) if value else None


def attachment_bytes(
    raw: ImapRawMessage | Message, attachment_id: str
) -> Optional[bytes]:
    """Bytes of the part whose synthetic id matches ``attachment_id``.

    Needed for the ``get_attachment(message_id, attachment_id)`` seam: with
    Gmail's REST API this was a second HTTP call; with IMAP the literal is
    already in the fetched message, so it is a lookup.
    """
    msg = raw.msg if isinstance(raw, ImapRawMessage) else raw
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if not _is_attachment(part, filename):
            continue
        data = _payload_bytes(part)
        if attachment_part_id(
            filename, len(data), part.get("Content-ID")
        ) == attachment_id:
            return data
    return None
