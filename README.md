# placement_pipeline

Deterministic Python ingest/classify/parse pipeline for the JIIT & Jaypee
placement mailing-list corpus (`gmailmessages` in the `jiit_placement`
PostgreSQL database), a SQLite store of the extracted placement facts, and a
FastAPI read API on top of it.

No LLM/API dependency: classification and extraction are heuristic + rule
based, so results are reproducible and auditable.

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
scripts/run_validation.py    ground-truth validation over labelled samples
tests/                    pytest suite (unit + parser/API regression tests)
reports/                  generated validation report (validation.md)
data/                     SQLite database (git-ignored, regenerated)
```

## Quick start

```powershell
pip install -r requirements.txt
python -m placement_pipeline.ingest        # PostgreSQL -> classify/parse -> SQLite
python scripts/run_validation.py           # accuracy report over labelled samples
python -m pytest tests -q                  # unit + regression suite
python -m uvicorn placement_pipeline.api.app:app --port 8000
```

## Read API

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
