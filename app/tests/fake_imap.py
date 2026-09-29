"""Canned IMAP messages + a fake ``ImapClient`` (no network, no credentials).

``FakeImapClient`` mirrors the exact surface :class:`app.gmail.imap_client.
ImapClient` exposes, so ``run_sync``, the watcher and ``parse_message``'s IMAP
branch all run against real ``email.message`` payloads - the same bytes
``imaplib`` would hand over.  Every ``get_message`` goes through the real
:func:`app.gmail.imap_parse.from_fetch`, so the metadata parser (decimal
``X-GM-MSGID``, ``INTERNALDATE``, ``FLAGS``, ``X-GM-LABELS``) is exercised too.

Failure knobs mirror the Gmail-API fake so the same isolation tests hold:
``fail_get_ids`` (per-message), ``fail_list_after`` (listing abort).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.gmail.imap_client import ImapError
from app.gmail.imap_parse import ImapRawMessage, from_fetch

#: Same default the config uses (5 MiB) unless a test overrides it.
DEFAULT_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


# --------------------------------------------------------------- raw builders


def _headers_to_bytes(headers: list[str], body: str = "") -> bytes:
    head = "\n".join(headers)
    return (head + "\n\n" + body).encode("utf-8")


def make_imap_raw(
    *,
    message_id: str,
    subject: str,
    sender: str,
    body: str = "",
    html: Optional[str] = None,
    group: str = "jiitengg2027",
    date: str = "Tue, 15 Sep 2026 10:30:00 +0530",
    to: Optional[str] = None,
    message_id_header: Optional[str] = None,
    extra_headers: Optional[list[str]] = None,
    attachments: Optional[list[dict]] = None,
) -> bytes:
    """Build an RFC822 literal with stdlib ``EmailMessage``.

    ``attachments`` items: ``{"filename", "mime_type", "data": bytes}``.
    """
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to or f"{group}@googlegroups.com"
    msg["Date"] = date
    msg["Message-ID"] = message_id_header or f"<{message_id}@mail.example>"
    msg["List-Id"] = f"<{group}.googlegroups.com>"
    for header in extra_headers or []:
        name, _, value = header.partition(":")
        msg[name.strip()] = value.strip()

    if html:
        msg.set_content(body or html)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body or "")

    for att in attachments or []:
        mime = att.get("mime_type", "application/octet-stream")
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(
            att.get("data", b""),
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att.get("filename", "attachment.bin"),
        )
    return msg.as_bytes()


@dataclass
class CannedMessage:
    """One message the fake will serve, plus the IMAP metadata around it."""

    uid: int
    hex_id: str
    raw: bytes
    internaldate: str = "15-Sep-2026 10:30:00 +0000"
    flags: tuple[str, ...] = ()
    labels: tuple[str, ...] = ("\\Inbox",)
    thread_hex: Optional[str] = None
    group: str = "jiitengg2027"
    seen: bool = False
    #: Overridden by the client so parse-time size gates are deterministic.
    max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES


class FakeImapClient:
    """In-memory stand-in for :class:`app.gmail.imap_client.ImapClient`."""

    def __init__(
        self,
        messages: list[CannedMessage],
        *,
        groups: Optional[dict[str, list[str]]] = None,
        fail_get_ids: frozenset = frozenset(),
        fail_list_after: Optional[int] = None,
        attachment_bytes: Optional[dict[tuple[str, str], bytes]] = None,
        page_size: int = 100,
    ):
        self.messages = {m.hex_id: m for m in messages}
        self.groups = groups if groups is not None else {
            "jiitengg2027": [m.hex_id for m in messages]
        }
        self.fail_get_ids = set(fail_get_ids)
        self.fail_list_after = fail_list_after
        self.attachment_bytes = attachment_bytes or {}
        self.page_size = page_size

        self.list_calls = 0
        self.get_calls: list[str] = []
        #: ids (and the raw batches) the watcher asked to mark ``\Seen``
        self.marked_seen: list[str] = []
        self.mark_seen_batches: list[list[str]] = []
        self.marked_unseen: list[str] = []
        self.close_calls = 0

    # --- listing ---------------------------------------------------------

    def _ids_for(self, query: str) -> list[str]:
        if query.startswith("list:"):
            local = query[len("list:"):].split(".googlegroups.com", 1)[0]
            ids = list(self.groups.get(local, []))
        else:
            ids = list(self.messages)  # custom query -> everything canned
        # Newest first, mirroring Gmail's messages.list ordering.
        return sorted(ids, key=lambda i: self.messages[i].uid, reverse=True)

    def _list(
        self,
        query: str,
        *,
        unseen_only: bool,
        max_results: Optional[int],
    ):
        self.list_calls += 1
        if self.fail_list_after is not None and self.list_calls > self.fail_list_after:
            raise ImapError(429, "quota exceeded (fake)")
        ids = self._ids_for(query)
        if unseen_only:
            ids = [i for i in ids if not self.messages[i].seen]
        if max_results:
            ids = ids[:max_results]
        return ids

    def iter_message_ids(
        self, query: str, *, page_size=None, max_results=None
    ):
        yield from self._list(query, unseen_only=False, max_results=max_results)

    def iter_unseen_ids(
        self, query: str, *, page_size=None, max_results=None
    ):
        yield from self._list(query, unseen_only=True, max_results=max_results)

    # --- fetching --------------------------------------------------------

    @staticmethod
    def _metadata(message: CannedMessage) -> bytes:
        parts = [
            f"UID {message.uid}",
            f"X-GM-MSGID {int(message.hex_id, 16)}",
        ]
        thread = message.thread_hex or message.hex_id
        parts.append(f"X-GM-THRID {int(thread, 16)}")
        parts.append(f'INTERNALDATE "{message.internaldate}"')
        if message.flags:
            parts.append("FLAGS (" + " ".join(message.flags) + ")")
        if message.labels:
            quoted = " ".join(f'"{label}"' for label in message.labels)
            parts.append(f"X-GM-LABELS ({quoted})")
        joined = " ".join(parts)
        return (
            f'{message.uid} ({joined} BODY[] {{{len(message.raw)}}}'.encode("utf-8")
        )

    def get_message(self, message_id: str, fmt: str = "full") -> ImapRawMessage:
        self.get_calls.append(message_id)
        if message_id in self.fail_get_ids:
            raise ImapError(500, "simulated fetch failure")
        message = self.messages.get(message_id)
        if message is None:
            raise ImapError(404, f"unknown message {message_id}")
        raw = from_fetch(str(message.uid), self._metadata(message), message.raw)
        raw.max_attachment_bytes = message.max_attachment_bytes
        # The watcher may have flipped \Seen on the canned copy.
        if message.seen and "\\Seen" not in raw.flags:
            raw.flags = tuple(raw.flags) + ("\\Seen",)
        elif not message.seen and "\\Seen" in raw.flags:
            raw.flags = tuple(f for f in raw.flags if f != "\\Seen")
        return raw

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        key = (message_id, attachment_id)
        if key not in self.attachment_bytes:
            raise ImapError(404, f"unknown attachment {attachment_id}")
        return self.attachment_bytes[key]

    # --- flags -----------------------------------------------------------

    def mark_seen(self, message_id: str) -> bool:
        return self.mark_seen_many([message_id]) == 1

    def mark_seen_many(self, message_ids) -> int:
        marked: list[str] = []
        for message_id in message_ids:
            message = self.messages.get(message_id)
            if message is None:
                continue
            message.seen = True
            marked.append(message_id)
        if marked:
            self.marked_seen.extend(marked)
            self.mark_seen_batches.append(list(marked))
        return len(marked)

    def mark_unseen(self, message_id: str) -> bool:
        message = self.messages.get(message_id)
        if message is None:
            return False
        message.seen = False
        self.marked_unseen.append(message_id)
        return True

    # --- misc ------------------------------------------------------------

    def capabilities(self) -> tuple[str, ...]:
        return ("IMAP4REV1", "IDLE", "X-GM-EXT-1")

    def idle_wait(self, timeout: float) -> bool:
        return False  # polling fallback

    def close(self) -> None:
        self.close_calls += 1
        return None


def make_canned(
    hex_id: str,
    *,
    uid: int,
    group: str = "jiitengg2027",
    subject: str = "Placement notice",
    sender: str = "TPC <tpc@example.com>",
    body: str = "Body text",
    html: Optional[str] = None,
    attachments: Optional[list[dict]] = None,
    seen: bool = False,
    flags: tuple[str, ...] = (),
    labels: tuple[str, ...] = ("\\Inbox",),
    internaldate: str = "15-Sep-2026 10:30:00 +0000",
    max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
    **raw_kwargs,
) -> CannedMessage:
    """Convenience: build a ``CannedMessage`` from a hex id."""
    return CannedMessage(
        uid=uid,
        hex_id=hex_id,
        raw=make_imap_raw(
            message_id=hex_id,
            subject=subject,
            sender=sender,
            body=body,
            html=html,
            group=group,
            attachments=attachments,
            **raw_kwargs,
        ),
        internaldate=internaldate,
        flags=flags,
        labels=labels,
        group=group,
        seen=seen,
        max_attachment_bytes=max_attachment_bytes,
    )


__all__ = [
    "CannedMessage",
    "DEFAULT_MAX_ATTACHMENT_BYTES",
    "FakeImapClient",
    "make_canned",
    "make_imap_raw",
]
