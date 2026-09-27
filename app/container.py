"""Process-wide singletons wired into FastAPI via ``app.state.container``."""

from __future__ import annotations

from typing import Callable, Optional

from app.config import Settings, load_settings
from app.gmail.auth import GmailAuth
from app.gmail.client import GmailClient
from app.services.status_store import StatusStore
from app.workers.runner import JobRunner


class Container:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.status = StatusStore()
        self.runner = JobRunner(self.status)
        self._client: Optional[GmailClient] = None
        self._client_factory: Optional[Callable[[], GmailClient]] = None

    def set_client_factory(self, factory: Callable[[], GmailClient]) -> None:
        """Tests inject a fake Gmail client here (no network)."""
        self._client_factory = factory
        self._client = None

    def gmail_client(self) -> GmailClient:
        if self._client_factory is not None:
            return self._client_factory()
        if self._client is None:
            auth = GmailAuth(self.settings.gmail)
            self._client = GmailClient(
                auth,
                page_size=self.settings.gmail.page_size,
                timeout=self.settings.gmail.request_timeout,
                min_interval_ms=self.settings.gmail.min_interval_ms,
            )
        return self._client
