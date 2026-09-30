# JIITPlacement — Backend

ASP.NET Core (.NET 10) + PostgreSQL service for the JIIT placement job-sync system.

- **Public job API** — consumed by the React frontend (`GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{jobId}/documents/{documentId}`).
- **Admin API** — JWT login + the sync and delete-all workflows (see below).
- **Sync source** — SuperSet (`SuperSet` config section). Documents are downloaded to
  `FileStorage:RootPath` (`D:\JIITPlacementFiles`) during sync — unchanged behavior.
- **Gmail subsystem** — separate ingestion pipeline; admin endpoints now require a valid admin JWT,
  only the two OAuth browser endpoints stay anonymous.

## Running

```bash
dotnet run          # http://localhost:5104 (Development profile, user-secrets supported)
```

Configuration lives in `appsettings.json` (git-ignored — never commit it) with committed placeholders in
`appsettings.example.json`. Environment variables override file config (`Admin__Password`,
`Jwt__Secret`, `SuperSet__Password`, `ConnectionStrings__DefaultConnection`, `FileStorage__RootPath`, …).

**JWT**: the API refuses to start when `Jwt:Secret` is missing or shorter than 32 bytes. Copy the `Jwt`
section from `appsettings.example.json` into your git-ignored `appsettings.json` (or user-secrets) and
put a random ≥32-byte base64 value in `Secret` (e.g. from `Secret`/`openssl rand -base64 32`).

Database schema/functions: `migrations.sql` (base) + `SQL/*.sql` (gmail, placements, local documents,
`migration_admin.sql` = job-count function, `migration_delete_jobs.sql` = delete-all-jobs function,
`migration_job_placed_students.sql` = job ↔ offered-student mapping + the dashboard reads,
`cleanup_obsolete.sql` = audited cleanup).

## Admin API contracts

All admin endpoints except `login` require `Authorization: Bearer <jwt>` and answer challenges with
`401 {"success":false,"message":"Unauthorized"}`. Responses never contain passwords; the password is
compared in constant time.

### Console scripts

The admin data operations behave like console scripts: the POST/DELETE call **starts** (or runs) the
script and the console output is produced **server-side**, so the UI only renders what the API
returns — no client-side line synthesis, no invented numbers.

| Script key | Start | Status / result |
| --- | --- | --- |
| `jobs_sync` | `POST /api/admin/jobs/sync` | `GET /api/admin/jobs/sync/status` |
| `gmail_sync` | `POST /api/admin/gmail/sync` | `GET /api/admin/gmail/sync/status` |
| `offer_sync` | `POST /api/admin/jobs/sync-offer-students` | `GET /api/admin/jobs/sync-offer-students/status` |
| `delete_jobs` | `DELETE /api/admin/jobs` | response body |
| `delete_gmail` | `DELETE /api/admin/gmail` | response body |
| `delete_mappings` | `DELETE /api/admin/jobs/placed-students` | response body |
| `login` / `logout` | `POST /api/admin/login` / `logout` | `GET /api/admin/activity` |

One script at a time: all of them share a single slot, so a second start while one is running
answers `409` with `busyScript`. Every run (including logins and deletes) is persisted to
`admin_script_runs` with its counters and console output — see `GET /api/admin/activity` below.

### `POST /api/admin/login`

```json
{ "username": "admin@jiit", "password": "<Admin:Password>" }
```

The development credentials come from `appsettings.json` (git-ignored) or the `Admin__Username` /
`Admin__Password` environment variables — they are never committed to source control.

```json
{ "success": true, "message": "Login successful", "token": "...", "username": "admin@jiit",
  "expiresAt": "2026-09-28T02:30:11.4120355+00:00" }
```

Invalid → `401 { "success": false, "message": "Invalid credentials" }`.
Token: signed JWT (HMAC-SHA256, `Jwt:Secret`) carrying `username`, `role` and a `jti` session id;
expires after `Admin:TokenExpirationHours`, default 8h.

Every login (accepted **and** rejected) and every logout is written to the `admin_script_runs`
history table — that is where `GET /api/admin/overview` reads `session.lastLogin` / `lastLogout`
from. A rejected attempt stores only the first 100 characters of the submitted username and never
the password.

