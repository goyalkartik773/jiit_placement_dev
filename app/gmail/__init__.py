"""Mail integration: IMAP transport, MIME parsing, attachments.

Gmail REST API + OAuth were retired; ``imaplib`` + an app password now carry
the bytes, and :func:`parse_message` accepts both shapes so nothing downstream
had to change.
"""

from app.gmail.imap_client import (
    ImapAuthError,
    ImapClient,
    ImapError,
    is_quota_error,
)
from app.gmail.mime import MailAttachment, MailMessage, parse_message

__all__ = [
    "ImapAuthError",
    "ImapClient",
    "ImapError",
    "MailAttachment",
    "MailMessage",
    "is_quota_error",
    "parse_message",
]
