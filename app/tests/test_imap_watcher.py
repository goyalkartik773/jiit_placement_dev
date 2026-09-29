"""Auto-watcher behaviour: discovery, mark-seen-after-commit, poison valve.

Every test drives the real ``run_sync`` / ``run_processing`` against a
``FakeImapClient`` and the real (test-schema) database, so the ordering
guarantee the design rests on is asserted end to end:

    a message is only marked ``\\Seen`` once a row for it is committed -
    newly inserted *or* already present (self-healing).  A fetch/parse failure
    leaves it ``UNSEEN`` so the next cycle retries it.
"""

from __future__ import annotations

import dataclasses
import json
import threading

import pytest
from sqlalchemy import select

from app.config import load_settings
from app.gmail.imap_client import ImapError
from app.gmail.imap_watcher import InstanceLock, MailWatcher, WatcherHandle
from app.models import Email, EmailStatus
from app.tests.fake_imap import FakeImapClient, make_canned

GROUP = "jiitengg2027"
ID_A = "19b30d2a139faa80"
ID_B = "19b30d2a139faa81"
ID_C = "19b30d2a139faa82"


# ------------------------------------------------------------------ helpers


def _canned(hex_id: str, uid: int, **kwargs) -> object:
    return make_canned(
        hex_id,
        uid=uid,
        group=GROUP,
        subject=kwargs.pop("subject", f"Placement notice {uid}"),
        body=kwargs.pop("body", "Registration for placements is open."),
        **kwargs,
    )


def _watcher(fake, tmp_path, **kwargs):
    """Watcher wired to a fake client and isolated runtime files."""
    config = {
        "lock_path": tmp_path / "watcher.lock",
        "status_path": tmp_path / "status.json",
        "stop_path": tmp_path / "stop.flag",
        "stop_event": threading.Event(),
    }
    config.update(kwargs)
    return MailWatcher(client=fake, **config)


def _rows(session) -> list[Email]:
    return list(session.scalars(select(Email)).all())


def _ids(session) -> set[str]:
    return {row.gmail_message_id for row in _rows(session)}


# --------------------------------------------------------------- the cycle


def test_cycle_stores_marks_seen_and_processes(session, tmp_path):
    fake = FakeImapClient(
        [_canned(ID_A, 101), _canned(ID_B, 102)],
        groups={GROUP: [ID_A, ID_B]},
    )
    watcher = _watcher(fake, tmp_path)

    summary = watcher.run_once()

    assert summary["found_unseen"] == 2
    assert summary["new_messages"] == 2
    assert summary["duplicates_skipped"] == 0
    assert summary["failed_messages"] == 0
    assert summary["sync_skipped"] is False
    assert summary["marked_seen"] == 2
    assert summary["errors"] == []
    assert summary["processed"] == 1 + 1  # both PENDING rows attempted

    assert _ids(session) == {ID_A, ID_B}
    assert all(row.processing_status != EmailStatus.PENDING for row in _rows(session))

    # Discovery was newest-first; the batch is a single UID STORE.
    assert set(fake.marked_seen) == {ID_A, ID_B}
    assert len(fake.mark_seen_batches) == 1
    assert fake.messages[ID_A].seen and fake.messages[ID_B].seen
    assert fake.marked_unseen == []


def test_mark_seen_happens_only_for_committed_rows(session, tmp_path):
    """The one guarantee the design rests on: fail the fetch, keep UNSEEN."""
    good, bad = _canned(ID_A, 101), _canned(ID_B, 102)
    fake = FakeImapClient(
        [good, bad],
        groups={GROUP: [ID_A, ID_B]},
        fail_get_ids=frozenset({ID_B}),
    )
    watcher = _watcher(fake, tmp_path)

    summary = watcher.run_once()

    assert summary["found_unseen"] == 2
    assert summary["new_messages"] == 1
    assert summary["failed_messages"] == 1  # isolated, the good row still landed
    assert summary["marked_seen"] == 1

    assert _ids(session) == {ID_A}
    assert fake.marked_seen == [ID_A]  # ID_B was never fetched -> not in DB
    assert fake.messages[ID_B].seen is False  # ...so it stays UNSEEN and retries


def test_uncommitted_message_is_retried_on_the_next_cycle(session, tmp_path):
    fake = FakeImapClient(
        [_canned(ID_A, 101)],
        groups={GROUP: [ID_A]},
        fail_get_ids=frozenset({ID_A}),
    )
    first = _watcher(fake, tmp_path).run_once()
    assert first["new_messages"] == 0
    assert first["marked_seen"] == 0
    assert _ids(session) == set()

    # Failure cleared -> the very next cycle picks it up (still UNSEEN).
    fake.fail_get_ids.clear()
    second = _watcher(fake, tmp_path).run_once()
    assert second["found_unseen"] == 1
    assert second["new_messages"] == 1
    assert second["marked_seen"] == 1
    assert _ids(session) == {ID_A}


