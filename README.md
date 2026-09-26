# JIIT Placement — Frontend

React + Vite + TypeScript frontend for the JIIT Placement Management System.
**It consumes the existing `JIITPlacement` backend as-is — no backend APIs, tables or logic were changed or duplicated.**

---

## Run it

```bash
cd frontend
npm install
npm run dev
```

- App: <http://localhost:5173>
- Backend must be running: `cd ../JIITPlacement && dotnet run --launch-profile http` → <http://localhost:5104>
- Swagger (backend): <http://localhost:5104/swagger>

Other scripts: `npm run build` (type-check + production build), `npm run preview`.

## Configuration

```env
# frontend/.env
VITE_API_BASE_URL=http://localhost:5104
```

The dev server is pinned to port **5173** on purpose — the backend's CORS policy
(`JIITPlacement/Program.cs`) allows exactly `http://localhost:3000` and `http://localhost:5173`.
No backend change was required.

---

## Backend API contract (traced, not assumed)

Flow verified end-to-end:

```
PostgreSQL tables → fn_api_select_jobs_v1 / fn_api_select_jobdetail_v1
                 → JobController.cs  →  GET /api/…  →  JSON  →  React service layer
```

Sources: `JIITPlacement/Controllers/JobController.cs`, the function definitions read from the
`jiit_placement` database, and live responses from `http://localhost:5104`.

### 1. `GET /api/jobs?page&pageSize&company&search`

Server-side pagination + search ( `search` matches **jobprofile OR company**, `ILIKE` ).
`pageSize` is capped at **100** by the backend; ordering is `createdat DESC`.

```jsonc
{
  "status": true,
  "Message": "Jobs fetched successfully",
  "Data": {
    "Items": [
      {
        "id": "0f713fd5-…",
        "supersetjobidentifier": "f048a4a2-…",
        "company": "GreyB Services",
        "jobprofile": "Software Developer",
        "placementcategory": "Other than Mass recruitment drives",
        "placementcategorycode": "1",
        "content": "",                     // currently empty for all jobs
        "createdat": "2026-09-19T09:55:50+05:30",
        "deadline": "2026-09-21T08:00:20+05:30",   // null for some jobs
        "location": "Mohali (Chandigarh Region)",
        "package": 1e+06,                  // annual CTC in INR (8 LPA = 800000)
        "packageinfo": "",                 // extra CTC text (present for 26 jobs)
        "jobdescription": "<p>…</p>",      // full description as HTML
        "placementtype": "",               // currently empty for all jobs
        "status": "Active",
        "posteddatetime": "2026-09-20T12:55:02+05:30",
        "updateddatetime": "2026-09-20T15:56:29+05:30",
        "eligiblitymarks": [ { "id": "…", "sysjobuuid": "…", "level": "UG",
                               "criteria": "6", "status": "Active",
                               "posteddatetime": "…", "updateddatetime": null } ],
        "documents": [ { "id": "…", "sysjobuuid": "…", "documentidentifier": "…",
                         "documentname": "JD.pdf", "documentpath": "Jobs\\…",
                         "contenttype": "application/pdf", "filesize": 75756,
                         "status": "Active", "posteddatetime": "…", "updateddatetime": "…" } ]
      }
    ],
    "TotalCount": 87, "Page": 1, "PageSize": 100, "TotalPages": 1
  }
}
```

> Note: array fields are `null` (not `[]`) when a job has no child rows.
> The backend spellings `eligiblitymarks` / `eligiblitycourses` are kept **exactly** as returned.

### 2. `GET /api/jobs/{id}`

`{id}` = job UUID **or** `supersetjobidentifier` (the SQL function matches either).
Same job fields **plus** every child table:

```jsonc
{
  "status": true,
  "Message": "Job fetched successfully",
  "Data": {
    "status": "SUCCESS",
    "data": {
      /* …all job fields… */
      "eligiblitymarks":  [ … ],   // jobeligibilities   (level, criteria)
      "eligiblitycourses": [ … ],  // jobeligibilitycourses (coursename) — up to 400 rows/job
      "allowedgenders":   [ … ],   // jobgenders         (gender)
      "requiredskills":   [ … ],   // jobskills          (skillname) — currently null for all jobs
      "hiringflow":       [ … ],   // jobhiringflows (sequence, stagename), sorted by sequence
      "documents":        [ … ]    // jobdocuments
    }
  }
}
```

404 when the job does not exist.

### 3. `GET /api/jobs/{jobId}/documents/{documentId}`

Returns the **actual file bytes** with the file's `content-type` and
`Content-Disposition: attachment; filename=…`. Supports PDF, DOCX, XLSX, PNG, ZIP, etc.
404 when the job/document is unknown or the file is not stored locally yet.

### Auth

No `[Authorize]` attributes on the public jobs API — all GET endpoints are open.

### Admin API (used by `/admin`)

The admin console talks to the backend's admin API (full contract in
`JIITPlacement/README.md`). Every endpoint requires `Authorization: Bearer <token>`:

