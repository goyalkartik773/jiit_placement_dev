"""Deterministic fake Gmail client + payload builders (no network, no OAuth).

The fake mirrors the two methods Step 1 uses (``iter_message_ids``,
``get_message``) plus ``get_attachment`` for the download path, so the whole
sync flow - MIME decode, dedup, per-message isolation, quota abort - runs
against canned Gmail API payloads of the exact ``messages.get`` shape.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Optional

from app.gmail.client import GmailApiError


def b64(text: "str | bytes") -> str:
    raw = text if isinstance(text, bytes) else text.encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def make_payload(
    message_id: str,
    *,
    subject: str,
    sender: str,
    body: str = "",
    html: Optional[str] = None,
    group: str = "jiitengg2027",
    date: str = "Tue, 15 Sep 2026 10:30:00 +0530",
    attachments: Optional[list[dict]] = None,
    thread_id: str = "thread-0001",
) -> dict:
    """Build one canned Gmail API ``messages.get`` response (format=full).

    ``attachments`` items: ``{"filename", "mime_type"}`` plus either
    ``{"data": bytes}`` (inline-embedded) or ``{"attachment_id": str}``
    (server-side, fetched via ``get_attachment``).
    """
    parts: list[dict] = []
    if body:
        parts.append({"mimeType": "text/plain", "body": {"data": b64(body)}})
    if html:
        parts.append({"mimeType": "text/html", "body": {"data": b64(html)}})
    for att in attachments or []:
        part: dict = {
            "mimeType": att.get("mime_type", "application/octet-stream"),
            "filename": att.get("filename", "attachment.bin"),
            "body": {},
        }
        if att.get("data") is not None:
            part["body"] = {"data": b64(att["data"]), "size": len(att["data"])}
        else:
            part["body"] = {
                "attachmentId": att.get("attachment_id", "att-0001"),
                "size": att.get("size", 1024),
            }
        parts.append(part)

    return {
        "id": message_id,
        "threadId": thread_id,
        "labelIds": ["INBOX"],
        "snippet": (body or html or "")[:120],
        "internalDate": "1789381800000",
        "payload": {
            "mimeType": "multipart/mixed" if len(parts) > 1 else "text/plain",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": f"{group}@googlegroups.com"},
                {"name": "Cc", "value": f"{group}@googlegroups.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date},
                {"name": "Message-ID", "value": f"<{message_id}@mail.gmail.com>"},
                {"name": "List-Id", "value": f"<{group}.googlegroups.com>"},
            ],
            "parts": parts,
        },
    }


def make_xlsx(rows: list[list]) -> bytes:
    """A real .xlsx (openpyxl) - used to exercise the attachment download."""
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class FakeGmailClient:
    """Canned-message Gmail client.

    ``groups`` maps a group local-part (``jiitengg2027``) to the message ids
    its ``list:`` query returns; unknown groups list nothing.  Any other
    (custom) query returns every message.

    Failure knobs:
      * ``fail_get_ids`` - ``get_message`` raises (per-message isolation);
      * ``fail_list_after`` - once ``fail_list_after`` groups have been
        listed, the next listing raises ``GmailApiError`` (quota abort);
      * ``attachment_bytes`` - payload for ``get_attachment`` downloads.
    """

    def __init__(
        self,
        messages: list[dict],
        *,
        groups: Optional[dict[str, list[str]]] = None,
        fail_get_ids: frozenset = frozenset(),
        fail_list_after: Optional[int] = None,
        attachment_bytes: Optional[dict[tuple[str, str], bytes]] = None,
    ):
        self.messages = {m["id"]: m for m in messages}
        self.groups = groups if groups is not None else {
            "jiitengg2027": list(self.messages)
        }
        self.fail_get_ids = set(fail_get_ids)
        self.fail_list_after = fail_list_after
        self.attachment_bytes = attachment_bytes or {}
        self.list_calls = 0
        self.get_calls: list[str] = []

    # --- GmailClient interface -------------------------------------------
    def iter_message_ids(self, query: str, max_results: Optional[int] = None):
        self.list_calls += 1
        if (
            self.fail_list_after is not None
            and self.list_calls > self.fail_list_after
        ):
            raise GmailApiError(429, "quota exceeded (fake)")

        if query.startswith("list:"):
            local = query[len("list:"):].split(".googlegroups.com", 1)[0]
            ids = list(self.groups.get(local, []))
        else:
            ids = list(self.messages)  # custom query -> everything canned
        if max_results:
            ids = ids[:max_results]
        yield from ids

    def get_message(self, message_id: str, fmt: str = "full") -> dict:
        self.get_calls.append(message_id)
        if message_id in self.fail_get_ids:
            raise GmailApiError(500, "simulated messages.get failure")
        if message_id not in self.messages:
            raise GmailApiError(404, f"unknown message {message_id}")
        return self.messages[message_id]

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        key = (message_id, attachment_id)
        if key not in self.attachment_bytes:
            raise GmailApiError(404, f"unknown attachment {attachment_id}")
        return self.attachment_bytes[key]

    def close(self) -> None:  # pragma: no cover - parity with GmailClient
        return None
