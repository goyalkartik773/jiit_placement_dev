"""Automatic mail watcher: UNSEEN -> store -> mark ``\\Seen`` -> process.

One cycle (``run_once``)::

    1. discover   UID SEARCH UNSEEN X-GM-RAW "list:<group>"  (newest first,
                   capped at page_size) - metadata only, no flags touched
    2. sync       run_sync() inserts the new rows and confirms duplicates
    3. mark seen  ONLY for ids that are now in ``emails`` - i.e. the insert
                   committed (attachments included) *or* the row already
                   existed (self-healing).  Anything still missing stays
                   UNSEEN and is retried next cycle.
    4. poison     PENDING rows past ``IMAP_MAX_RETRIES`` -> FAILED, so one bad
                   mail cannot loop forever (the intentional LLM-unavailable
                   requeue is exempt - that is a provider outage, not a bad
                   mail, and its deterministic rows are already written).
    5. process    run_processing(): PENDING -> PROCESSED | FAILED
    6. summarize  found / new / duplicates_skipped / failed / marked_seen /
                  duration, written to the status file and the log.

Design decisions worth knowing
------------------------------
* ``emails.processing_status`` stays the source of truth for *ingestion*;
  IMAP ``\\Seen`` is only a mirror of "already in the DB".  ``BODY.PEEK[]``
  means discovery never flips a flag by accident.
* Sync is skipped when nothing was discovered UNSEEN: a brand-new message is
  by definition UNSEEN, so a cycle with zero UNSEEN cannot insert anything.
  This keeps an idle mailbox at ~5 commands per cycle instead of ~35.
* ``BODY.PEEK[]`` + batched ``UID STORE`` keep the ``min_interval_ms`` pacing
  off the critical path (one STORE for a whole page of ids, not one per mail).
* Single-instance: a kernel-level file lock (``msvcrt``/``fcntl``) that the OS
  releases if the process dies, so there is never a stale lock to clean up.
* IMAP auth failure is fatal - it stops the loop with the variable names only,
  never the app password.  Connection drops back off exponentially.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import func, or_, select, update

# Importing placement_pipeline.config loads the git-ignored .env file.
from placement_pipeline.config import PROJECT_ROOT  # noqa: F401  (side effect)

from app.config import Settings, load_settings
from app.db import get_session_factory
from app.gmail.imap_client import ImapAuthError, ImapClient, ImapError
from app.models import Email, EmailStatus
from app.schemas.processing import ProcessPendingRequest
from app.schemas.sync import SyncRequest
from app.services.processing_service import run_processing
from app.services.sync_service import group_query, run_sync
from app.utils.logging import log_event

log = logging.getLogger("app.gmail.watcher")

#: Runtime files live next to ``.env`` and are git-ignored.
LOCK_PATH = PROJECT_ROOT / ".imap_watcher.lock"
STATUS_PATH = PROJECT_ROOT / ".imap_watcher_status.json"
STOP_PATH = PROJECT_ROOT / ".imap_watcher.stop"

#: Matching ``process_one``'s intentional requeue message (we own this string).
_LLM_REQUEUE_PREFIX = "LLM unavailable for this run"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WatcherHandle:
    """``handle`` stub accepted by ``run_sync``/``run_processing``.

    Keeps the last message and merges counters so the cycle summary can report
    what each step actually did without a JobRunner/StatusStore.
    """

    def __init__(self) -> None:
        self.message = ""
        self.counters: dict = {}

    def update(self, message: Optional[str] = None, **counters) -> None:
        if message:
            self.message = message
        self.counters.update({k: v for k, v in counters.items() if v is not None})


class InstanceLock:
    """Single-instance guard.

    Locks byte 0 of a file with the platform's kernel lock, which the OS
    releases automatically when the fd is closed or the process dies - unlike
    a PID file, there is no stale-lock cleanup to get wrong.
    """

    def __init__(self, path: Path):
        self._path = Path(path)
        self._fd: Optional[int] = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> bool:
        if self.held:
            return True
        try:
            fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            return False
        try:
            if os.path.getsize(str(self._path)) == 0:
                os.write(fd, b"0000000000")
            os.lseek(fd, 0, os.SEEK_SET)
            if sys.platform == "win32":  # pragma: no cover - Windows only
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - POSIX only
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                os.close(fd)
            except OSError:
                pass
            return False
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except OSError:  # pragma: no cover - pid is informational only
            pass
        self._fd = fd
        return True

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            if sys.platform == "win32":  # pragma: no cover - Windows only
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - POSIX only
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass


class MailWatcher:
    """Polls the mailbox for UNSEEN group mail and drives the pipeline.

    All collaborators are injectable so the whole flow is unit-testable with a
    fake client and an in-process session factory (no network).
    """

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        client: Optional[ImapClient] = None,
        session_factory=None,
        stop_event: Optional[threading.Event] = None,
        lock_path: Optional[Path] = None,
        status_path: Optional[Path] = None,
        stop_path: Optional[Path] = None,
        mark_seen: Optional[bool] = None,
        poison_retries: Optional[int] = None,
        poll_seconds: Optional[int] = None,
        idle_enabled: Optional[bool] = None,
    ):
        self.settings = settings or load_settings()
        cfg = self.settings.gmail
        self._client = client
        self._owns_client = client is None
        #: Optional pre-built ``sessionmaker``; ``None`` means "ask the app
        #: for the current one" so a later ``configure()`` is still honoured.
        self._session_factory = session_factory
        self.stop_event = stop_event or threading.Event()
        self._lock = InstanceLock(Path(lock_path or LOCK_PATH))
        self._status_path = Path(status_path or STATUS_PATH)
        self._stop_path = Path(stop_path or STOP_PATH)
        self._mark_seen_enabled = (
            cfg.imap_mark_seen_after_store if mark_seen is None else mark_seen
        )
        self._poison_retries = cfg.imap_max_retries if poison_retries is None else int(poison_retries)
        self._poll = cfg.imap_poll_seconds if poll_seconds is None else max(1, int(poll_seconds))
        self._idle = cfg.imap_idle_enabled if idle_enabled is None else idle_enabled
        self.cycles = 0
        self._status: dict = {
            "pid": os.getpid(),
            "state": "idle",
            "started_at": None,
            "updated_at": None,
            "cycles": 0,
            "last": None,
            "error": None,
        }

    # -------------------------------------------------------------- plumbing

    @property
    def _factory(self):
        """Current ``sessionmaker`` (explicitly injected, else the app's)."""
        return self._session_factory or get_session_factory()

    @property
    def client(self) -> ImapClient:
        if self._client is None:
            self._client = ImapClient(
                self.settings.gmail, timeout=self.settings.gmail.request_timeout
            )
        return self._client

    def request_stop(self) -> None:
        self.stop_event.set()

    def _write_status(self, **fields) -> None:
        self._status.update(fields)
        self._status["updated_at"] = utcnow()
        self._status["cycles"] = self.cycles
        try:
            tmp = self._status_path.with_suffix(self._status_path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(self._status, indent=2, default=str), encoding="utf-8"
            )
            os.replace(tmp, self._status_path)
        except OSError as exc:  # pragma: no cover - status is best effort
            log.debug("cannot write status file: %s", exc)

    @staticmethod
    def read_status(status_path: Optional[Path] = None) -> Optional[dict]:
        path = Path(status_path or STATUS_PATH)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    # ----------------------------------------------------------------- cycle

    def _discover(self) -> list[str]:
        """UNSEEN ids across every source group, newest first, de-duplicated."""
        cfg = self.settings.gmail
        found: list[str] = []
        seen: set[str] = set()
        for group in cfg.source_groups:
            for message_id in self.client.iter_unseen_ids(
                group_query(group),
                page_size=cfg.page_size,
                max_results=cfg.page_size,
            ):
                if message_id in seen:
                    continue
                seen.add(message_id)
                found.append(message_id)
        return found

    def _in_db(self, message_ids: Iterable[str]) -> set[str]:
        """Ids with a committed row (newly inserted *or* pre-existing)."""
        present: set[str] = set()
        batch: list[str] = []
        session = self._factory()
        try:
            for message_id in message_ids:
                batch.append(message_id)
                if len(batch) >= 500:
                    present.update(self._lookup(session, batch))
                    batch = []
            if batch:
                present.update(self._lookup(session, batch))
        finally:
            session.close()
        return present

    @staticmethod
    def _lookup(session, ids: list[str]) -> set[str]:
        rows = session.execute(
            select(Email.gmail_message_id).where(Email.gmail_message_id.in_(ids))
        ).scalars()
        return {r for r in rows}

    def _mark_seen(self, message_ids: list[str]) -> int:
        """Batched ``+FLAGS.SILENT (\\Seen)`` - only for committed rows."""
        if not message_ids or not self._mark_seen_enabled:
            return 0
        try:
            return self.client.mark_seen_many(message_ids)
        except ImapError as exc:
            log_event(
                log,
                "watcher.mark_seen_failed",
                level=logging.WARNING,
                error=str(exc)[:300],
            )
            return 0

    def _sweep_poison(self) -> int:
        """``PENDING`` past the retry budget -> ``FAILED`` (fail forward)."""
        if self._poison_retries <= 0:
            return 0
        session = self._factory()
        try:
            result = session.execute(
                update(Email)
                .where(
                    Email.processing_status == EmailStatus.PENDING,
                    func.coalesce(Email.retry_count, 0) >= self._poison_retries,
                    or_(
                        Email.error_message.is_(None),
                        Email.error_message.not_like(f"{_LLM_REQUEUE_PREFIX}%"),
                    ),
                )
                .values(
                    processing_status=EmailStatus.FAILED,
                    error_message=(
                        f"watcher: gave up after {self._poison_retries} retries "
                        "(poison message)"
                    )[:2000],
                )
            )
            session.commit()
            count = int(result.rowcount or 0)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        if count:
            log_event(
                log,
                "watcher.poison_failed",
                level=logging.WARNING,
                rows=count,
                retries=self._poison_retries,
            )
        return count

    def run_once(self) -> dict:
        """One full cycle.  Raises only for transport-level failures."""
        started = time.perf_counter()
        summary: dict = {
            "at": utcnow(),
            "found_unseen": 0,
            "new_messages": 0,
            "duplicates_skipped": 0,
            "failed_messages": 0,
            "sync_skipped": False,
            "marked_seen": 0,
            "poison_failed": 0,
            "processed": 0,
            "process_failed": 0,
            "requeued_for_llm_retry": 0,
            "errors": [],
            "seconds": 0.0,
        }

        # 1. discover -----------------------------------------------------
        discovered = self._discover()
        summary["found_unseen"] = len(discovered)

        handle = WatcherHandle()

        # 2. store --------------------------------------------------------
        # A brand-new message is UNSEEN by definition, so a cycle that found
        # nothing UNSEEN cannot insert anything - skip the ~35-command sync.
        if discovered:
            session = self._factory()
            try:
                stats = run_sync(
                    client=self.client,
                    session=session,
                    handle=handle,
                    payload=SyncRequest(),
                    settings=self.settings,
                )
            finally:
                session.close()
            summary["new_messages"] = stats.get("new_messages", 0)
            summary["duplicates_skipped"] = stats.get("duplicates_skipped", 0)
            summary["failed_messages"] = stats.get("failed_messages", 0)
            summary["errors"].extend(stats.get("errors") or [])
        else:
            summary["sync_skipped"] = True

        # 3. mark seen ----------------------------------------------------
        # Only ids with a committed row: insert + attachments done, or the row
        # was already there (self-healing).  Parse/insert failures stay UNSEEN
        # and are retried next cycle.
        if discovered:
            committed = sorted(self._in_db(discovered))
            summary["marked_seen"] = self._mark_seen(committed)

        # 4. poison valve -------------------------------------------------
        summary["poison_failed"] = self._sweep_poison()

        # 5. process ------------------------------------------------------
        pstats = run_processing(
            session_factory=self._factory,
            handle=handle,
            payload=ProcessPendingRequest(),
            settings=self.settings,
        )
        summary["processed"] = pstats.get("processed", 0)
        summary["process_failed"] = pstats.get("failed", 0)
        summary["requeued_for_llm_retry"] = pstats.get("requeued_for_llm_retry", 0)
        summary["by_category"] = pstats.get("by_category", {})

        summary["seconds"] = round(time.perf_counter() - started, 3)
        return summary

    # ------------------------------------------------------------------ loop

    def _wait(self, seconds: float) -> None:
        """Sleep until the next cycle, waking early for stop / IDLE / new mail."""
        deadline = time.monotonic() + max(0.0, seconds)
        while not self.stop_event.is_set():
            if self._stop_path.exists():
                self._stop_path.unlink(missing_ok=True)
                self.stop_event.set()
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if self._idle:
                # Optional IMAP IDLE: returns True when a wait completed (new
                # mail or the interval elapsed) and False when the server does
                # not offer IDLE - in that case drop to polling for the rest
                # of the run so we never spin.
                try:
                    if self.client.idle_wait(remaining):
                        return
                except ImapError as exc:
                    log_event(
                        log,
                        "watcher.idle_fallback",
                        level=logging.WARNING,
                        error=str(exc)[:200],
                    )
                log_event(log, "watcher.idle_disabled", level=logging.INFO)
                self._idle = False
                continue
            self.stop_event.wait(min(1.0, deadline - time.monotonic()))

    def run_forever(self) -> int:
        """Poll until stopped.  Returns a process exit code."""
        if not self._lock.acquire():
            message = (
                f"another watcher already holds {self._lock.path} - refusing "
                "to run two instances"
            )
            log_event(log, "watcher.already_running", level=logging.WARNING)
            self._write_status(state="refused", error=message)
            print(message, file=sys.stderr)
            return 3

        failures = 0
        self._status["started_at"] = utcnow()
        self._write_status(state="running", error=None)
        log_event(log, "watcher.started", poll_seconds=self._poll, pid=os.getpid())
        try:
            while not self.stop_event.is_set():
                if self._stop_path.exists():
                    self._stop_path.unlink(missing_ok=True)
                    break
                try:
                    summary = self.run_once()
                except ImapAuthError as exc:
                    # Credentials are wrong / IMAP is off: retrying cannot help.
                    self.cycles += 1
                    self._write_status(state="failed", error=str(exc))
                    log_event(
                        log,
                        "watcher.fatal_auth",
                        level=logging.ERROR,
                        detail=str(exc),
                    )
                    print(f"FATAL: {exc}", file=sys.stderr)
                    return 4
                except (ImapError, OSError) as exc:
                    failures += 1
                    backoff = min(
                        self.settings.gmail.imap_backoff_base_seconds
                        * (2 ** (failures - 1)),
                        self.settings.gmail.imap_backoff_cap_seconds,
                    )
                    self.cycles += 1
                    self._write_status(state="backoff", error=str(exc))
                    log_event(
                        log,
                        "watcher.cycle_failed",
                        level=logging.WARNING,
                        attempt=failures,
                        backoff_seconds=backoff,
                        detail=str(exc)[:300],
                    )
                    self._wait(backoff)
                    continue

                failures = 0
                self.cycles += 1
                self._write_status(state="running", error=None, last=summary)
                log_event(
                    log,
                    "watcher.cycle",
                    cycle=self.cycles,
                    found=summary["found_unseen"],
                    new=summary["new_messages"],
                    duplicates=summary["duplicates_skipped"],
                    failed=summary["failed_messages"],
                    marked_seen=summary["marked_seen"],
                    processed=summary["processed"],
                    process_failed=summary["process_failed"],
                    poison_failed=summary["poison_failed"],
                    seconds=summary["seconds"],
                )
                self._wait(self._poll)
            self._write_status(state="stopped", error=None)
            log_event(log, "watcher.stopped", cycles=self.cycles)
            return 0
        except Exception as exc:  # unexpected (DB/parse bug) - keep the daemon
            self.cycles += 1
            self._write_status(state="failed", error=str(exc))
            log_event(
                log,
                "watcher.cycle_error",
                level=logging.ERROR,
                detail=str(exc)[:300],
                error=type(exc).__name__,
            )
            raise
        finally:
            self._lock.release()
            self._close_client()

    def _close_client(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception:  # pragma: no cover
                pass
            self._client = None


# --------------------------------------------------------------------- main


def install_signal_handlers(watcher: MailWatcher) -> None:
    """SIGINT/SIGTERM -> graceful shutdown (locks released, status written)."""

    def _handler(signum, frame):  # pragma: no cover - signal plumbing
        watcher.request_stop()

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):  # pragma: no cover - non-main thread
            pass


__all__ = [
    "InstanceLock",
    "LOCK_PATH",
    "MailWatcher",
    "STOP_PATH",
    "STATUS_PATH",
    "WatcherHandle",
    "install_signal_handlers",
]