### `POST /api/admin/logout`

```json
{ "success": true, "message": "Logged out successfully" }
```

The token's `jti` is revoked immediately — subsequent calls with that token get `401` (revocation
entries expire together with the token they belong to).

### `GET /api/admin/jobs/count`

```json
{ "success": true, "totalJobs": 123 }
```

Live `COUNT(*)` from the `jobs` table via `fn_api_count_jobs_v001` (single source of truth; no
duplicate counting tables).

### `POST /api/admin/jobs/sync`

```json
{ "success": true, "message": "Job synchronization started", "script": "jobs_sync",
  "syncId": "...", "status": "started" }
```

Runs the **existing** sync logic (`SuperSetSyncService.SyncAllAsync`, single SuperSet login, jobs +
notices) in the background — the HTTP request returns immediately. **All admin scripts share one
slot** (Superset sync, mailbox sync, job↔student sync and both deletes), so concurrent starts →
`409`:

```json
{ "success": false, "message": "Mailbox sync is already running",
  "busyScript": "gmail_sync", "syncId": "...", "status": "running" }
```

`busyScript` names the operation that holds the slot
(`jobs_sync | gmail_sync | offer_sync | delete_jobs | delete_gmail | delete_mappings`); the
`message` is the human label of the same operation.

### `GET /api/admin/jobs/sync/status`

Before any run: `{ "success": true, "script": "jobs_sync", "status": "idle" }`.

While running / when finished (`status`: `idle | running | completed | failed`) — all fields with
unknown values are **omitted, never fabricated**; `progress` only appears once the source total is
known; `output` is the console the run printed (also persisted for replay):

```json
{
  "success": true,
  "script": "jobs_sync",
  "status": "completed",
  "syncId": "...",
  "message": "Sync completed in 00:03:41",
  "totalJobsBeforeSync": 0,
  "totalJobsAfterSync": 87,
  "jobsTotal": 87,
  "jobsProcessed": 87,
  "newJobs": 87,
  "documentsDownloaded": 61,
  "documentsFailed": 6,
  "failedJobs": 0,
  "progress": 100,
  "startedAt": "...",
  "finishedAt": "...",
  "error": null,
  "output": [
    { "time": "18:01:02", "tone": "cmd", "text": "$ POST /api/admin/jobs/sync" },
    { "time": "18:01:02", "tone": "info", "text": "→ 87 jobs in the database before sync" },
    { "time": "18:01:44", "tone": "info", "text": "  [44/87] 12 new · 31 documents" },
    { "time": "18:04:43", "tone": "success", "text": "✓ 87 → 87 jobs in the database" }
  ]
}
```

Failure path sets `status: "failed"` with a populated `error` and is logged — exceptions are never
silently swallowed.

### `DELETE /api/admin/jobs`

