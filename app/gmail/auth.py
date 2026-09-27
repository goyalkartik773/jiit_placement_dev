"""OAuth2 access-token refresh for the Gmail API (``gmail.readonly`` scope).

Mirrors the existing .NET ``GmailService``:

* ``credentials.json`` - OAuth *web* client id/secret (path from env);
* ``token.json``       - refresh token + access-token cache.  The file is the
  very same one the .NET admin app uses (``AccessToken`` / ``RefreshToken`` /
  ``ExpiresInSeconds`` / ``IssuedUtc``), so both systems share one consent.

The token is refreshed over HTTPS only when missing/expired (2 minute skew),
and the cache is written back atomically in the same JSON shape.  Tokens are
returned to callers but NEVER logged or embedded in errors.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import GmailConfig
from app.utils.logging import log_event

import logging

log = logging.getLogger("app.gmail.auth")

TOKEN_URL = "https://oauth2.googleapis.com/token"
_SKEW_SECONDS = 120  # refresh 2 minutes before expiry


class GmailAuthError(RuntimeError):
    """OAuth material missing/invalid. Message never contains secrets."""


def _parse_issued(value: str) -> float:
    """Parse .NET's ISO-8601 ``...6414318Z`` (7 fractional digits) safely."""
    m = re.match(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$",
        (value or "").strip(),
    )
    if not m:
        return 0.0
    base, frac, tz = m.group(1), m.group(2) or "0", m.group(3)
    dt = datetime.fromisoformat(f"{base}.{frac[:6]:0<6}")
    if tz in (None, ""):
        dt = dt.replace(tzinfo=timezone.utc)
    elif tz == "Z":
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        sign = 1 if tz[0] == "+" else -1
        tz_clean = tz.replace(":", "")
        offset = timedelta(
            hours=int(tz_clean[1:3]), minutes=int(tz_clean[3:5])
        ) * sign
        dt = dt.replace(tzinfo=timezone(offset))
    return dt.timestamp()


class GmailAuth:
    """Lazily loads OAuth material and hands out valid access tokens."""

    def __init__(self, config: GmailConfig):
        self._config = config
        self._client_id = ""
        self._client_secret = ""
        self._refresh_token = ""
        self._access_token = ""
        self._expires_at = 0.0
        self._loaded = False

    # ------------------------------------------------------------------ load

    def _load(self) -> None:
        if self._loaded:
            return

        creds_path = self._config.credentials_path
        if not creds_path.is_file():
            raise GmailAuthError(
                f"OAuth client file not found: {creds_path} "
                "(set GMAIL_CREDENTIALS_PATH)"
            )
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise GmailAuthError(f"cannot read OAuth client file: {exc}") from exc
        block = creds.get("web") or creds.get("installed") or {}
        client_id, secret = block.get("client_id"), block.get("client_secret")
        if not client_id or not secret:
            raise GmailAuthError("OAuth client file lacks client_id/client_secret")
        self._client_id, self._client_secret = client_id, secret

        token_path = self._config.token_path
        if not token_path.is_file():
            raise GmailAuthError(
                f"OAuth token file not found: {token_path} (set GMAIL_TOKEN_PATH)"
            )
        try:
            token = json.loads(token_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise GmailAuthError(f"cannot read OAuth token file: {exc}") from exc

        refresh = token.get("RefreshToken") or token.get("refresh_token")
        if not refresh:
            raise GmailAuthError("token file has no refresh token - re-consent needed")
        self._refresh_token = refresh
        self._access_token = token.get("AccessToken") or token.get("access_token") or ""
        expires_in = int(
            token.get("ExpiresInSeconds") or token.get("expires_in") or 3599
        )
        issued = token.get("IssuedUtc") or token.get("issued_utc") or ""
        issued_ts = _parse_issued(issued) if isinstance(issued, str) else 0.0
        self._expires_at = (issued_ts + expires_in) if issued_ts else 0.0
        self._loaded = True

    # ------------------------------------------------------------- access

    def invalidate(self) -> None:
        """Drop the cached access token (401 handler forces a refresh)."""
        self._access_token = ""
        self._expires_at = 0.0

    def access_token(self) -> str:
        self._load()
        if self._access_token and time.time() < self._expires_at - _SKEW_SECONDS:
            return self._access_token
        self._refresh()
        return self._access_token

    # ------------------------------------------------------------- refresh

    def _refresh(self) -> None:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            # payload (secrets) is never passed to the logger.
            response = httpx.post(TOKEN_URL, data=payload, timeout=15.0)
        except httpx.HTTPError as exc:
            raise GmailAuthError(f"token refresh network error: {exc}") from exc

        if response.status_code != 200:
            try:
                detail = response.json().get("error", "")
            except ValueError:
                detail = ""
            log_event(
                log,
                "gmail.token_refresh_failed",
                level=logging.ERROR,
                status=response.status_code,
                error=detail,
            )
            raise GmailAuthError(
                f"OAuth token refresh failed (HTTP {response.status_code}"
                + (f": {detail}" if detail else "")
                + ")"
            )

        body = response.json()
        self._access_token = body.get("access_token", "")
        expires_in = int(body.get("expires_in", 3599))
        self._expires_at = time.time() + expires_in
        rotated = body.get("refresh_token")
        if rotated and rotated != self._refresh_token:
            self._refresh_token = rotated
        self._persist(expires_in)
        log_event(log, "gmail.token_refreshed", expires_in=expires_in)

    def _persist(self, expires_in: int) -> None:
        """Write the cache back in the .NET token.json shape (atomic replace)."""
        path = self._config.token_path
        existing: dict[str, Any] = {}
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                existing = {}
        existing.update(
            {
                "AccessToken": self._access_token,
                "RefreshToken": self._refresh_token,
                "ExpiresInSeconds": expires_in,
                "IssuedUtc": datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
            }
        )
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        os.replace(tmp, path)
