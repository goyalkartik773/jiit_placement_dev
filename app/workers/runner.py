"""Single-process job runner: one sync and one processing run at a time.

No Celery/queue machinery (spec: keep it simple) - jobs execute on the
request thread while :class:`~app.services.status_store.StatusStore` exposes
live progress to concurrent ``GET .../status`` polls.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from app.services.status_store import JobBusyError, StatusStore
from app.utils.logging import log_event

log = logging.getLogger("app.worker")

T = TypeVar("T")


class RunHandle:
    """What a job body uses to publish live counters/messages."""

    def __init__(self, store: StatusStore, kind: str):
        self._store = store
        self.kind = kind

    def update(self, message: str | None = None, **counters: Any) -> None:
        self._store.update(self.kind, message, **counters)


class JobRunner:
    def __init__(self, store: StatusStore):
        self._store = store

    @property
    def status(self) -> StatusStore:
        return self._store

    def execute(self, kind: str, body: Callable[[RunHandle], T]) -> T:
        """Run ``body`` while tracking status. Re-raises failures after
        recording them (the API layer turns them into HTTP errors)."""
        self._store.begin(kind)  # raises JobBusyError when already running
        handle = RunHandle(self._store, kind)
        log_event(log, "job.start", kind=kind, run_id=self._store.snapshot(kind)["run_id"])
        try:
            result = body(handle)
        except JobBusyError:
            raise
        except Exception as exc:
            self._store.finish(kind, "failed", f"{kind} failed", error=str(exc))
            log_event(
                log, "job.failed", kind=kind, error=str(exc), level=logging.ERROR
            )
            raise
        self._store.finish(kind, "completed", f"{kind} completed")
        log_event(log, "job.completed", kind=kind)
        return result
