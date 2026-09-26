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
src/placement_pipeline/   library code (normalize, classify, parse, dedup, db)
api/                      FastAPI app
scripts/                  ingestion, validation, corpus export CLIs
tests/                    pytest suite (unit + full-corpus integration)
reports/                  generated validation report
data/                     SQLite database (git-ignored, regenerated)
```

## Quick start

```powershell
pip install -r requirements.txt
python scripts/run_ingest.py            # PostgreSQL -> classify/parse -> SQLite
python scripts/run_validation.py        # accuracy report over labelled samples
python -m uvicorn api.app:app --port 8000
```

## Configuration

Environment variables (see `src/placement_pipeline/config.py`):

- `PLACEMENT_PG_DSN` — PostgreSQL connection string for the mail corpus
- `PLACEMENT_SQLITE_PATH` — SQLite file (default `data/placement.sqlite3`)

## Scope note (step 1)

Step 1 covers ingestion, classification, parsing, dedup, storage, and the read
API over *parsed* records. It performs **no cross-email student identity
mapping** (no roster/master-data resolution); student rows are stored exactly
as parsed (`raw_name` preserved, plus a normalized form).
