"""IMAP transport (stdlib ``imaplib``) - replaces the retired Gmail REST client.

Same seam :func:`app.services.sync_service.run_sync` already programs against,
so that module's logic did not change::

    iter_message_ids(query, *, page_size=None, max_results=None)  -> ids
    get_message(message_id, fmt="full")                            -> raw
    get_attachment(message_id, attachment_id)                      -> bytes
    close()

Identity mapping (live-proven by ``scripts/probe_imap_identity.py``, 6/6)::

    gmail_message_id = format(int(X-GM-MSGID), 'x')     # decimal -> hex
    thread_id        = format(int(X-GM-THRID), 'x')
    received_at      = INTERNALDATE
    label_ids        = X-GM-LABELS (+ UNREAD derived from FLAGS)
    search           = X-GM-RAW "<same group_query() string>"

``X-GM-MSGID`` is what the Gmail REST API returns as ``id``, so the unique
index on ``emails.gmail_message_id`` keeps deduping on the same key: zero
migration, zero duplicates for the existing 596 rows.

Pacing/backoff notes
--------------------
* ``min_interval_ms`` spaces command *groups* (one batched metadata FETCH per
  ``page_size`` ids, not one round trip per message).
* The connection is long-lived (the container caches one client), so a drop is
  repaired with a single transparent reconnect + retry; authentication failure
  raises :class:`ImapAuthError` and is never retried.
* Every message passed to a log/exception goes through :meth:`_redact`, which
  strips the app password - the secret is only ever handed to ``imaplib``.

Non-Gmail IMAP providers (documented caveat)
--------------------------------------------
``X-GM-EXT-1`` is a Gmail extension.  Without it there is no ``X-GM-MSGID``, so
ids fall back to ``imap:{uidvalidity}:{uid}`` and ``list:`` queries are
translated to ``HEADER List-Id ...``; anything richer than a ``list:`` query is
rejected loudly rather than silently returning the whole mailbox.
"""

from __future__ import annotations

import imaplib
import logging
import re
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from app.config import GmailConfig
from app.gmail.imap_parse import (
    ImapRawMessage,
    attachment_bytes,
    from_fetch,
    raw_message_id,
)
from app.utils.logging import log_event

log = logging.getLogger("app.gmail.imap")

_QUOTA_MARKERS = ("quota exceeded", "rate limit", "ratelimit", "too many")
_AUTH_MARKERS = (
    "authenticationfailed",
    "invalid credentials",
    "invalid login",
    "application-specific password",
    "too many login attempts",
    "please log in via web",
    "not accepted",
)
_RE_LIST_QUERY = re.compile(r"^list:([^\s]+)$", re.I)
_RE_METADATA = re.compile(r"\bUID\s+(\d+)")


def is_quota_error(status: int, reason: str) -> bool:
    """Server-side throttling/quotas - retryable after the window resets."""
    text = (reason or "").lower()
    return status in (403, 429) or any(marker in text for marker in _QUOTA_MARKERS)


def _is_auth_error(reason: str) -> bool:
    text = (reason or "").lower()
    return any(marker in text for marker in _AUTH_MARKERS)


def _text(data) -> str:
    """imaplib payload -> printable reason (never contains the password)."""
    if not data:
        return ""
    parts: list[str] = []
    for item in data:
        if isinstance(item, bytes):
            parts.append(item.decode("utf-8", "replace"))
        elif isinstance(item, (list, tuple)):
            parts.append(_text(item))
        elif item is not None:
            parts.append(str(item))
    return " ".join(p for p in parts if p).strip()