def test_rerun_is_idempotent_and_skips_the_sync(session, tmp_path):
    fake = FakeImapClient(
        [_canned(ID_A, 101), _canned(ID_B, 102)],
        groups={GROUP: [ID_A, ID_B]},
    )
    _watcher(fake, tmp_path).run_once()
    lists_after_first = fake.list_calls

    second = _watcher(fake, tmp_path).run_once()

    assert second["found_unseen"] == 0  # everything is \Seen now
    assert second["sync_skipped"] is True  # -> no listing round trips at all
    assert second["marked_seen"] == 0
    # Still exactly one discovery SEARCH per source group, and none of the
    # extra listings the sync pass would have added for the same groups.
    groups = load_settings().gmail.source_groups
    assert fake.list_calls - lists_after_first == len(groups)
    assert _ids(session) == {ID_A, ID_B}  # no duplicate rows


def test_no_unseen_mail_means_no_sync_and_no_rows(session, tmp_path):
    fake = FakeImapClient(
        [_canned(ID_A, 101, seen=True)],
        groups={GROUP: [ID_A]},
    )
    summary = _watcher(fake, tmp_path).run_once()

    assert summary["found_unseen"] == 0
    assert summary["sync_skipped"] is True
    assert summary["new_messages"] == 0
    assert _ids(session) == set()  # read-but-not-ingested mail is not fetched
    assert fake.marked_seen == []


def test_mark_seen_can_be_disabled_for_ingest_only_runs(session, tmp_path):
    fake = FakeImapClient([_canned(ID_A, 101)], groups={GROUP: [ID_A]})
    summary = _watcher(fake, tmp_path, mark_seen=False).run_once()

    assert summary["new_messages"] == 1
    assert summary["marked_seen"] == 0
    assert _ids(session) == {ID_A}
    assert fake.messages[ID_A].seen is False


def test_already_stored_unseen_mail_is_self_healed(session, tmp_path, insert_email):
    """Read-in-Gmail-but-never-ingested rows get flagged without re-inserting."""
    insert_email(gmail_message_id=ID_A, processing_status=EmailStatus.PROCESSED)

    fake = FakeImapClient([_canned(ID_A, 101)], groups={GROUP: [ID_A]})
    summary = _watcher(fake, tmp_path).run_once()

    assert summary["found_unseen"] == 1
    assert summary["new_messages"] == 0
    assert summary["duplicates_skipped"] == 1
    assert summary["marked_seen"] == 1  # already in DB -> safe to flag
    assert fake.messages[ID_A].seen is True
    assert len(_rows(session)) == 1  # still exactly one row


def test_discovery_is_newest_first_and_capped_at_page_size(tmp_path):
    messages = [_canned(ID_A, 101), _canned(ID_B, 102), _canned(ID_C, 103)]
    fake = FakeImapClient(messages, groups={GROUP: [ID_A, ID_B, ID_C]})

    watcher = _watcher(fake, tmp_path)
    assert watcher._discover() == [ID_C, ID_B, ID_A]  # highest uid first

    settings = load_settings()
    capped = dataclasses.replace(
        settings, gmail=dataclasses.replace(settings.gmail, page_size=2)
    )
    small = _watcher(fake, tmp_path, settings=capped)
    assert small._discover() == [ID_C, ID_B]  # newest two only


def test_discovery_failure_surfaces_as_a_typed_transport_error(tmp_path):
    fake = FakeImapClient(
        [_canned(ID_A, 101)],
        groups={GROUP: [ID_A]},
        fail_list_after=0,  # very first SEARCH blows up
    )
    with pytest.raises(ImapError) as excinfo:
        _watcher(fake, tmp_path).run_once()
    assert excinfo.value.status == 429  # run_forever backs off on exactly this


# ---------------------------------------------------------------- poison valve


def test_poison_sweep_fails_rows_past_the_budget_and_spares_llm_requeues(
    session, insert_email, tmp_path
):
    insert_email(
        gmail_message_id="gm-poison",
        processing_status=EmailStatus.PENDING,
        retry_count=5,
        error_message="boom",
    )
    insert_email(
        gmail_message_id="gm-requeue",
        processing_status=EmailStatus.PENDING,
        retry_count=99,
        error_message="LLM unavailable for this run - deterministic result kept",
    )
    watcher = _watcher(FakeImapClient([]), tmp_path, poison_retries=5)

    assert watcher._sweep_poison() == 1

    rows = {
        row.gmail_message_id: row
        for row in session.scalars(select(Email)).all()
    }
    assert rows["gm-poison"].processing_status == EmailStatus.FAILED
    assert "poison" in rows["gm-poison"].error_message
    # A provider outage is not a bad mail: its deterministic rows are already
    # written, so it keeps its automatic retry instead of being poisoned.
    assert rows["gm-requeue"].processing_status == EmailStatus.PENDING
    assert rows["gm-requeue"].error_message.startswith(
        "LLM unavailable for this run"
    )


