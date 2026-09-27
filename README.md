# placement_pipeline

Deterministic Python ingest/classify/parse pipeline for the JIIT & Jaypee
placement mailing-list corpus (`gmailmessages` in the `jiit_placement`
PostgreSQL database), a SQLite store of the extracted placement facts, and a
FastAPI read API on top of it.

No LLM/API dependency: classification and extraction are heuristic + rule
based, so results are reproducible and auditable.

The repository also contains the **Gmail placement backend** (`app/`): a
production FastAPI service that syncs raw messages from Gmail into the same
central PostgreSQL database and processes them into normalized placement
tables. Its deliverables are documented 1–14 below; the original parser
library documentation follows afterwards.

---

# Gmail backend — deliverables (1–14)

## 1. Architecture

Two-step flow, exactly as specified:

```
Step 1  POST /api/gmail/sync           Gmail API -> raw emails (PENDING)
Step 2  POST /api/gmail/process-pending  PENDING -> classify + extract -> tables
```

Processing pipeline per email (deterministic first, LLM optional):

```
sync raw -> MIME decode (app/gmail/mime.py, HTML->text)
        -> PostgreSQL emails (status PENDING)
        -> prepare_parts (quoted/forwarded stripping, placement_pipeline)
        -> normalization -> rule-based classification (app/classifiers/taxonomy.py)
        -> deterministic extraction (app/extractors/* on placement_pipeline output)
        -> Pydantic-validated rows -> dedup/cluster links
        -> delete-then-rebuild DB write (idempotent)
```

```
app/
  api/           FastAPI routers (gmail, messages, companies, placements,
                 opportunities, status, deps)
  services/      sync_service, processing_service, status_store
  gmail/         auth (OAuth refresh), client (quota pacing), mime, attachments
  parsers/       email_adapter: DB row -> placement_pipeline Email
  classifiers/   taxonomy (14-value mapping), llm_fallback (optional)
  extractors/    offers, shortlists, opportunities, events, companies, evidence
  models/        SQLAlchemy ORM (10 tables)
  schemas/       Pydantic request/response models + serializers
  repositories/  email/company/placement/opportunity queries (pagination)
  workers/       JobRunner + live status counters
  utils/         structured JSON logging (secrets never logged)
  tests/         44-test suite on the app_test schema of the same database
```

- The parser/classifier/dedup logic is reused from `src/placement_pipeline`
  (installed editable); `app/` is the wiring: Gmail, status machine,
  PostgreSQL persistence, taxonomy mapping.
- Jobs run in-process via `JobRunner` — one sync **and** one processing run
  at a time, with live counters on `/api/sync/status` and
  `/api/processing/status`. No Kafka/Redis/Celery/Kubernetes.

## 2. Database schema

One central PostgreSQL database (`jiit_placement`), same instance the legacy
system uses; its 13 existing tables are never touched (Alembic env filters
them out of autogenerate).

Migration: `alembic upgrade head` -> revision `e93c6591e1da` creates this
system's schema alongside the existing tables.

| table | contents |
|---|---|
| `emails` | raw messages: gmail ids, headers, bodies, `classification` + signals, `processing_status` (PENDING/PROCESSING/PROCESSED/FAILED/SKIPPED), `error_message`, `retry_count` |
| `email_attachments` | attachment metadata + extracted text (`legacy_copy` / `downloaded` / `inline` / `skipped`) |
| `companies` | canonical name, raw name, aliases |
| `offers` | one row per final-selection email: role, CTC (value + raw + basis), stipend, deadline, evidence `{value, confidence, evidence, method}` |
| `offer_students` | student rows of one offer (roll_no, name, status_raw) |
| `shortlist_events` | one row per shortlist/process email: `stage` enum + `stage_raw` verbatim, venue, reporting_at, selection steps, interview dates, deadline |
| `shortlist_students` | named shortlist rows (roll_no, status_raw) |
| `funnel_counts` | ordered `{round_name, count}` aggregates (2B pattern) |
| `opportunities` | hackathons/events/etc: `event_type` (taxonomy value), eligibility, team rules, links, deadline, `is_revision_of` |
| `student_placement_events` | append-only per-student timeline keyed by `roll_no` |

Indexes: unique `gmail_message_id`, `thread_id`, `roll_no`, `company_id`,
`event_type`, `processing_status`, `classification`, `created_at`/
`received_at` — list/detail endpoints page at 1,000+ emails without seq scans.

