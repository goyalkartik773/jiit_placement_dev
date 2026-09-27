"""Job status tracking for the sync/processing runs (drives the UI popup)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional
from uuid import uuid4


class JobBusyError(RuntimeError):
    """Raised when a run is already active (API turns this into HTTP 409)."""

    def __init__(self, kind: str, snapshot: dict):
        self.kind = kind
        self.snapshot = snapshot
        super().__init__(f"a {kind} run is already in progress")


@dataclass
class RunState:
    kind: str
    run_id: Optional[str] = None
    state: str = "idle"  # idle | running | completed | failed
    message: str = ""
    counters: dict = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    def snapshot(self) -> dict:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "state": self.state,
            "message": self.message,
            "counters": dict(self.counters),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


class StatusStore:
    """Thread-safe live status for each job kind (single process)."""

    KINDS = ("sync", "processing")

    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, RunState] = {k: RunState(kind=k) for k in self.KINDS}

    def snapshot(self, kind: str) -> dict:
        with self._lock:
            return self._runs[kind].snapshot()

    def is_running(self, kind: str) -> bool:
        with self._lock:
            return self._runs[kind].state == "running"

    def begin(self, kind: str) -> RunState:
        """Claim the run slot; raises :class:`JobBusyError` if already running."""
        with self._lock:
            current = self._runs[kind]
            if current.state == "running":
                raise JobBusyError(kind, current.snapshot())
            self._runs[kind] = RunState(
                kind=kind,
                run_id=uuid4().hex[:12],
                state="running",
                message=f"{kind} started",
                started_at=datetime.now(timezone.utc),
            )
            return self._runs[kind]

    def update(self, kind: str, message: Optional[str] = None, **counters: Any) -> None:
        with self._lock:
            run = self._runs[kind]
            if run.state != "running":
                return
            if message:
                run.message = message
            run.counters.update(counters)

    def finish(
        self, kind: str, state: str, message: str, error: Optional[str] = None
    ) -> None:
        with self._lock:
            run = self._runs[kind]
            run.state = state
            run.message = message
            run.finished_at = datetime.now(timezone.utc)
            run.error = error