def test_poison_sweep_can_be_turned_off(session, insert_email, tmp_path):
    insert_email(
        gmail_message_id="gm-poison",
        processing_status=EmailStatus.PENDING,
        retry_count=5,
        error_message="boom",
    )
    watcher = _watcher(FakeImapClient([]), tmp_path, poison_retries=0)

    assert watcher._sweep_poison() == 0
    row = session.scalar(select(Email).where(Email.gmail_message_id == "gm-poison"))
    assert row.processing_status == EmailStatus.PENDING
    assert row.error_message == "boom"


# --------------------------------------------------------------------- lock


def test_instance_lock_is_single_instance(tmp_path):
    path = tmp_path / "watcher.lock"
    first, second = InstanceLock(path), InstanceLock(path)

    assert first.acquire() is True
    assert first.held is True
    assert second.acquire() is False  # a second watcher must be refused
    assert second.held is False

    first.release()
    assert first.held is False
    assert second.acquire() is True  # released by hand -> usable again
    second.release()

    # A lock released once must not leave a stale file behind it.
    assert path.exists()
    third = InstanceLock(path)
    assert third.acquire() is True
    third.release()


def test_run_forever_refuses_a_second_instance(tmp_path):
    path = tmp_path / "watcher.lock"
    holder = InstanceLock(path)
    assert holder.acquire() is True

    watcher = _watcher(FakeImapClient([]), tmp_path, lock_path=path)
    assert watcher.run_forever() == 3
    status = MailWatcher.read_status(tmp_path / "status.json")
    assert status["state"] == "refused"
    assert "already holds" in status["error"]
    holder.release()


def test_run_forever_with_a_pre_set_stop_event_exits_cleanly(tmp_path):
    event = threading.Event()
    event.set()
    watcher = _watcher(FakeImapClient([]), tmp_path, stop_event=event)

    assert watcher.run_forever() == 0

    status = MailWatcher.read_status(tmp_path / "status.json")
    assert status["state"] == "stopped"
    assert status["error"] is None
    # The kernel lock was released in `finally`, so a new watcher can start.
    assert InstanceLock(tmp_path / "watcher.lock").acquire() is True


# ------------------------------------------------------------- status / stop


def test_status_file_is_written_atomically_and_readable(tmp_path):
    watcher = _watcher(FakeImapClient([]), tmp_path)
    watcher._write_status(state="running", error=None, last={"found_unseen": 3})

    status = MailWatcher.read_status(tmp_path / "status.json")
    assert status["state"] == "running"
    assert status["pid"] == watcher._status["pid"]
    assert status["last"] == {"found_unseen": 3}
    assert status["updated_at"]
    # Atomic write: no half-written temporary left behind.
    assert not (tmp_path / "status.json.tmp").exists()


def test_read_status_returns_none_for_a_missing_file(tmp_path):
    assert MailWatcher.read_status(tmp_path / "nope.json") is None


def test_stop_flag_file_shuts_the_wait_down_immediately(tmp_path):
    watcher = _watcher(FakeImapClient([]), tmp_path)
    tmp_path.joinpath("stop.flag").write_text("stop\n", encoding="utf-8")

    watcher._wait(30)  # would sleep 30s; must return straight away

    assert watcher.stop_event.is_set()
    assert not tmp_path.joinpath("stop.flag").exists()  # consumed, not left stale


def test_watcher_handle_merges_counters_without_a_job_runner():
    handle = WatcherHandle()
    handle.update(message="started")
    handle.update(total_fetched=10, new_messages=2, skipped=None)

    assert handle.message == "started"
    assert handle.counters["total_fetched"] == 10
    assert handle.counters["new_messages"] == 2
    assert "skipped" not in handle.counters  # None means "no news"


# --------------------------------------------------------------- end-to-end


def test_full_sequence_store_then_flag_then_process(session, tmp_path):
    """Ordering: rows exist *before* any flag is flipped, processing last."""
    fake = FakeImapClient(
        [_canned(ID_A, 101, seen=False)],
        groups={GROUP: [ID_A]},
    )
    watcher = _watcher(fake, tmp_path)
    summary = watcher.run_once()

    assert summary["new_messages"] == 1
    assert summary["marked_seen"] == 1
    assert summary["processed"] == 1

    row = session.scalar(select(Email).where(Email.gmail_message_id == ID_A))
    assert row is not None
    assert row.processing_status in (EmailStatus.PROCESSED, EmailStatus.FAILED)
    assert row.received_at is not None
    assert row.snippet
    assert fake.messages[ID_A].seen is True

    # Status file reflects the run for `watch_mail.py --status`.
    watcher._write_status(state="stopped", last=summary)
    status = MailWatcher.read_status(tmp_path / "status.json")
    assert status["last"]["marked_seen"] == summary["marked_seen"]
    assert json.dumps(status, default=str)  # serialisable end to end