def _quote(value: str) -> str:
    """IMAP quoted-string: ``"`` and ``\`` must be escaped."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _metadata_segments(data) -> list[str]:
    """imaplib FETCH payload -> decoded metadata lines (empties dropped)."""
    out: list[str] = []
    for part in data or []:
        meta = part[0] if isinstance(part, tuple) else part
        if isinstance(meta, bytes):
            text = meta.decode("utf-8", "replace")
        elif meta is None:
            continue
        else:
            text = str(meta)
        if text.strip():
            out.append(text)
    return out


class ImapError(RuntimeError):
    """Non-success IMAP result (``NO``/``BAD`` or a lost connection)."""

    def __init__(self, status: int, reason: str = ""):
        self.status = status
        self.reason = reason
        super().__init__(f"IMAP error {status}" + (f": {reason}" if reason else ""))


class ImapAuthError(ImapError):
    """Login rejected: bad app password, 2-Step Verification off, IMAP off.

    Never retried - the caller surfaces it verbatim (variable names only).
    """


class ImapClient:
    """Mail transport for ``run_sync`` and the auto-watcher.

    One long-lived connection per client: ``iter_message_ids`` streams ids and
    ``get_message``/``get_attachment`` reuse the same session (IMAP cannot
    fetch by id without a selected mailbox).  ``close()`` is idempotent.
    """

    #: How many parsed messages to keep for ``get_attachment`` lookups.
    CACHE_MESSAGES = 8

    def __init__(self, config: GmailConfig, *, timeout: Optional[float] = None):
        self._config = config
        self._timeout = float(timeout if timeout is not None else config.request_timeout)
        # Fail fast at construction with variable names only - the sync endpoint
        # is the only thing that builds a real client (tests inject a fake).
        if not config.imap_email or not config.imap_app_password:
            raise ImapAuthError(
                401,
                "IMAP_EMAIL / IMAP_APP_PASSWORD not set in the environment "
                "(add them to placement_pipeline/.env)",
            )
        self._conn: Optional[imaplib.IMAP4_SSL] = None
        self._gmail_ext: Optional[bool] = None
        self._uid_by_id: dict[str, str] = {}
        self._raw_by_id: dict[str, ImapRawMessage] = {}
        self._last_command = 0.0

    # ------------------------------------------------------------ connection

    def _redact(self, value: str) -> str:
        """Guarantee the app password can never reach a log or an exception."""
        password = self._config.imap_app_password
        text = str(value or "")
        return text.replace(password, "***") if password else text

    def _open(self) -> imaplib.IMAP4_SSL:
        cfg = self._config
        try:
            conn = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port, timeout=self._timeout)
        except OSError as exc:
            raise ImapError(
                0, f"cannot reach {cfg.imap_host}:{cfg.imap_port}: {exc}"
            ) from exc
        try:
            conn.login(cfg.imap_email, cfg.imap_app_password)
        except imaplib.IMAP4.error as exc:
            reason = self._redact(str(exc))
            try:
                conn.shutdown()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
            raise ImapAuthError(
                401,
                f"IMAP login rejected for {cfg.imap_email}: {reason} "
                "(check IMAP_APP_PASSWORD and that 2-Step Verification + IMAP "
                "are enabled for the account)",
            ) from exc
        status, _ = conn.select(cfg.imap_mailbox, readonly=False)
        if str(status).upper() != "OK":
            reason = self._redact(_text(_))
            try:
                conn.logout()
            except Exception:  # pragma: no cover
                pass
            raise ImapError(0, f"SELECT {cfg.imap_mailbox} failed: {status} {reason}")
        self._gmail_ext = any(
            str(c).upper() == "X-GM-EXT-1" for c in (conn.capabilities or ())
        )
        return conn

    def connect(self) -> None:
        """Open (or re-use) the mailbox connection."""
        self._connection()

    def disconnect(self) -> None:
        conn, self._conn = self._conn, None
        self._gmail_ext = None
        if conn is None:
            return
        try:
            conn.logout()
        except Exception:  # pragma: no cover - logout is best effort
            pass

    #: Seam parity with the retired ``GmailClient.close()``.
    close = disconnect

    @contextmanager
    def session(self):
        """Open the connection for a block of work and always release it."""
        self._connection()
        try:
            yield self
        finally:
            self.disconnect()

    def _connection(self) -> imaplib.IMAP4_SSL:
        if self._conn is None:
            self._conn = self._open()
            self._last_command = time.monotonic()
        return self._conn

    def capabilities(self) -> tuple[str, ...]:
        return tuple(str(c) for c in (self._connection().capabilities or ()))

    def _throttle(self) -> None:
        ms = self._config.min_interval_ms
        if ms <= 0:
            return
        wait = ms / 1000.0 - (time.monotonic() - self._last_command)
        if wait > 0:
            time.sleep(wait)

    def _cmd(self, name: str, *args):
        """One paced IMAP command; reconnects once when the socket drops."""
        conn = self._connection()
        self._throttle()
        try:
            status, data = getattr(conn, name)(*args)
        except (imaplib.IMAP4.abort, OSError) as exc:
            # Dropped connection / TLS hiccup: repair and retry exactly once.
            log_event(log, "imap.reconnect", detail=self._redact(str(exc))[:200])
            self._drop()
            conn = self._connection()
            self._throttle()
            try:
                status, data = getattr(conn, name)(*args)
            except imaplib.IMAP4.error as exc2:
                raise ImapError(0, self._redact(_text([exc2]))) from exc2
        except imaplib.IMAP4.error as exc:
            raise ImapError(0, self._redact(_text([exc]))) from exc
        finally:
            self._last_command = time.monotonic()

        if str(status).upper() != "OK":
            reason = self._redact(_text(data))
            if str(status).upper() == "BYE":
                self._drop()
            detail = f"{name} -> {status}: {reason}"
            if _is_auth_error(reason):
                raise ImapAuthError(401, detail)
            raise ImapError(0, detail)
        return status, data

    def _drop(self) -> None:
        conn, self._conn = self._conn, None
        self._gmail_ext = None
        if conn is None:
            return
        try:
            conn.shutdown()
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------- discovery

    def _uidvalidity(self) -> str:
        conn = self._connection()
        try:
            response = conn.response("UIDVALIDITY")
        except Exception:  # pragma: no cover - not all servers report it
            return "0"
        value = response[1] if response else None
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        return str(value or "0")

    def _fallback_id(self, uid: int | str) -> str:
        return f"imap:{self._uidvalidity()}:{uid}"

    def _gmail_extension(self) -> bool:
        if self._gmail_ext is None:
            self._gmail_ext = any(
                str(c).upper() == "X-GM-EXT-1" for c in self.capabilities()
            )
        return bool(self._gmail_ext)

    def _search_terms(self, query: str, unseen_only: bool) -> list[str]:
        terms: list[str] = ["UNSEEN"] if unseen_only else []
        q = (query or "").strip()
        if self._gmail_extension():
            return terms + (["X-GM-RAW", _quote(q)] if q else ["ALL"])
        # Non-Gmail fallback: Gmail's X-GM-RAW syntax does not exist here.
        match = _RE_LIST_QUERY.match(q) if q else None
        if match:
            return terms + ["HEADER", "List-Id", _quote(f"<{match.group(1)}>")]
        if q:
            raise ImapError(
                0,
                f"non-Gmail IMAP cannot evaluate Gmail query {q!r} - only "
                "'list:<group>' queries are supported without X-GM-EXT-1",
            )
        return terms + ["ALL"]

    def _search(self, query: str, *, unseen_only: bool = False) -> list[int]:
        _, data = self._cmd("uid", "SEARCH", None, *self._search_terms(query, unseen_only))
        raw = data[0] if data else b""
        if isinstance(raw, bytes):
            raw = raw.decode("ascii", "replace")
        uids: list[int] = []
        for token in str(raw or "").split():
            if token.isdigit():
                uids.append(int(token))
        return sorted(uids)

    def _resolve_ids(
        self, uids: list[int], *, page_size: Optional[int] = None
    ) -> dict[int, str]:
        """Batched ``UID FETCH (UID X-GM-MSGID)`` -> ``uid -> message id``.

        One round trip per page of ids (the old REST client paged 100 ids per
        call), so a full mailbox listing never costs one command per mail.
        """
        chunk = max(1, page_size or self._config.page_size or 100)
        mapping: dict[int, str] = {}
        for start in range(0, len(uids), chunk):
            part = uids[start:start + chunk]
            spec = ",".join(str(u) for u in part)
            _, data = self._cmd("uid", "FETCH", spec, "(UID X-GM-MSGID)")
            for meta in _metadata_segments(data):
                uid_m = _RE_METADATA.search(meta)
                mid = raw_message_id(meta)
                if uid_m and mid:
                    mapping[int(uid_m.group(1))] = mid
        return mapping

    def _discover(
        self,
        query: str,
        *,
        unseen_only: bool = False,
        page_size: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[tuple[int, str]]:
        """Yield ``(uid, message_id)`` newest-first (Gmail list ordering)."""
        uids = self._search(query, unseen_only=unseen_only)
        if not uids:
            return
        if max_results and len(uids) > max_results:
            uids = uids[-max_results:]  # highest UIDs == newest arrivals
        mapping = self._resolve_ids(uids, page_size=page_size)
        for uid in sorted((u for u in uids if u in mapping), reverse=True):
            message_id = mapping[uid]
            self._uid_by_id[message_id] = str(uid)
            yield uid, message_id

    def iter_message_ids(
        self,
        query: str,
        *,
        page_size: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[str]:
        """Stream message ids for ``query``, newest first.

        ``page_size``/``max_results`` keep the old REST client's meaning:
        ids per listing page and an overall cap for this call.
        """
        for _uid, message_id in self._discover(
            query, page_size=page_size, max_results=max_results
        ):
            yield message_id

    def iter_unseen_ids(
        self,
        query: str,
        *,
        page_size: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[str]:
        """Same as :meth:`iter_message_ids` but only ``UNSEEN`` messages.

        Used by the auto-watcher for discovery; nothing is marked ``\Seen``
        here - ``BODY.PEEK[]`` and this search leave flags untouched.
        """
        for _uid, message_id in self._discover(
            query, unseen_only=True, page_size=page_size, max_results=max_results
        ):
            yield message_id

    # ----------------------------------------------------------------- fetch

    def _uid_for(self, message_id: str) -> Optional[str]:
        uid = self._uid_by_id.get(message_id)
        if uid:
            return uid
        # ``imap:{uidvalidity}:{uid}`` (non-Gmail) carries its own address.
        parts = message_id.split(":")
        if len(parts) == 3 and parts[0] == "imap":
            self._uid_by_id[message_id] = parts[2]
            return parts[2]
        try:
            decimal = str(int(message_id, 16))
        except ValueError:
            return None
        # Gmail fallback: ask the server which UID owns this X-GM-MSGID.
        _, data = self._cmd("uid", "SEARCH", None, "X-GM-MSGID", decimal)
        raw = data[0] if data else b""
        if isinstance(raw, bytes):
            raw = raw.decode("ascii", "replace")
        found = [int(t) for t in str(raw or "").split() if t.isdigit()]
        if not found:
            return None
        self._uid_by_id[message_id] = str(found[-1])
        return str(found[-1])

    def get_message(self, message_id: str, fmt: str = "full") -> ImapRawMessage:
        """Fetch one message as an :class:`ImapRawMessage`.

        ``BODY.PEEK[]`` is used on purpose: the fetch must never set ``\Seen``
        as a side effect (only the watcher's explicit ``mark_seen`` does).
        ``fmt`` is kept for seam parity with the REST client - IMAP always
        returns the complete RFC822 literal.
        """
        uid = self._uid_for(message_id)
        if uid is None:
            raise ImapError(404, f"message {message_id} not found in mailbox")
        cached = self._raw_by_id.get(message_id)
        if cached is not None:
            return cached
        _, data = self._cmd(
            "uid",
            "FETCH",
            uid,
            "(INTERNALDATE FLAGS X-GM-LABELS UID X-GM-MSGID X-GM-THRID BODY.PEEK[])",
        )
        literal = None
        metadata = ""
        for part in data or []:
            if isinstance(part, tuple) and len(part) >= 2:
                metadata, literal = part[0], part[1]
                break
            if isinstance(part, bytes) and b"BODY[]" in part:
                metadata = part
        if metadata == "" and literal is None:
            raise ImapError(404, f"message {message_id} (uid {uid}) returned no data")
        raw = from_fetch(str(uid), metadata, literal)
        raw.max_attachment_bytes = self._config.max_attachment_bytes
        # Prefer the id the caller asked for: it is the same value by
        # construction, but a non-Gmail provider may only have produced
        # ``imap:{uidvalidity}:{uid}`` from the header fallback.
        if raw.msg is not None:
            setattr(raw.msg, "_gmail_hex_id", message_id)
        if len(self._raw_by_id) >= self.CACHE_MESSAGES:
            self._raw_by_id.pop(next(iter(self._raw_by_id)))
        self._raw_by_id[message_id] = raw
        return raw

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Bytes of one attachment (a lookup - the literal is already fetched)."""
        raw = self._raw_by_id.get(message_id)
        if raw is None:
            raw = self.get_message(message_id)
        data = attachment_bytes(raw, attachment_id)
        if data is None:
            raise ImapError(
                404, f"attachment {attachment_id} not found on message {message_id}"
            )
        return data

    # ----------------------------------------------------------------- flags

    def mark_seen(self, message_id: str) -> bool:
        """Set ``\Seen`` - called only after the row is committed."""
        uid = self._uid_for(message_id)
        if uid is None:
            return False
        self._cmd("uid", "STORE", uid, "+FLAGS.SILENT", "(\\Seen)")
        return True

    def mark_unseen(self, message_id: str) -> bool:
        """Clear ``\Seen`` (self-healing rollback if a later step failed)."""
        uid = self._uid_for(message_id)
        if uid is None:
            return False
        self._cmd("uid", "STORE", uid, "-FLAGS.SILENT", "(\\Seen)")
        return True
