"""Thin Gmail REST client: paginated ``messages.list``, ``get``, attachments.

Design notes:

* ``iter_message_ids`` streams page by page (default 100 ids/page) so a
  1,000+ message sync never holds the whole mailbox in memory;
* transient errors (429/5xx) are retried with exponential backoff, a 401
  forces one token refresh and a single retry;
* responses and errors never include the bearer token.
"""

from __future__ import annotations

import time
from typing import Iterator, Optional

import httpx

from app.gmail.auth import GmailAuth

API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
_RETRY_STATUS = (429, 500, 502, 503, 504)


class GmailApiError(RuntimeError):
    """Non-200 from the Gmail API (status + server reason, no secrets)."""

    def __init__(self, status: int, reason: str = ""):
        self.status = status
        self.reason = reason
        super().__init__(f"Gmail API HTTP {status}" + (f": {reason}" if reason else ""))


class GmailClient:
    def __init__(
        self,
        auth: GmailAuth,
        *,
        page_size: int = 100,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._auth = auth
        self.page_size = page_size
        self._timeout = timeout
        self._max_retries = max_retries
        self._http = httpx.Client(timeout=timeout)

    # --------------------------------------------------------------- http

    def _request(
        self, method: str, url: str, *, params: Optional[dict] = None
    ) -> httpx.Response:
        response: Optional[httpx.Response] = None
        for attempt in range(self._max_retries):
            headers = {"Authorization": f"Bearer {self._auth.access_token()}"}
            try:
                response = self._http.request(
                    method, url, params=params, headers=headers
                )
            except httpx.HTTPError as exc:
                if attempt < self._max_retries - 1:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise GmailApiError(0, f"network error: {exc}") from exc
            if response.status_code == 401 and attempt < self._max_retries - 1:
                self._auth.invalidate()  # refreshed on next access_token()
                continue
            if response.status_code in _RETRY_STATUS and attempt < self._max_retries - 1:
                time.sleep(0.5 * (2**attempt))
                continue
            return response
        return response  # pragma: no cover - loop always returns above

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        if response.status_code >= 400:
            try:
                reason = response.json().get("error", {}).get("message", "")
            except ValueError:
                reason = ""
            raise GmailApiError(response.status_code, reason)
        return response.json()

    # ------------------------------------------------------------ messages

    def iter_message_ids(
        self,
        query: str,
        *,
        page_size: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[str]:
        """Yield message ids for ``query``, one API page at a time."""
        page_size = page_size or self.page_size
        page_token: Optional[str] = None
        yielded = 0
        while True:
            params: dict = {"q": query, "maxResults": page_size}
            if page_token:
                params["pageToken"] = page_token
            data = self._json(self._request("GET", f"{API_ROOT}/messages", params=params))
            batch = data.get("messages") or []
            for item in batch:
                yield item["id"]
                yielded += 1
                if max_results is not None and yielded >= max_results:
                    return
            page_token = data.get("nextPageToken")
            if not page_token or not batch:
                return

    def get_message(self, message_id: str, fmt: str = "full") -> dict:
        data = self._json(
            self._request(
                "GET",
                f"{API_ROOT}/messages/{message_id}",
                params={"format": fmt},
            )
        )
        return data

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        response = self._request(
            "GET", f"{API_ROOT}/messages/{message_id}/attachments/{attachment_id}"
        )
        payload = self._json(response)
        import base64

        data = payload.get("data") or ""
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def close(self) -> None:
        self._http.close()
