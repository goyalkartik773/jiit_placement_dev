# Mail transport migration: Gmail REST + OAuth → IMAP + app password

Status: **done** (phases A–D). Decision record, evidence, and the things that
were deliberately left alone.

---

## 1. Scope — Option A: Python only

The backend (`placement_pipeline/app/`) was moved to `imaplib` + a Gmail app
password. The .NET admin app was **not touched**, per Option A.

### Changed (this migration)

| phase | files |
|---|---|
| A | **new** `app/gmail/imap_client.py`, **new** `app/gmail/imap_parse.py`; `app/gmail/mime.py` gained a payload-type dispatch; `app/gmail/__init__.py` re-exports; **deleted** `app/gmail/auth.py`, `app/gmail/client.py` |
| B | `app/config.py` (`GmailConfig` now IMAP fields), `app/container.py`, `app/api/gmail.py` (error types), `app/services/sync_service.py` (4 lines), `.env`, `.env.example`, `.gitignore` |
| C | **new** `app/gmail/imap_watcher.py`, **new** `scripts/watch_mail.py` |
| D | **new** `app/tests/fake_imap.py`, `app/tests/test_imap_parse.py` (35), `app/tests/test_imap_watcher.py` (19); `README.md`; this note |

### Frozen — unchanged on purpose

* **`emails` / `email_attachments` schema.** No column added, renamed, or
  retyped. Zero DB migration.
* Derived tables, the deterministic parser, the taxonomy, and the hybrid LLM
  router.
* `run_sync` / `run_processing` stats contracts (`sync_service.py` only had
  its import, two type hints and one `except` rewritten — no logic).
* The `.NET → job_placed_students → frontend` read path and notifications.
* `processing_service.process_one`'s `PENDING → PROCESSING → PROCESSED | FAILED`
  state machine.
* The sync seam itself: `iter_message_ids(query, *, page_size, max_results)`,
  `get_message(id)`, `get_attachment(id, aid)`.

### .NET side (Option A)

No file under `JIITPlacement/` was created, edited, or deleted. It still runs
its own OAuth path:

* `Services/GmailService.cs` → `GmailSyncService`, `GoogleCredential.FromAccessToken(...)`,
  `TokenFilePath ?? "token.json"` (`C:\Users\HP\AppData\Local\JIITPlacement\token.json`)
* `JIITPlacement/credentials.json` — still present, still git-ignored there

Both of those files were **kept**, because they belong to .NET. The Python
backend no longer reads either (the `_default_credentials_path` /
`_default_token_path` helpers and `GMAIL_CREDENTIALS_PATH` / `GMAIL_TOKEN_PATH` /
`GMAIL_SCOPES` were removed).

**Consequence — two independent mail paths.** The .NET mirror
(`gmailmessages`, 583 rows) and the Python `emails` table (598 rows) are now
fed by different transports. They cannot double-insert, because both write the
same `gmail_message_id` and `emails.gmail_message_id` has a unique index.

> Follow-up (needs a decision, not taken here): retire the .NET OAuth mirror
> too, or formally document it as read-only legacy. That is a .NET change and
> was out of scope for Option A.

---

## 2. Identity map — why there is zero migration

Live-proven by `scripts/probe_imap_identity.py` (**6/6 round-trip, exit 0**):

| field | source | note |
|---|---|---|
| `emails.gmail_message_id` | `X-GM-MSGID` | **decimal on the wire → `format(int(v), 'x')`**. Gmail REST's `id` *is* that hex value, so the unique index keeps deduping on the same key. |
| `emails.thread_id` | `X-GM-THRID` | decimal → hex, same rule |
| `emails.received_at` | `INTERNALDATE` | aware UTC from `26-Sep-2026 06:20:56 +0000` (locale-safe hand parser) |
| `emails.label_ids` | `X-GM-LABELS` + `FLAGS` | `\Important`→`IMPORTANT`, …, and `UNREAD` derived from the *absence* of `\Seen` — so values match the REST-spelled rows already stored |
| discovery query | `SEARCH X-GM-RAW "<group_query()>"` | byte-identical query string to the REST path (`list:jiitengg2027.googlegroups.com` → 509) |
| `emails.snippet` | first 200 chars of the text body | `SNIPPET_CHARS = 200` |
| attachment id | `part:{sha1(filename\|size\|content-id)}` | deterministic, no counter/timestamp; bytes held inline so `get_attachment` is a lookup, not a fetch |

`received_at` is `INTERNALDATE` first (per spec). The body `Date:`/`From:`
regexes that Google Groups puts inside forwarded messages are applied
**defensively only** — they fire when the corresponding *header* is missing.
A normal message therefore gets byte-identical `sender` / `cluster_key` /
`received_at` to the Gmail-API parse, which is what keeps the existing
dedup and the 712 double-count analysis untouched.

