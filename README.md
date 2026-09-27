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

### `POST /api/admin/login`

```json
{ "username": "admin@jiit", "password": "<Admin:Password>" }
```

The development credentials come from `appsettings.json` (git-ignored) or the `Admin__Username` /
`Admin__Password` environment variables — they are never committed to source control.

```json
{ "success": true, "message": "Login successful", "token": "..." }
```

Invalid → `401 { "success": false, "message": "Invalid credentials" }`.
Token: signed JWT (HMAC-SHA256, `Jwt:Secret`) carrying `username`, `role` and a `jti` session id;
expires after `Admin:TokenExpirationHours`, default 8h.

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
{ "success": true, "message": "Job synchronization started", "syncId": "...", "status": "started" }
```

Runs the **existing** sync logic (`SuperSetSyncService.SyncAllAsync`, single SuperSet login, jobs +
notices) in the background — the HTTP request returns immediately. Exactly one admin data operation
(sync **or** delete) can run at a time; concurrent clicks → `409`:

```json
{ "success": false, "message": "Job synchronization is already running", "syncId": "...", "status": "running" }
```

When a deletion holds the slot instead, the message is `"Job deletion is already running"`.

### `GET /api/admin/jobs/sync/status`

Before any run: `{ "success": true, "status": "idle" }`.

While running / when finished (`status`: `idle | running | completed | failed`) — all fields with
unknown values are **omitted, never fabricated**; `progress` only appears once the source total is
known:

```json
{
  "success": true,
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
  "error": null
}
```

Failure path sets `status: "failed"` with a populated `error` and is logged — exceptions are never
silently swallowed.

### `DELETE /api/admin/jobs`

Deletes **every job record** in one transaction (`fn_api_delete_all_jobs_v001`: `jobs` plus the seven
job child tables — notices and Gmail data are never touched) and then removes the documents those
records owned from `FileStorage:RootPath`, including orphaned leftovers under `Jobs\`; the empty
folder tree is dropped too (recreated by the next sync). While a sync (or another deletion) runs →
`409 { "success": false, "message": "Job synchronization is already running" }` /
`"Job deletion is already running"`.

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

### `POST /api/admin/jobs/sync-offer-students`

Admin-triggered matching of the offer students parsed from congratulation emails onto the jobs that
already exist in the system (`fn_api_sync_offer_students_v1`). One run:

* a student is mapped **only** when his/her company exists in the `jobs` table — companies that were
  never listed are counted in `companiesSkipped` and ignored (no job is created, no match is guessed);
* the comparison uses one shared normaliser (trim, collapse spaces, lowercase, drop a single trailing
  parenthetical), so `Josh Technology Group (JTG)` matches `Josh Technology Group`;
* a job row is a company listing, so a student maps to every job row of that company;
* idempotent: `UNIQUE (job_id, student_roll_no)` + `ON CONFLICT DO NOTHING` — a second run inserts
  nothing and reports every candidate under `duplicatesSkipped`.

```json
{
  "success": true,
  "message": "Offer-student sync completed",
  "jobsTotal": 96, "jobsMatched": 44, "jobsWithoutPlacements": 52,
  "studentsConsidered": 504, "studentsMapped": 417,
  "mappingsInserted": 0, "duplicatesSkipped": 906,
  "companiesMatched": 33, "companiesSkipped": 21,
  "totalMappings": 906, "lastRunAt": "2026-09-27T16:19:02.919301+05:30"
}
```

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
GET /api/placements/jobs/{jobId}/placed-students      → { status, Message, Data }
```

`pageSize` is capped at 100. Missing job → `404`.

* **`/api/notices/email`** — canonical Gmail notices (shortlist, selection process, hackathon, event,
  webinar, …) with `Facets` (count per classification) and a `type` filter; congratulation /
  final-offer emails are excluded on purpose — that data is served by the placement endpoints.
* **`/api/placements/company-wise`** — one row per company that has a job: its listings, the number of
  distinct students placed and their role / CTC distribution (`roles[].ctcmax`).
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