Deletes **every job record** in one transaction (`fn_api_delete_all_jobs_v001`: `jobs` plus the seven
job child tables — notices and Gmail data are never touched) and then removes the documents those
records owned from `FileStorage:RootPath`, including orphaned leftovers under `Jobs\`; the empty
folder tree is dropped too (recreated by the next sync). While any other script runs → `409` with
`busyScript` (`"Superset job sync is already running"` / `"Mailbox delete is already running"` …).
A successful deletion is also written to the history (`script: "delete_jobs"`).

```json
{
  "success": true,
  "message": "Deleted 96 jobs and 84 documents",
  "jobsDeleted": 96,
  "documentRowsDeleted": 82,
  "filesDeleted": 84,
  "filesMissing": 0,
  "filesFailed": 0,
  "durationMs": 179,
  "phases": [
    { "phase": "delete_records", "durationMs": 63 },
    { "phase": "delete_files", "durationMs": 115 }
  ]
}
```

`phases` are real wall-clock measurements (the admin UI prints them as console output);
`filesMissing` counts referenced documents already absent on disk, `filesFailed` counts real
failures (a non-empty value is logged per path). DB failure → `500 { "success": false, "message": ... }`
and nothing is partially reported as deleted (the record deletion is transactional).

### `POST /api/admin/jobs/sync-offer-students` (console script)

Admin-triggered matching of the offer students parsed from congratulation emails onto the jobs that
already exist in the system (`fn_api_sync_offer_students_v1`). The endpoint now behaves like every
other admin script: it **starts** the run and returns immediately; the stats, the console output and
the delta come from the status endpoint below.

```json
{ "success": true, "message": "Job to student sync started", "script": "offer_sync", "status": "started" }
```

While another script holds the slot → `409 { "success": false, "message": "... is already running",
"script": "offer_sync", "busyScript": "..." }`.

Matching rules (unchanged):

* a student is mapped **only** when his/her company exists in the `jobs` table — companies that were
  never listed are counted in `companiesSkipped` and ignored (no job is created, no match is guessed);
* the comparison uses one shared normaliser (trim, collapse spaces, lowercase, drop a single trailing
  parenthetical), so `Josh Technology Group (JTG)` matches `Josh Technology Group`;
* a job row is a company listing, so a student maps to every job row of that company;
* idempotent: `UNIQUE (job_id, student_roll_no)` + `ON CONFLICT DO NOTHING` — a second run inserts
  nothing and reports every candidate under `duplicatesSkipped`.

### `GET /api/admin/jobs/sync-offer-students/status`

Same envelope as the mailbox status (`idle | running | completed | failed` + `runId`, `startedAt`,
`finishedAt`, `durationMs`, `progress`, `output`, `error`). `counters` is built from three real
queries — the source snapshot before the run, the sync function's own result, and a delta computed
from `placed_at >= startedAt`:

```jsonc
{
  "success": true, "script": "offer_sync", "runId": "...", "status": "completed",
  "message": "Job to student sync completed — no new mappings (906 total)",
  "durationMs": 203,
  "counters": {
    "source": { "mappingsBefore": 906, "studentsBefore": 895, "jobsBefore": 96, "jobs": 96 },
    "stats": { "jobsTotal": 96, "jobsMatched": 44, "jobsWithoutPlacements": 52,
               "studentsConsidered": 504, "studentsMapped": 417,
               "mappingsInserted": 0, "duplicatesSkipped": 906,
               "companiesMatched": 33, "companiesSkipped": 21,
               "totalMappings": 906, "lastRunAt": "..." },
    "delta": { "mappingsInserted": 0, "studentsAdded": 0, "companiesTouched": 0,
               "changes": [ { "company": "Zomato", "students": 3 } ] },
    "integrity": { "orphanMappings": 0, "duplicateMappings": 0, "orphanOffers": 0,
                   "blankRolls": 0, "totalMappings": 906 }
  },
  "output": [ { "time": "18:00:41", "tone": "cmd", "text": "$ POST /api/admin/jobs/sync-offer-students" },
              { "time": "18:00:41", "tone": "info", "text": "→ source tables — 895 offer students · 94 offers · 596 emails · 96 job listings" },
              { "time": "18:00:41", "tone": "success", "text": "✓ 0 mappings inserted · 417 students mapped · 44/96 jobs matched · 33 companies · 21 skipped" },
              { "time": "18:00:41", "tone": "info", "text": "→ changes — no new mappings (every offer student was already mapped; re-run is idempotent)" },
              { "time": "18:00:41", "tone": "success", "text": "✓ integrity — 906 rows · 0 orphan · 0 duplicate (job_id, roll) · 0 blank roll" } ]
}
```

`source.*` is the snapshot read **before** the sync writes (the same three values sit at the
root of `counters` while the run is still in flight, then move under `source` when it finishes),
so `mappingsBefore + mappingsInserted` always adds up to `integrity.totalMappings`.

`delta.changes[]` is the "what changed" list — it is computed from `placed_at`, so a re-run that
inserts nothing honestly reports an empty delta instead of repeating the totals.

### `POST /api/admin/gmail/sync` + `GET /api/admin/gmail/sync/status`

Console-script style mailbox sync: for every configured source group it lists the message ids
(`list:<group>` query), fetches each message, stores it with its attachments, extracts and
classifies it — i.e. **everything the Gmail pipeline writes to the database** — while streaming real
progress into `output`.

```jsonc
// POST  body is optional: { "maxResults": 500, "query": "newer_than:7d", "groups": ["..."] }
{ "success": true, "message": "Mailbox sync started", "script": "gmail_sync", "status": "started" }