Lifecycle statuses stored per student: `REGISTERED → ELIGIBLE →
SHORTLISTED → FINAL_SELECTED/OFFERED → JOINED` plus `REJECTED`,
`DISQUALIFIED`, `UNKNOWN`. **`JOINED` is never generated automatically**,
shortlisted rows are never auto-upgraded to selected, and every value comes
from the source email or stays `NULL`.

## 3. Gmail OAuth and environment variables

OAuth mirrors the existing .NET admin app so both share one consent:

- `credentials.json` — OAuth **web** client id/secret (`GMAIL_CREDENTIALS_PATH`)
- `token.json` — `AccessToken`/`RefreshToken`/`ExpiresInSeconds`/`IssuedUtc`
  cache (`GMAIL_TOKEN_PATH`), refreshed over HTTPS only when expired
  (2-minute skew), written back atomically
- scope: `gmail.readonly` (the backend never writes to the mailbox)
- tokens are **never** logged or embedded in errors

Secrets live only in the git-ignored `.env` / environment:

| variable | purpose | default |
|---|---|---|
| `PLACEMENT_DATABASE_URL` or `PLACEMENT_PG_HOST/PORT/DB/USER` + `PLACEMENT_PG_PASSWORD`/`PGPASSWORD` | PostgreSQL connection | `localhost:5432/jiit_placement`, user `postgres` |
| `GMAIL_SOURCE_GROUPS` | comma-separated Google Groups to sync | 5 JIIT/Jaypee groups (see `app/config.py`) |
| `GMAIL_PAGE_SIZE`, `GMAIL_MIN_INTERVAL_MS`, `GMAIL_REQUEST_TIMEOUT` | request pacing (consumer quota ~60 queries/min) | 100 / 1100 ms / 30 s |
| `GMAIL_MAX_ATTACHMENT_BYTES` | attachment download cap | 5 MiB |
| `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`, `GMAIL_APPLICATION_NAME` | OAuth material | shared .NET paths |
| `PLACEMENT_LLM_ENABLED` | enable the Gemini fallback | off |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL` | LLM fallback config | `gemini-2.5-flash` |
| `LOG_LEVEL` | structured log level | `INFO` |

## 4. Endpoints

All responses use the envelope `{success, message, data}`; errors use
FastAPI's `{detail}` with **404** (unknown id), **422** (schema validation),
**409** (a run of that kind is already in progress), **502/503** (Gmail
API/auth failure).

| method | path | purpose |
|---|---|---|
| POST | `/api/gmail/sync` | Step 1: fetch raw messages (optional `query`, `groups`, `max_results`, `download_attachments`) |
| POST | `/api/gmail/process-pending` | Step 2: classify + extract (`limit` 1–10000) |
| POST | `/api/gmail/messages/{message_id}/process` | process/retry one email (uuid or gmail id) |
| GET | `/api/sync/status`, `/api/processing/status` | live job counters |
| GET | `/api/gmail/messages` | paginated list; filters `status`, `classification`, `q` |
| GET | `/api/gmail/messages/{message_id}` | full detail incl. extraction rows + signals |
| GET | `/api/companies` | companies with offer/shortlist totals (`q`) |
| GET | `/api/companies/{company_id}/funnel` | latest `[{round_name, count}]` + source email |
| GET | `/api/placements?student_roll=` | one student's append-only timeline |
| GET | `/api/placements/summary` | aggregate counts + package stats |
| GET | `/api/opportunities?upcoming=true&event_type=` | hackathons/events/webinars |
| GET | `/health` | liveness |

Pagination is `page` / `page_size` (1–100) with honest `total` metadata on
every list endpoint.

## 5. Classification taxonomy

14 spec values; the deterministic parser's coarse category (OFFER /
SHORTLIST / OPPORTUNITY / OTHER) is mapped by a **hybrid multi-signal**
layer (`app/classifiers/taxonomy.py`) that always combines category,
subject + body wording, and extracted evidence — never a single keyword.
Anything unmatched is `UNKNOWN` (never a forced fit).

| taxonomy value | primary signals |
|---|---|
| `FINAL_SELECTION` | parser category OFFER (offer/PPO tables) |
| `SHORTLIST` | named shortlist table, or funnel counts, or explicit shortlist subject |
| `SELECTION_PROCESS_NOTICE` | process logistics wording (venue/reporting/GD/technical round) without list evidence |
| `REGISTRATION` | registration-stage wording (subject-strong) incl. registration-status tables |
| `JOB_OPPORTUNITY` | hiring + company, drive wording |
| `INTERNSHIP_OPPORTUNITY` | internship wording / internship drives |
| `HACKATHON` | hackathon/contest typing |
| `EVENT`, `WORKSHOP`, `WEBINAR` | event typing; subject-strong webinar wins over a parent hackathon program |
| `OFF_CAMPUS_OPPORTUNITY` | off-campus wording (subject+body) |
| `GENERAL_PLACEMENT_NOTICE` | placement-cell policy/admin wording |
| `IRRELEVANT` | footer-sized body with zero signals (company/dates/links/rows) |
| `UNKNOWN` | no confident combination |

Sub-rules order subject-strong signals before body evidence, and explicit
shortlist wording outranks registration wording when both appear. Corpus
distribution after full processing (596 emails): SHORTLIST 137,
FINAL_SELECTION 94, HACKATHON 90, REGISTRATION 49, EVENT 44,
GENERAL 42, UNKNOWN 39, SPN 28, INTERNSHIP 27, WEBINAR 21, JOB 20,
WORKSHOP 5, **OFF_CAMPUS 0, IRRELEVANT 0** (zero corpus samples — their
rules are proven by unit tests only; see deliverable 11).

## 6. Pydantic schemas

- `ApiResponse[T]` — universal `{success, message, data}` envelope
- `SyncRequest` / `SyncStats`, `ProcessPendingRequest` / `ProcessStats` /
  `MessageProcessResult`, `JobStatus`
- `MessageSummary` / `MessageDetail` (rows, attachments,
  `classification_signals`, `classification_method`, dedup/revision links)
- `OfferOut` (with per-row students), `ShortlistEventOut` (+`stage_raw`,
  steps, interview dates), `FunnelCountOut`, `OpportunityOut` (links,
  eligibility, team rules, `is_revision_of`), `CompanyOut`/`FunnelOut`,
  `StudentTimeline`, `PlacementSummary`
- Field constraints do real validation work: `page_size ≤ 100`,
  `1 ≤ limit ≤ 10000`, `student_roll` required (`422` otherwise)

Every semantic extraction carries provenance: `{value, confidence,
evidence, method: rule_based | llm | hybrid}` columns on offers,
shortlists, funnel rows, opportunities and student events.

## 7. Deduplication

- **Gmail level**: `gmail_message_id` is unique — a per-run `seen` set, a
  pre-insert existence check and the unique index (IntegrityError →
  counted as duplicate) make sync idempotent; the same message cross-posted
  to several groups is stored once.
- **Cluster level**: normalized `cluster_key` (subject + sender) links
  crossposts and revisions — `is_canonical`, `dedup_of`, `revision_of`
  (`opportunities.is_revision_of`). Revisions are *linked*, never
  double-counted; distinct events from the same company are never merged
  (different subjects keep different cluster keys).
- **Student identity**: `roll_no` (raw name always preserved alongside the
  normalized form).
- **Timeline**: `student_placement_events` is append-only; reprocessing one
  email deletes only *that email's* derived rows (delete-then-rebuild) and
  rebuilds them, so other emails' contributions stay intact.

## 8. Error handling

- **Sync**: per-message isolation (a failing `messages.get` marks
  `failed_messages` and continues); quota/pagination failures (403/429)
  abort *gracefully* — every committed row is kept, `errors[]` records the
  group, remaining groups are skipped, and a re-run resumes idempotently.
  Client pacing: `GMAIL_MIN_INTERVAL_MS` spacing + 62 s backoff on quota.
- **Processing**: per-email isolation — an exception rolls back that email's
  partial rows, sets `FAILED` + `error_message` (type + message) +
  `retry_count += 1`, and the queue continues. Stale `PROCESSING` rows are
  reset to `PENDING` at the start of every run (crash recovery).
- **Jobs**: one run per kind at a time → `409` with the live snapshot;
  Gmail auth failure → `503`, Gmail API failure → `502`.
- **Logging**: structured JSON events (`job.*`, `sync.*`, `process.*`) with
  counters; secrets (passwords, tokens, client secrets) are never logged.

## 9. LLM strategy

- Fully **optional**: `PLACEMENT_LLM_ENABLED` (default off). The pipeline
  behaves identically when the LLM/API is unavailable.
- Used only as a fallback for genuinely ambiguous prose: parser category
  `SHORTLIST` with **zero** deterministic students and zero funnel counts.
- Results are recorded with `method = llm` and the same
  `{value, confidence, evidence}` provenance; everything else stays
  `rule_based`. No LLM is ever allowed to invent students or counts.

## 10. Run commands

```powershell
# setup
pip install -r requirements.txt
python -m pip install -e .                      # placement_pipeline (parser)
$env:PLACEMENT_PG_PASSWORD = "<password>"       # or keep the git-ignored .env

