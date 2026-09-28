"""Mail auto-watcher CLI.

    python scripts/watch_mail.py                 # poll forever (default)
    python scripts/watch_mail.py --once          # exactly one cycle, then exit
    python scripts/watch_mail.py --status        # show the last cycle's summary
    python scripts/watch_mail.py --stop          # ask a running watcher to stop
    python scripts/watch_mail.py --interval 30   # override IMAP_POLL_SECONDS
    python scripts/watch_mail.py --idle          # enable IMAP IDLE (else poll)
    python scripts/watch_mail.py --no-mark-seen  # discovery only, no \\Seen

Exit codes: ``0`` clean, ``1`` cycle failed, ``3`` another instance is running,
``4`` IMAP authentication failed (fix ``IMAP_EMAIL`` / ``IMAP_APP_PASSWORD``).

Run it under any supervisor you like (Task Scheduler, systemd, ``nohup``);
the single-instance lock is kernel-enforced, so a double start is rejected
rather than silently racing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402  (path set above)
from app.gmail.imap_watcher import (  # noqa: E402
    STOP_PATH,
    STATUS_PATH,
    MailWatcher,
    install_signal_handlers,
)


def _print_status(path: Path) -> int:
    status = MailWatcher.read_status(path)
    if not status:
        print(f"no status file at {path} - the watcher has never run")
        return 1
    last = status.get("last")
    print(f"state   : {status.get('state')}")
    print(f"pid     : {status.get('pid')}")
    print(f"started : {status.get('started_at')}")
    print(f"updated : {status.get('updated_at')}")
    print(f"cycles  : {status.get('cycles')}")
    if status.get("error"):
        print(f"error   : {status.get('error')}")
    if last:
        print("--- last cycle ---")
        print(json.dumps(last, indent=2, default=str))
    return 0


def _request_stop(stop_path: Path) -> int:
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.write_text("stop\n", encoding="utf-8")
    status = MailWatcher.read_status()
    state = (status or {}).get("state")
    print(f"stop requested ({stop_path})")
    print(f"watcher state: {state or 'unknown'}")
    if state in (None, "stopped", "refused", "failed"):
        print("note: no running watcher reported itself - stale flag removed")
        stop_path.unlink(missing_ok=True)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Placement mail auto-watcher")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--status", action="store_true", help="print last status")
    parser.add_argument("--stop", action="store_true", help="request graceful stop")
    parser.add_argument("--interval", type=int, default=None, help="poll seconds")
    parser.add_argument("--idle", action="store_true", help="enable IMAP IDLE")
    parser.add_argument(
        "--no-mark-seen",
        action="store_true",
        help="never set \\Seen (ingest + process only)",
    )
    parser.add_argument(
        "--status-file", type=Path, default=STATUS_PATH, help="status JSON path"
    )
    parser.add_argument("--stop-file", type=Path, default=STOP_PATH, help="stop flag path")
    args = parser.parse_args(argv)

    if args.status:
        return _print_status(args.status_file)
    if args.stop:
        return _request_stop(args.stop_file)

    settings = load_settings()
    if not settings.gmail.imap_email or not settings.gmail.imap_app_password:
        print(
            "FATAL: IMAP_EMAIL / IMAP_APP_PASSWORD are not set. "
            "Add them to placement_pipeline/.env before starting the watcher.",
            file=sys.stderr,
        )
        return 4

    watcher = MailWatcher(
        settings=settings,
        status_path=args.status_file,
        stop_path=args.stop_file,
        mark_seen=False if args.no_mark_seen else None,
        poll_seconds=args.interval,
        idle_enabled=True if args.idle else None,
    )
    install_signal_handlers(watcher)

    if args.once:
        if not watcher._lock.acquire():  # noqa: SLF001 - CLI owns the lifecycle
            print("another watcher instance is already running", file=sys.stderr)
            return 3
        try:
            summary = watcher.run_once()
        except Exception as exc:  # noqa: BLE001 - report and exit non-zero
            import traceback

            traceback.print_exc()
            print(f"cycle failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            watcher._write_status(state="failed", error=str(exc))  # noqa: SLF001
            return 1
        finally:
            watcher._lock.release()  # noqa: SLF001
        print(json.dumps(summary, indent=2, default=str))
        watcher.cycles += 1
        watcher._write_status(state="stopped", last=summary)  # noqa: SLF001
        return 0

    return watcher.run_forever()


if __name__ == "__main__":
    sys.exit(main())
