"""Process-wide singletons wired into FastAPI via ``app.state.container``."""

from __future__ import annotations

from typing import Callable, Optional

from app.config import Settings, load_settings
from app.gmail.imap_client import ImapClient
from app.services.status_store import StatusStore
from app.workers.runner import JobRunner


class Container:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.status = StatusStore()
        self.runner = JobRunner(self.status)
        self._client: Optional[ImapClient] = None
        self._client_factory: Optional[Callable[[], ImapClient]] = None

    def set_client_factory(self, factory: Callable[[], ImapClient]) -> None:
        """Tests inject a fake mail client here (no network)."""
        self._client_factory = factory
        self._client = None

    def gmail_client(self) -> ImapClient:
        if self._client_factory is not None:
            return self._client_factory()
        if self._client is None:
            # One long-lived IMAP connection per process; the client reconnects
            # itself on a drop and never logs the app password.
            self._client = ImapClient(
                self.settings.gmail,
                timeout=self.settings.gmail.request_timeout,
            )
        return self._client