### Non-Gmail IMAP (documented caveat)

`X-GM-EXT-1` is a Gmail extension. Without it:

* no `X-GM-MSGID` → ids fall back to `imap:{uidvalidity}:{uid}`
* FETCH items drop `X-GM-MSGID` / `X-GM-THRID` / `X-GM-LABELS` (asking for
  them would be a `BAD`)
* `list:<group>` is translated to `HEADER List-Id <group>`; any richer Gmail
  query is **rejected loudly** rather than silently listing the whole mailbox

---

## 3. The auto-watcher

`python scripts/watch_mail.py` — one cycle:

1. **discover** `UID SEARCH UNSEEN X-GM-RAW "list:<group>"`, newest first,
   capped at `page_size`, metadata FETCH only → discovery never flips a flag
2. **store** `run_sync()` inserts new rows and confirms duplicates
3. **mark seen** batched `UID STORE … +FLAGS.SILENT (\Seen)` — and **only** for
   ids that now have a committed row (newly inserted with attachments stored,
   *or* already present → self-healing). Fetch/parse/insert failures stay
   `UNSEEN` and retry next cycle.
4. **poison valve** `PENDING AND retry_count >= IMAP_MAX_RETRIES` → `FAILED`
5. **process** `run_processing()`: `PENDING → PROCESSED | FAILED`
6. **summarize** found / new / duplicates_skipped / failed / marked_seen /
   duration → log + `.imap_watcher_status.json`

Sync is **skipped when nothing was discovered UNSEEN** (step 2 only runs if
step 1 found something). A brand-new message is UNSEEN by definition, so a
cycle with zero UNSEEN cannot insert anything — an idle mailbox costs ~5
commands per cycle instead of ~35.

Reliability: single-instance kernel lock (`msvcrt`/`fcntl`, auto-released if
the process dies → exit 3), exponential reconnect backoff
(`IMAP_BACKOFF_BASE`…`IMAP_BACKOFF_CAP`), **fatal on auth error** (exit 4,
variable names only), SIGINT/SIGTERM graceful shutdown, `--stop` flag file,
optional `IDLE` (`IMAP_IDLE_ENABLED`, default **off**) run on a throwaway
connection with polling as the fallback.

`IMAP_MARK_SEEN_AFTER_STORE` (default `true`) turns step 3 off; `--no-mark-seen`
does the same from the CLI.

---

## 4. Evidence

All commands run from `placement_pipeline/` unless noted.

| check | result |
|---|---|
| `python -m pytest -q` | **304 passed**, 46 warnings (was 250; +35 parse, +19 watcher) |
| `python scripts/run_backend_validation.py` | **33/33 samples pass**, idempotency `identical derived rows: True`, `RESULT: PASS`, exit 0 |
| `python scripts/probe_imap_identity.py` | **GATE PASS 6/6**, exit 0 |
| `python scripts/probe_imap.py` | login OK; `X-GM-EXT-1` + `IDLE` offered; `list:jiitengg2027…` → 509, `list:jiitintgt2027…` → 196; `GATE: PASS - 5/5` |
| `npx tsc --noEmit` (frontend) | exit 0 |
| `npx vite build` (frontend) | `✓ 186 modules transformed … built in 18.96s` |

### Live identity proof — `POST /api/gmail/sync`

```
HTTP 200
Sync completed: 2 new, 1146 duplicates skipped, 0 failed
  total_fetched 1148 | new_messages 2 | duplicates_skipped 1146 | failed 0 | 47.4s
  jiitengg2027     listed 509  new 1  dup 508  failed 0
  jiitintgt2027    listed 196  new 0  dup 196  failed 0
  jiitmtech2027    listed 170  new 0  dup 170  failed 0
  jiitmca2027      listed 142  new 0  dup 142  failed 0
  jaypeeengg2027   listed 131  new 1  dup 130  failed 0
```

DB before/after:

```
PRE : count 596 | distinct 596 | pending 0 | failed 0
POST: count 598 | distinct 598 | pending 2 | failed 0
duplicate id groups      = 0
pre-existing ids lost    = 0   (all 596 still present, exactly once)
new rows added by IMAP   = 2   (1a0e6843fb2630d7, 1a0e7806d3a3be8d)
```

`duplicates_skipped` is 1146 rather than 596 because the same cross-posted
message is listed by more than one group and each listing counts it — exactly
what the Gmail-API path did too. The invariant that matters holds:
**zero duplicates, zero lost rows.**