| Endpoint | Purpose |
|---|---|
| `POST /api/admin/login` | `{username, password}` → `{success, message, token}`; 401 `Invalid credentials` |
| `POST /api/admin/logout` | Revokes the session token server-side; 401 `Unauthorized` without one |
| `GET /api/admin/jobs/count` | `{success, totalJobs}` from `fn_api_count_jobs_v001()` |
| `POST /api/admin/jobs/sync` | Starts the single background sync; 409 `Job synchronization is already running` when one is live |
| `GET /api/admin/jobs/sync/status` | `idle / running / completed / failed` + real counters (fields stay `null` until actually known) |
| `DELETE /api/admin/jobs` | Deletes every job record **and** its stored documents; 409 while a sync (or another delete) runs. Returns honest counts (`jobsDeleted`, `documentRowsDeleted`, `filesDeleted`, `filesMissing`, `filesFailed`) plus real per-phase timings (`phases[]`) |

The token lives in `sessionStorage` (per tab — never logged or rendered) and is
attached by `services/adminService.ts`, the only file that knows these paths. The frontend
treats it as an opaque bearer string (the backend issues a signed JWT — no frontend change
needed). Progress is polled from the status endpoint every 2s while a run is active — the
UI never invents percentages.

### Script console

`components/admin/ScriptConsole/` renders every operation as terminal output: timestamped,
tone-colored lines (command / info / success / warn / error / dim) inside a dark console
window with `role="log"` + `aria-live`, auto-scroll and a blinking cursor while busy.
Lines are produced by `hooks/useAdminSync.ts` **from real server responses only** — the
request that was sent, run milestones, polled progress bars built from server counters,
delete phase timings, and failures. Nothing is fabricated; an empty console reads
"Awaiting command…". The destructive action is two-step: the first click arms the button
("Click again to confirm" + a live-count hint) and auto-disarms after 4 seconds.

---

## How data maps into the UI

| UI element | Backend field(s) |
|---|---|
| Role line (`job-card__role`) | `jobprofile` |
| Company (+ avatar initials) | `company` |
| Location | `location` (single string, shown as-is) |
| Status badge | `status` (e.g. `Active`) |
| Category chip / “type” | `placementcategory` (+ `placementcategorycode`) |
| Salary | `package` (INR → `₹10,00,000`, `10 LPA`), `packageinfo` |
| Posted date | `posteddatetime` (fallback `createdat`) |
| Deadline | `deadline` (+ factual “deadline passed” when the date is past) |
| Description | `jobdescription` (HTML, rendered as rich text) |
| Document count / list | `documents[]` (correlated by `sysjobuuid` = job `id` server-side) |
| Eligibility | `eligiblitymarks[]`, `eligiblitycourses[]` |
| Skills / genders | `requiredskills[]`, `allowedgenders[]` |
| Selection process | `hiringflow[]` (ordered by `sequence`) |

Relationships are **never** matched by array index — documents always travel inside their own
job's response (`sysjobuuid`), and downloads use the job's `id` + the document's `id`.

### Deliberately not invented

- **Experience / job-type / department fields do not exist in the API** → not shown.
- `placementtype` and `content` exist but are empty for every current job → shown as
  “Not specified” / omitted.
- Filters the backend cannot evaluate (location/status/category) run **client-side only when the
  complete result set is loaded** (`items.length === TotalCount`), so displayed counts never lie.
  Search + pagination are always server-side.

## Feature checklist

**Functionality (unchanged from the original integration)**

- ✅ Job listing from `GET /api/jobs` with server pagination + server search (debounced)
- ✅ Refine filters (location / status / category) + sorting over the complete result set
- ✅ Job details route `/jobs/:jobId` with every field the API returns
- ✅ Admin console route `/admin`: sign-in, live job count, single-run sync with honest
  server-side progress, completed/failed result summaries, logout — presented as a
  terminal-style **script console** (real request/milestone/progress/phase lines)
- ✅ **Delete all jobs** (two-step confirm) — removes every job record and its stored
  documents, prints the server's real phase timings and refreshed count
- ✅ Documents with **working View** (PDF/images opened via blob URLs) and
  **Download** (real bytes from `GET /api/jobs/{jobId}/documents/{documentId}`)
- ✅ Loading skeletons, empty states, error states with retry, failure toasts
- ✅ Null/missing/empty-array safe rendering everywhere
- ✅ Env-based API base URL, centralized service layer, no hardcoded endpoints
- ✅ No mock/demo data — every byte on screen comes from the backend

**Engineering & UI (refactored to production standards)**

- ✅ SCSS design system: `styles/_variables.scss` (all colors/spacing/type/radius/shadows/breakpoints),
  `_mixins.scss`, `_reset.scss`, `_typography.scss`, `_utilities.scss`, `_animations.scss`, `main.scss`
- ✅ Component-per-folder with colocated styles: `JobCard/JobCard.tsx` + `JobCard.scss` — zero inline styles,
  zero hardcoded hex values outside `_variables.scss`