# database
alembic upgrade head                            # creates this system's schema

# run the API (repo root)
python -m uvicorn app.main:app --reload --port 8000

# tests (44 backend tests on the app_test schema of the same DB)
python -m pytest app/tests -q
# parser library tests (174)
python -m pytest tests -q

# validation reports
python scripts/run_validation.py                # 18-sample parser ground truth
python scripts/run_backend_validation.py        # full backend report (exit 0 = PASS)
python scripts/corpus_seed.py <gmail_id> ...    # seed specific emails (optional)
```

## 11. Accuracy & validation results

Latest run — `reports/backend_validation.md` (regenerated by
`python scripts/run_backend_validation.py`):

- **Parser ground truth: 18/18 samples, 99/99 checks** (categories,
  packages, roles, deadlines, funnel counts, links, company names).
- **Golden taxonomy + DB rows: 33/33 samples, 99/99 checks** - 18 validated
  samples + 15 hand-reviewed extras covering every corpus-reachable
  taxonomy value; each check asserts the label *and* the derived rows
  (offer/shortlist student counts, funnel counts, opportunity deadline/
  links/event_type, company, and the revision link of the DPA resend -
  its parent email is seeded alongside as an unscored support row).
- **Reprocess idempotency: identical derived row counts** over two full
  golden reprocesses (and over the whole corpus — deliverable 14).
- **Test suite: 44/44** (`app/tests`), including sync idempotency,
  crosspost dedup, per-email error isolation, quota abort + resume,
  attachment download/parse, every read endpoint with 404/422 guards, and
  the golden dataset end-to-end through the public API.

Honest gaps:

- `OFF_CAMPUS_OPPORTUNITY` and `IRRELEVANT` have **zero** samples in the
  saved corpus; their rules are covered by unit tests only
  (`app/tests/test_taxonomy.py`).
- One email (Codestore `1a0c23cae824d3fb`) parses its student list
  partially (57/162): names continued as wrapped prose outside a table are
  only recovered when they match table-like rows (see deliverable 13).

## 12. Assumptions

- The API has **no authentication**: it is an internal admin backend for
  the placement cell's network (the Gmail OAuth is read-only and the DB is
  the shared university instance). Add auth before exposing it publicly.
- Sync reads the five configured Google Groups; the corpus-backed defaults
  are `jiitengg2027`/`jaypeeengg2027`, the rest come from the platform spec
  (empty lists are harmless).
- Legacy data is reused, not re-fetched: attachment text already extracted
  by the .NET system is copied (`method = legacy_copy`); only new/xlsx/
  csv/txt attachments ≤ 5 MiB are downloaded and parsed here.
- Email timestamps come from the `Date` header (stored `timestamptz`);
  the parser receives IST-wall-clock naive datetimes (legacy semantics).
- Single-process deployment: `JobRunner` serializes sync and processing
  runs (no queue infrastructure, per spec).
- `JOINED` and any count not present in an email are never invented.

## 13. Known unparsable / partial patterns

- **Wrapped-prose student lists**: names continued outside a table (the
  Codestore email: 57/162 rows) are recovered only when they look like
  table rows; the rest are honestly missing rather than guessed.
- **Clipped / truncated bodies** (mailbox truncation): extraction uses
  whatever text exists; missing fields stay `NULL`.
- **Malformed spacing in tables**: tolerated by the normalizer, but
  degenerate columns can drop a row — never fabricate one.
- **Forwarded/quoted threads**: quoted history is stripped before parsing;
  revised emails are linked via `is_revision_of` instead of being merged.
- **HTML-only mails**: converted to clean text (block-aware); exotic
  layouts may lose visual grouping — the attachment text path is used when
  the real table is an attachment.
- The corpus currently contains no off-campus or footer-junk mail, so those
  two rules have no end-to-end sample (deliverable 11).

## 14. Idempotency & scale proof (recorded live runs)

```
Sync run 1   : 1146 fetched, 364 new, 782 duplicates, 0 failed, 417.9s
Sync re-run  : 1146 fetched,   0 new, 1146 duplicates, 0 failed,  17.9s
Process run 1: 596 pending -> 596 succeeded, 0 failed
Process run 2: same 596 forced back to PENDING -> 596 succeeded, 0 failed;
               derived row counts identical (offers 94, offer_students 895,
               shortlist_events 184, shortlist_students 19276,
               funnel_counts 12, opportunities 229,
               student_placement_events 20171)