The 2 new messages parsed correctly from IMAP:

```
1a0e6843fb2630d7 | Reminder : LTM 2027 Batch Mass… | vinod.jptnp@gmail.com  | 2026-09-28 11:07:01+05:30 | PENDING | snippet t | att t | ["UNREAD"] | jiitengg2027
1a0e7806d3a3be8d | ZS Associates-Hiring For FT…    | anurag.jptnp@gmail.com | 2026-09-28 15:42:28+05:30 | PENDING | snippet t | att f | []          | jaypeeengg2027
```

`11:07:01+05:30` is the probe's `INTERNALDATE "28-Sep-2026 05:37:01 +0000"`
converted — i.e. arrival time, not body time. `label_ids` came back in REST
spelling (`["UNREAD"]`, `[]` for the already-read one).

`POST /api/gmail/process-pending` then reported `Processed 2/2 emails`
(1 `REGISTRATION`, 1 `FINAL_SELECTION`, `1` offer, `13` offer_students,
`13` student_placement_events, 0 failed).

### Watcher self-healing — `python scripts/watch_mail.py --once`

```json
{
  "found_unseen": 96, "new_messages": 0, "duplicates_skipped": 1148,
  "failed_messages": 0, "sync_skipped": false, "marked_seen": 96,
  "poison_failed": 0, "processed": 0, "process_failed": 0,
  "requeued_for_llm_retry": 0, "errors": [], "seconds": 52.401
}
```

96 messages were UNSEEN in Gmail but already stored (they came in over the old
Gmail-API path, which never touched `\Seen`) → all 96 flagged, none inserted.

Re-running `scripts/probe_imap.py` after the cycle:

```
[ -- ] UNSEEN in whole INBOX:                        14529
[ -- ] UNSEEN in jiitengg2027@googlegroups.com:          0   (was 86)
GATE: PASS - 5/5 sampled X-GM-MSGID values already exist in emails.gmail_message_id
```

Group UNSEEN drained to 0 while the 14 529 non-group messages were left
completely alone — the query is scoped by `X-GM-RAW "list:…"`.

---

## 5. Known deltas and risks

1. **Corpus 596 → 598.** Two genuinely new group messages arrived and were
   ingested (1 `FINAL_SELECTION`, 1 `REGISTRATION`). `reports/backend_validation.md`
   now totals **598** with idempotency still `identical`.
2. **Watcher vs. manual API runs.** The watcher lives in its own process, so
   its `run_processing()` is outside the in-process `JobRunner` guard. Firing
   `POST /api/gmail/process-pending` *while the watcher is cycling* can
   double-process an email. A `pg_try_advisory_lock` inside `run_processing`
   would close that gap — it was **not** added, because it means editing a
   frozen-adjacent function; needs a go-ahead.
3. **Poison valve vs. LLM outage.** The sweep exempts rows whose
   `error_message` starts with `LLM unavailable for this run`. That requeue is
   a provider outage, not a bad message, and its deterministic rows are already
   written — poisoning it would give up after `IMAP_MAX_RETRIES` (default 5)
   cycles. Hard parse/extract failures already go terminal `FAILED` inside
   `process_one`, so the sweep is the backstop for anything else. Raise/lower
   `IMAP_MAX_RETRIES`, or set `0` to disable the valve.
4. **Idle-cycle cost.** A cycle that finds UNSEEN mail still runs a full sync
   (~35 paced commands ≈ 47 s at `GMAIL_MIN_INTERVAL_MS=1100`). With
   `IMAP_POLL_SECONDS=60` the effective period is ~107 s. The no-UNSEEN skip
   keeps an idle mailbox at ~5 commands.
5. **`IDLE` is off by default** and uses a throwaway connection (imaplib has
   no IDLE support, so the tagged exchange is driven over the raw socket).
   Any problem drops to polling for the rest of the run.
6. **App password is a real credential.** It lives only in the git-ignored
   `.env`; `ImapClient._redact()` strips it from every log line and exception.
   Rotating it stops the watcher with exit 4 and a variable-name-only message.
7. **Runtime files**: `.imap_watcher.lock`, `.imap_watcher_status.json`,
   `.imap_watcher.stop` in `placement_pipeline/` — all git-ignored.

## 6. Running it

```powershell
# one cycle, prints the summary, then exits
python scripts/watch_mail.py --once

# daemon (Task Scheduler / nssm / nohup), stop it cleanly
python scripts/watch_mail.py --interval 60
python scripts/watch_mail.py --status
python scripts/watch_mail.py --stop
```

Exit codes: `0` clean · `1` cycle failed · `3` another instance is already
running · `4` IMAP authentication failed.