// GET   (idle until first run)
{ "success": true, "script": "gmail_sync", "runId": "...", "status": "running",
  "message": "…", "username": "admin@jiit", "startedAt": "…", "progress": 42,
  "counters": { "messagesBefore": 581, "messagesAfter": 581, "messagesAdded": 0,
                "attachmentsBefore": 557, "attachmentsAfter": 557, "attachmentsAdded": 0,
                "fetched": 4, "newMessages": 0, "existingMessages": 4,
                "processed": 0, "reviewRequired": 0, "failed": 0,
                "groups": [ { "name": "JIIT Engg 2027", "email": "…", "fetched": 2,
                              "newMessages": 0, "existingMessages": 2,
                              "processed": 0, "reviewRequired": 0, "failed": 0 } ] },
  "output": [ … ] }
```

`messagesBefore` / `messagesAfter` are `COUNT(*)` from `gmailmessages` taken around the run, so
`messagesAdded` is a measured delta. If the Gmail session is not authorized the run fails with the
real error (`status: "failed"`, `error` populated) instead of reporting zeros.

### `DELETE /api/admin/gmail`

Wipes the **synced mailbox only** — `gmailmessages`, `gmailattachments` and `emailextractions`, in
one transaction, children first (`fn_api_delete_all_gmail_v001`). The parsed corpus (`emails`,
`offers`, `offer_students`, …) and `job_placed_students` are deliberately **not** touched, and the
response says so in `output`. Synchronous, guarded by the shared script slot, and recorded in the
history with its console output.

```json
{
  "success": true, "script": "delete_gmail",
  "message": "Mailbox deleted — 581 messages, 557 attachments, 22 extractions",
  "counters": { "messagesBefore": 581, "attachmentsBefore": 557, "messagesDeleted": 581,
                "attachmentsDeleted": 557, "extractionsDeleted": 22, "sqlDurationMs": 67 },
  "phases": [ { "phase": "inspect", "durationMs": 47 }, { "phase": "delete", "durationMs": 77 } ],
  "durationMs": 125,
  "output": [ … ]
}
```

409 while another script runs; `500 { "success": false, "message": ..., "error": ..., "output": [...] }`
on failure. To re-sync afterwards, run `POST /api/admin/gmail/sync`.

### `DELETE /api/admin/jobs/placed-students`

Wipes every row of `job_placed_students` (`fn_api_delete_all_placed_students_v001`). Jobs, offers and
`offer_students` are untouched — `POST /api/admin/jobs/sync-offer-students` rebuilds the whole
mapping from scratch (verified: 906 rows deleted → re-run re-inserted exactly 906 with 0 duplicates).

```json
{
  "success": true, "script": "delete_mappings",
  "message": "Placement mappings deleted — 906 rows cleared",
  "counters": { "mappingsBefore": 906, "studentsBefore": 417, "companiesBefore": 33,
                "mappingsDeleted": 906, "studentsCleared": 417, "companiesCleared": 33,
                "sqlDurationMs": 7 },
  "phases": [ { "phase": "inspect", "durationMs": 47 }, { "phase": "delete", "durationMs": 9 } ],
  "durationMs": 120,
  "output": [ … ]
}
```

### `GET /api/admin/activity?page&pageSize&script`

Newest-first history of **every** admin action (logins, logouts, syncs, deletes) with the console
output each run produced — this is what feeds the admin timeline and the console replay. `pageSize`
is capped at 100; `script` (`login | logout | jobs_sync | gmail_sync | offer_sync | delete_gmail |
delete_mappings | delete_jobs`) filters to one action; `page` is 1-based.

```jsonc
{ "success": true, "message": "Activity fetched successfully",
  "data": { "Items": [ { "id": "…", "script": "offer_sync", "status": "completed",
                         "username": "admin@jiit",
                         "message": "Job to student sync completed — no new mappings (906 total)",
                         "counters": { … }, "output": [ { "time": "18:00:41", "tone": "cmd", "text": "$ …" } ],
                         "error": null, "durationms": 203,
                         "startedat": "2026-09-27T18:00:41+05:30",
                         "finishedat": "2026-09-27T18:00:41+05:30" } ],
            "TotalCount": 7, "Page": 1, "PageSize": 12, "TotalPages": 1 } }