Error case   : Codestore 1a0c23cae824d3fb failed once (isolated, error kept),
               parser edge case fixed -> 596/596 on re-run
Quota        : 403/429 responses back off 62s; sync aborts gracefully and a
               re-run resumes (rows committed so far are kept)
Scale        : full corpus (596 stored / 1146 listed) processed twice with
               identical results; list endpoints paginate (page_size <= 100)
```

The same proofs re-run automatically for the golden set by
`scripts/run_backend_validation.py` and `app/tests/test_golden_dataset.py`.

---

# Parser library (original scope)

## Categories

| Category   | Meaning                                                            |
|------------|--------------------------------------------------------------------|
| `OFFER`    | Offer / PPO / offer-status notices with (usually) student lists     |
| `SHORTLIST`| Round-wise progress: named shortlists (pattern A) and aggregate funnel counts (pattern B) |
| `OPPORTUNITY` | External events: hackathons, contests, webinars, sessions, apply-by notices |
| `OTHER`    | Administrative / policy / logistics mail kept for manual review    |

Emails that do not fit any pattern are kept raw under `OTHER` — the pipeline
never force-fits a category.

## Layout

```
src/placement_pipeline/   library code (normalize, classify, parse, tables,
                          dates, numbers, dedup, ingest, db, config)
