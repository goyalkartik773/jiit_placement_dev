"""Gmail API payload -> plain ``MailMessage`` (MIME parsing, HTML -> text).

Deterministic and dependency-free (stdlib ``html.parser``): the clean text
produced here is what the placement_pipeline parser classifies and extracts.
Quoted/forwarded stripping happens later inside ``prepare_parts`` (parser
side); here we only decode what Gmail gives us.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_BLOCK_TAGS = {
    "p", "div", "br", "tr", "table", "ul", "ol", "li", "h1", "h2", "h3",
    "h4", "h5", "h6", "section", "article", "header", "footer", "blockquote",
    "pre", "hr",
}
_SKIP_TAGS = {"script", "style", "head", "title", "meta", "link"}


@dataclass
class MailAttachment:
    """Attachment metadata; ``data`` is present only when inline-embedded."""

    gmail_attachment_id: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    data: Optional[bytes] = None


@dataclass
class MailMessage:
    """One raw email exactly as decoded from the Gmail API."""

    gmail_message_id: str
    thread_id: Optional[str] = None
    message_id_header: Optional[str] = None
    in_reply_to: Optional[str] = None
    source_group: Optional[str] = None
    source_group_email: Optional[str] = None
    sender: Optional[str] = None
    sender_email: Optional[str] = None
    recipient: Optional[str] = None
    cc: Optional[str] = None
    subject: str = ""
    received_raw: Optional[str] = None
    received_at: Optional[datetime] = None
    body_text: str = ""
    body_html: Optional[str] = None
    snippet: Optional[str] = None
    label_ids: list = field(default_factory=list)
    has_attachments: bool = False
    attachments: list = field(default_factory=list)


# --------------------------------------------------------------------- html


class _HTMLTextExtractor(HTMLParser):
    """Block-aware HTML -> text: line breaks kept, script/style dropped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")
        if tag == "li":
            self._chunks.append("- ")
        if tag == "br":
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._chunks.append(data)


def html_to_text(html: str) -> str:
    """Convert an HTML body to readable plain text (deterministic)."""
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        # Malformed HTML: fall back to a crude tag strip rather than dropping
        # the body entirely (the parser tolerates the noise).
        return re.sub(r"<[^>]+>", " ", html)
    text = "".join(extractor._chunks)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


# ------------------------------------------------------------------ headers


def _decode_header(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _headers(payload: dict) -> dict[str, str]:
    """Lower-cased header map; repeated headers (to/cc) are comma-joined."""
    out: dict[str, str] = {}
    for item in payload.get("headers") or []:
        name = str(item.get("name", "")).strip().lower()
        value = _decode_header(str(item.get("value", "")).strip()) or ""
        if not name:
            continue
        if name in out and name in ("to", "cc", "bcc", "received"):
            out[name] = f"{out[name]}, {value}"
        else:
            out.setdefault(name, value)
    return out


_GROUP_RE = re.compile(r"([A-Za-z0-9._-]+)@(?:googlegroups\.com)", re.I)
_LIST_ID_RE = re.compile(r"([A-Za-z0-9._-]+\.googlegroups\.com)", re.I)


def _source_group(
    headers: dict[str, str], hint: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """Best-effort (display name, group email): List-Id > To/Cc > query hint."""
    list_id = headers.get("list-id", "")
    match = _LIST_ID_RE.search(list_id)
    if match:
        local = match.group(1).split(".googlegroups.com", 1)[0]
        return local, f"{local}@googlegroups.com"
    for header in ("to", "cc", "delivered-to"):
        match = _GROUP_RE.search(headers.get(header, ""))
        if match:
            local = match.group(1)
            return local, f"{local}@googlegroups.com"
    if hint:
        local = hint.split("@", 1)[0]
        return local, hint
    return None, None


# --------------------------------------------------------------------- body


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _walk(payload: dict, plains: list, htmls: list, atts: list) -> None:
    mime = payload.get("mimeType", "")
    filename = payload.get("filename") or ""
    body = payload.get("body") or {}

    if payload.get("parts"):
        for part in payload["parts"]:
            _walk(part, plains, htmls, atts)
        return

    if filename or body.get("attachmentId"):
        atts.append(
            MailAttachment(
                gmail_attachment_id=body.get("attachmentId"),
                filename=filename or None,
                mime_type=mime or None,
                file_size=body.get("size"),
                data=_b64url_decode(body["data"]) if body.get("data") else None,
            )
        )
        return

    data = body.get("data")
    if not data:
        return
    text = _b64url_decode(data).decode("utf-8", errors="replace")
    if mime == "text/html":
        htmls.append(text)
    else:  # text/plain and anything unknown treated as text
        plains.append(text)


def _received_at(date_raw: Optional[str], internal_ms: Optional[str]) -> Optional[datetime]:
    if date_raw:
        try:
            parsed = parsedate_to_datetime(date_raw)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
        except (TypeError, ValueError):
            pass
    if internal_ms:
        try:
            return datetime.fromtimestamp(int(internal_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


# -------------------------------------------------------------------- parse


def parse_message(payload: dict, *, source_group_hint: Optional[str] = None) -> MailMessage:
    """Decode one Gmail API ``messages.get`` response into :class:`MailMessage`."""
    top = payload.get("payload") or {}
    headers = _headers(top)
    group_name, group_email = _source_group(headers, source_group_hint)

    full, email_addr = parseaddr(headers.get("from", "") or "")
    sender = _decode_header(full) or None
    sender_email = email_addr or None

    plains: list[str] = []
    htmls: list[str] = []
    atts: list[MailAttachment] = []
    _walk(top, plains, htmls, atts)

    body_text = "\n".join(p for p in plains if p).strip()
    body_html = "\n".join(h for h in htmls if h).strip() or None
    if not body_text and body_html:
        body_text = html_to_text(body_html)

    date_raw = headers.get("date")
    return MailMessage(
        gmail_message_id=payload.get("id", ""),
        thread_id=payload.get("threadId"),
        message_id_header=headers.get("message-id"),
        in_reply_to=headers.get("in-reply-to"),
        source_group=group_name,
        source_group_email=group_email,
        sender=sender,
        sender_email=sender_email,
        recipient=headers.get("to"),
        cc=headers.get("cc"),
        subject=_decode_header(headers.get("subject", "")) or "",
        received_raw=date_raw,
        received_at=_received_at(date_raw, payload.get("internalDate")),
        body_text=body_text,
        body_html=body_html,
        snippet=payload.get("snippet"),
        label_ids=list(payload.get("labelIds") or []),
        has_attachments=bool(atts),
        attachments=atts,
    )


def to_pipeline_received(mail: MailMessage) -> Optional[datetime]:
    """IST-wall-clock naive datetime, matching the legacy corpus semantics."""
    if mail.received_at is None:
        return None
    return mail.received_at.astimezone(IST).replace(tzinfo=None)