```

### `GET /api/admin/overview`

Everything the admin dashboard shows, counted live from the tables — no cached or estimated values:

```jsonc
{ "success": true, "message": "Overview fetched successfully",
  "data": {
    "counts": { "jobs": 96, "jobsActive": 96, "notices": 55, "gmailMessages": 581,
                "gmailAttachments": 557, "emails": 596, "emailsCanonical": 575, "offers": 94,
                "offerStudents": 895, "mappings": 906, "shortlistEvents": 184,
                "shortlistStudents": 19276, "opportunities": 229 },
    "mailbox": { "total": 581, "processed": 14, "reviewRequired": 2, "irrelevant": 6,
                 "received": 559, "failed": 0, "finishedRate": 3.4, "reviewRate": 0.3 },
    "classification": { "canonical": 575, "classified": 575, "coverage": 100.0,
                        "shortlistedStudents": 19276 },
    "matching": { "studentsConsidered": 504, "studentsMapped": 417, "jobsMatched": 44,
                  "jobsWithoutPlacements": 52, "companiesMatched": 33, "companiesSkipped": 21,
                  "lastRunAt": "…" },
    "integrity": { "orphanMappings": 0, "orphanOffers": 0, "duplicateMappings": 0, "blankRolls": 0 },
    "session": { "lastLogin": "…", "previousLogin": "…", "lastLogout": "…", "logins": 3 },
    "lastRuns": [ { "script": "gmail_sync", "status": "completed", "message": "…",
                    "durationms": 14210, "startedat": "…", "finishedat": "…" } ]
  } }