- ✅ BEM class naming (`job-card`, `job-card__role`, `job-card--skeleton`)
- ✅ Data flow separated: `Component → hook → service → apiClient` (pages contain no raw fetch logic;
  filter/sort logic lives in `utils/jobList.ts`)
- ✅ Reusable primitives: Button/ButtonLink, Badge, Chip, Icon, IconLabel, CompanyAvatar, Skeleton,
  Loader, StateShell → EmptyState/ErrorState/NotFoundState, Toast
- ✅ Detail page split into JobHeader / JobOverview / JobDescription / JobRequirements /
  JobSelectionProcess / JobDocuments + DocumentItem
- ✅ Responsive at 5 breakpoints (480/640/860/1080/1280) — cards stack, details rail unsticks,
  metadata wraps, buttons stay touchable
- ✅ Accessibility: semantic landmarks, skip-to-content link, real `<button>`/`<link>` elements,
  visible focus rings, labelled selects, `aria-live` counts, `prefers-reduced-motion` support
- ✅ Performance: memoized `JobCard`, memoized derived options/filtered lists, aborted stale requests
- ✅ Typography: Inter (UI) + JetBrains Mono (IDs & labels) with system fallbacks

## Architecture & styling

```
Component (.tsx)  →  className only
      ↓ import './Component.scss'
Component.scss    →  @use '../../../styles/variables' as *   (design tokens)
                     @use '../../../styles/mixins' as *      (up/down/card/truncate/…)
```

- **No value is typed twice**: change a color/space/radius once in `_variables.scss`.
- **No inline `style={{}}`** anywhere; dynamic skeleton sizes use token-backed modifier
  classes (`skeleton--w-lg`, `skeleton--h-md`).
- Page-level composition lives in `pages/`; presentational pieces live in `components/`;
  endpoint paths live only in `services/`.

### Color coding system (fixed semantics)

The rules live **once** in `src/utils/tiers.ts` (pure functions) with the palettes in
`_variables.scss`; components only render the returned `key`:

| Channel | Scale | Palette |
|---|---|---|
| **CTC tier** (card PACKAGE pill + `CtcChip`) | Entry &lt; ₹4L · Standard 4–8 · Advanced 8–12 · High 12–20 · Premium 20+ | slate → blue → violet → gold → emerald |
| **Min. criteria** (`CriteriaChip`) | relaxed ≤ 6 CGPA / ≤ 60 % · moderate ≤ 7.5 / ≤ 75 % · strict above | success green · warning amber · danger red |
| **Company avatar** | `company` column → initials on the fixed brand-gradient tile | blue-700 → blue-600 → indigo-800 + white sheen |

`TierLegend` sits above the job grid so first-time users learn the scale instantly;
the same palette repeats in the card's PACKAGE pill, the detail hero stat and the overview card.
Color never carries meaning alone — the chip text (`₹8 LPA`, `UG · 7`) always states
the value, and tier words (Entry…Premium) appear on detail views.

## Structure

```
frontend/
├── src/
│   ├── assets/images|icons/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button/         Badge/          Chip/
│   │   │   ├── Icon/           IconLabel/      CompanyAvatar/
│   │   │   ├── Skeleton/       Loader/         Toast/
│   │   │   ├── CtcChip/        StateShell/     EmptyState/
│   │   │   ├── ErrorState/     NotFoundState/
│   │   ├── layout/
│   │   │   ├── Header/  Footer/  MainLayout/   # app shell + skip link
│   │   ├── admin/
│   │   │   ├── AdminLogin/  SyncPanel/         # sign-in + operations panel
│   │   │   └── ScriptConsole/                  # terminal-style output surface
│   │   └── jobs/
│   │       ├── JobCard/  JobList/  JobsToolbar/  Pagination/
│   │       ├── JobHeader/  JobOverview/  JobDescription/
│   │       ├── JobRequirements/  JobSelectionProcess/
│   │       ├── JobDocuments/  DocumentItem/
│   │       ├── CriteriaChip/  TierLegend/      # color-coding primitives
│   │       └── _detail-card.scss               # shared detail section shell
│   ├── pages/
│   │   ├── Jobs/           (Jobs.tsx + Jobs.scss)
│   │   ├── Admin/          (Admin.tsx + Admin.scss)
│   │   ├── JobDetails/     (JobDetails.tsx + JobDetailsSkeleton.tsx + .scss)
│   │   └── NotFound/       (NotFound.tsx + NotFound.scss)
│   ├── services/           # apiClient.ts, jobService.ts, documentService.ts, adminService.ts
│   ├── hooks/              # useJobs, useJobDetails, useDebounce, useAdminSync
│   ├── utils/              # format, html, jobList, tiers (color-coding rules)
│   ├── types/job.types.ts  # exact backend contract (incl. key spellings)
│   ├── types/admin.types.ts # admin API response shapes
│   └── styles/
│       ├── _variables.scss  _mixins.scss  _reset.scss  _typography.scss
│       ├── _utilities.scss  _animations.scss  main.scss
├── .env                    # VITE_API_BASE_URL
└── vite.config.ts          # pinned to 5173 to match backend CORS
```