src/placement_pipeline/api/  FastAPI app (placement_pipeline.api.app)
app/                     Gmail backend (deliverables 1-14 above)
scripts/run_validation.py    ground-truth validation over labelled samples
scripts/run_backend_validation.py  backend golden validation + report
tests/                   pytest suite (unit + parser/API regression tests)
app/tests/               backend test suite (app_test schema)
reports/                 generated validation reports
data/                    SQLite database (git-ignored, regenerated)
```

## Quick start

```powershell
pip install -r requirements.txt
python -m placement_pipeline.ingest        # PostgreSQL -> classify/parse -> SQLite
python scripts/run_validation.py           # accuracy report over labelled samples
python -m pytest tests -q                  # unit + regression suite
python -m uvicorn placement_pipeline.api.app:app --port 8000
```

## Read API (parser library)

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/` | route index |
| GET  | `/companies` | per-company counts (offers, students, packages) |
| GET  | `/companies/{name}/funnel` | funnel counts for one company |
| GET  | `/offers`, `/offers/summary` | offer records + summary aggregates |
| GET  | `/shortlists` | shortlist records (named lists + funnel counts) |
| GET  | `/opportunities` | opportunity/event records |
| GET  | `/students/{roll_no}` | one student's parsed rows across emails |
| GET  | `/emails/{email_id}` | one email with rows, counts and links |
| POST | `/sync` | run the PostgreSQL ingest on demand |

List endpoints accept `limit`/`offset` paging plus category-specific filters
(company, status, date ranges) and return honest pagination metadata.

## Configuration

Environment variables (see `src/placement_pipeline/config.py`):

- `PLACEMENT_PG_DSN` — PostgreSQL connection string for the mail corpus
- `PLACEMENT_SQLITE_PATH` — SQLite file (default `data/placement.sqlite3`)

## Scope note (step 1)

Step 1 covers ingestion, classification, parsing, dedup, storage, and the read
API over *parsed* records. It performs **no cross-email student identity
mapping** (no roster/master-data resolution); student rows are stored exactly
as parsed (`raw_name` preserved, plus a normalized form).