```

`finishedRate` = share of mailbox rows that finished the pipeline (`PROCESSED + IRRELEVANT`),
`reviewRate` = share still awaiting a human; `coverage` = share of canonical emails that carry a
classification; `integrity` must read all zeros (any orphan/duplicate is a real defect).

### Database migration

```
SQL/migration_admin_scripts.sql
```

Idempotent (`CREATE TABLE IF NOT EXISTS` / `CREATE OR REPLACE FUNCTION`) — run it against
`jiit_placement` before starting the API. It creates:

| Object | Purpose |
| --- | --- |
| `admin_script_runs` | one row per admin action: `script`, `status`, `username`, `message`, `counters jsonb`, `output jsonb`, `error`, `durationms`, `startedat`, `finishedat` |
| `fn_api_script_run_begin_v1(script, username, message)` | opens a run row before the work starts |
| `fn_api_script_run_finish_v1(id, status, message, counters, output, error, durationms)` | closes it with the real counters and console lines |
| `fn_api_script_run_log_v1(script, status, username, message, counters, output, durationms)` | one-shot actions (login / logout) |
| `fn_api_select_script_runs_v1(page, pagesize, script)` | history feed for `/api/admin/activity` |
| `fn_api_admin_overview_v1()` | counts, accuracy ratios, integrity, session, last runs |
| `fn_api_offer_sync_changes_v1(since)` | delta of one sync run (measured from `placed_at`) |
| `fn_api_delete_all_gmail_v001()` | wipe the synced mailbox |
| `fn_api_delete_all_placed_students_v001()` | wipe the job↔student mapping |

JSON payloads are passed as **text** and cast inside the functions — PostgreSQL has no implicit
`text → json` cast, and a `bigint` (CLR `long`) argument does not resolve against an `integer`
parameter, so both mistakes would otherwise fail silently.

### `GET /api/admin/jobs/{jobId}/placed-students`

Who got placed against one job (`jobId` = jobs id **or** Superset job identifier), enriched with the
role and compensation taken from the originating offer email:

```json
{
  "success": true,
  "message": "Placed students fetched successfully",
  "job": { "id": "...", "company": "Zomato", "jobprofile": "...", "package": 5600000 },
  "placedCount": 2,
  "students": [
    {
      "id": "...", "rollno": "9923103020", "studentname": "Archit Tiwari", "branch": "CSE",
      "program": "B.Tech", "email": "...", "role": "Software Development Engineer (SDE) Intern",
      "ctcraw": "INR 56.00 Lakhs", "ctctotal": 5600000.00, "stipend": 100000.00,
      "employmenttype": "internship_to_fulltime", "companyname": "Zomato",
      "offeremailid": "...", "offersubject": "...", "offerreceivedat": "...",
      "placedat": "..."
    }
  ]
}
```

Unknown job → `404 { "success": false, "message": "Job not found" }`.

## Public job API (unchanged envelope)

```
GET /api/jobs?page&pageSize&company&search   → { status, Message, Data }
GET /api/jobs/{id}                           → { status, Message, Data }
GET /api/jobs/{jobId}/documents/{documentId} → raw file bytes
GET /api/notices?page&pageSize&search        → { status, Message, Data }
GET /api/notices/email?page&pageSize&search&type → { status, Message, Data }
GET /api/placements/company-wise?page&pageSize&search → { status, Message, Data }
GET /api/placements/branch-stats                      → { status, Message, Data }
GET /api/placements/jobs/{jobId}/placed-students      → { status, Message, Data }
```

`pageSize` is capped at 100. Missing job → `404`.

* **`/api/notices/email`** — canonical Gmail notices (shortlist, selection process, hackathon, event,
  webinar, …) with `Facets` (count per classification) and a `type` filter; congratulation /
  final-offer emails are excluded on purpose — that data is served by the placement endpoints.
* **`/api/placements/company-wise`** — one row per company that has a job: its listings, the number of
  distinct students placed and their role / CTC distribution (`roles[].ctcmax`).
* **`/api/placements/branch-stats`** — one payload for the whole graduating batch, computed entirely
  inside `fn_api_select_branch_stats_v1` (`SQL/migration_branch_stats.sql`): per-branch placement rate,
  offers, companies, avg/median/highest package (LPA, from `offers.ctc_total` taken once per student),
  JIIT's four official distribution bands and a monthly timeline bucketed on `emails.received_at`.
  The head-count denominators are the reference repo's hardcoded `student_counts` (BATCH_CONFIGS
  `202627`, total 1322), so a rate can never exceed 100%. Purely read-only — no existing table,
  column or function is touched.
* **`/api/placements/jobs/{jobId}/placed-students`** — the public twin of the admin endpoint above.

## Cleanup performed in this revamp (dependency-audited)

**Removed APIs** (each traced route → controller → service → DB → callers first):
`POST /api/jobs`, `POST /api/notices` (manual creation — no internal callers, frontend never used
them), `POST /api/superset/admin/sync`, `POST /api/superset/jobs/sync`,
`POST /api/superset/notices/sync` (superseded by the admin sync API — one sync mechanism only),
`POST /api/superset/authenticate` (login test endpoint).

**Removed code**: `SuperSetController`, `AuthController`, `Cls_Job`, `Cls_Notice`, `Cls_Dashboard`,
unused `Common` helpers (`ReturnResponse_Pagination`, `ParaNameArray`, `Set_SelectSP`,
`ConvertDataTable`, `GetItem`, `AsciiToHex`, `ConvertHex`, `GetSizeInMemory`, `GetMimeType`,
`ToJson`), unused `DataEntity` executors (`ExecuteDataTableSP[Async]`, `ExecuteDataSetFN` ×2).

**Removed DB objects**: `fn_api_post_supersetaccount_v001`, `fn_api_update_studentplacement_status_v001`
(0 code references, `pg_proc` bodies audited), table `supersetaccounts` (0 rows, no views/FKs).

**Truncated** (see `SQL/cleanup_obsolete.sql`): `jobs`, `jobdocuments`, `jobeligibilities`,
`jobeligibilitycourses`, `jobgenders`, `jobhiringflows`, `jobskills`, `notices` — all fetched data
that regenerates via sync; verified at 0. Preserved: gmail/placement tables,
`__EFMigrationsHistory`, every file under `D:\JIITPlacementFiles`.

**Kept intact**: existing job-sync logic (only additive progress callbacks), document storage path
and naming, all public read APIs, the Gmail pipeline.

## Swagger

`/swagger` — includes a `Bearer` security definition (paste the token from `login`).
`JIITPlacement.http` contains a ready-to-run request collection for the whole admin workflow.
