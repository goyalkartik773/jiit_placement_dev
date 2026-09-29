# Roll number → branch / batch year

Request-time derivation of `branch_from_roll` and `batch_year` from an
enrollment number. **Additive read-side only** — no table, no column, no
write-path change anywhere: the roll is already on every row, so the value is
computed while serialising and thrown away.

Ported from the reference repo `tashifkhan/JIIT-placement-alerts`, with the
numbers copied verbatim.

---

## 1. Files

| Layer | File | What |
|---|---|---|
| Config (port) | `app/domain/enrollment_ranges.py` | `ENROLLMENT_RANGES`, `BATCH_CONFIGS`, `BranchRange`, `normalize_batch_year`, `get_batch_config`, `get_enrollment_ranges_for_year`, `build_branch_ranges` |
| Logic (port) | `app/domain/roll_mapper.py` | `resolve_branch()`, `resolve_batch_year()` |
| Read path (ours) | `app/schemas/messages.py`, `app/schemas/placements.py`, `app/schemas/serializers.py`, `app/api/placements.py` | two optional fields on every student row |
| SQL (ours) | `JIITPlacement/SQL/migration_job_placed_students.sql` | `fn_branch_from_roll_v1`, `fn_batch_year_from_roll_v1`, two keys in `fn_api_select_placed_students_v1` |
| Frontend (ours) | `frontend/src/types/dashboard.types.ts` | optional `branchfromroll`, `batchyear` on `PlacedStudent` |
| Tests | `app/tests/test_roll_mapper.py` | decision table, boundaries, SQL↔Python parity, endpoint wiring |

## 2. Reference source (verbatim port)

| Ours | Reference |
|---|---|
| `ENROLLMENT_RANGES` | `analysis/config.py:9-56` |
| `BATCH_CONFIGS` (`enrollment_ranges` only) | `analysis/config.py:91-258` |
| `DEFAULT_PLACEMENT_YEAR` | `analysis/config.py:86` |
| `normalize_batch_year` | `analysis/config.py:261-278` |
| `get_batch_config` | `analysis/config.py:281-297` |
| `get_enrollment_ranges_for_year` | `analysis/config.py:300-312` |
| `build_branch_ranges` | `analysis/helpers.py:13-59` |
| `BranchRange` | `analysis/models.py:7-13` |
| `resolve_branch` decision order | `analysis/helpers.py:84-121` (`get_branch_for_year`) |

Not ported — stats-only for the reference, dead code here: `label`,
`graduating_batch`, `student_counts`, `excluded_branches`, `STUDENT_COUNTS`,
`EXCLUDED_BRANCHES`.

### Decision order (the reference's, byte for byte)

```
1. falsy enrollment                    -> "Other"
2. any alpha character                 -> "JUIT"
3. digits startswith "24"              -> "MTech"     <- hardcoded, not a pattern
4. len(digits) == 9                    -> "JUIT"
5. no digits left                      -> "Other"
6. int(digits) raises ValueError       -> "Other"
7. start <= num < end in the ranges    -> branch      <- half-open
8. otherwise                           -> "Other"
```

Steps 1–6 are identical in Python and SQL. Step 7's range list is duplicated
(see §4) because the dashboard reads through .NET, not Python.

## 3. Keying — placement year vs admission year

**The reference keys ranges by placement year**, not admission year:
`202526` = AY 2025-26, graduating batch 2026 (config.py:1-7 says so). So

* `202526` covers `221xxxxx` → admitted 2022
* `202627` covers `231xxxxx` → admitted 2023

The reference is handed that year by its caller and has **no**
`enrollment → year` function at all (its `normalize_batch_year` takes a
placement-year string like `"2025-26"`, never a roll).

We serve students at request time with no placement-year context, so
`resolve_batch_year()` is **our** rule, clearly marked as such:

```
digits = all digits of the roll
digits startswith "99" and len >= 10  -> drop the 2-digit campus prefix
2000 + int(digits[:2])                -> admission year
outside ADMISSION_YEAR_WINDOW (2015..2035) -> None
```

`resolve_branch()` then selects ranges by that admission year, derived from
**each range's own** roll prefix (`ranges_for_admission_year`). This is not a
guess: every configured range has a constant two-digit prefix, and the
graduation maths is consistent — 4-year B.Tech 2022→2026 / 2023→2027, 5-year
Intg. MTech 2021→2026 / 2022→2027.

`admission_year=None` (the default) searches **every** configured year. That
matters: the live corpus is 86% 2023-admitted, and the reference's own
`get_branch()` — which hardcodes the default year — returns `"Other"` for all
of them. Measured over `job_placed_students` (260 distinct rolls):

| | reference `get_branch()` | ours (union) |
|---|---|---|
| resolved to a real branch | 36 (13.8%) | 247 (95.0%) |

`admission_year=2030` (no config) → `[]` → `"Other"`, never raises.

## 4. SQL duplication + drift guard

`fn_api_select_placed_students_v1` runs inside Postgres, so the 20 ranges are
repeated as a `VALUES` list in `fn_branch_from_roll_v1`.
`app/tests/test_roll_mapper.py::test_sql_and_python_mappings_agree` replays
every reference row **plus the start / end−1 / end of every configured range**
against both implementations and fails on any drift. A range added to
`enrollment_ranges.py` but forgotten in SQL fails the suite.

Apply / re-apply after editing either side:

```powershell
$env:PGPASSWORD = (...)
psql -U postgres -d jiit_placement -v ON_ERROR_STOP=1 -f JIITPlacement\SQL\migration_job_placed_students.sql
```

Idempotent — `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` /
`CREATE OR REPLACE FUNCTION` only; the file contains no `DROP`, `DELETE`,
`TRUNCATE` or `ALTER`.

## 5. Response shape

New keys are **optional and additive**; every pre-existing key is untouched.

| Endpoint | New keys |
|---|---|
| `GET /api/placements/jobs/{jobId}/placed-students` (reads SQL) | `branchfromroll`, `batchyear` |
| `GET /api/gmail/messages/{id}` → `offer.students[]`, `events[]`, `shortlists[].students[]` | `branch_from_roll`, `batch_year` |
| `GET /api/placements?student_roll=` | `branch_from_roll`, `batch_year` |

`branch` (extraction-sourced, from `offer_students.branch`) is **not** touched
— `branch_from_roll` lives in its own field so the two can be compared instead
of silently disagreeing. Frontend `PlacedStudent` fields are optional
(`branchfromroll?`, `batchyear?`), so an older backend simply omits them.

## 6. Findings in the live corpus

Over 260 distinct `job_placed_students` rolls / 366 `offer_students` rolls:

| branch | 260 rolls | 366 rolls |
|---|---|---|
| CSE | 162 | 225 |
| ECE | 38 | 61 |
| IT | 21 | 25 |
| JUIT | 18 | 19 |
| Other | 13 | 18 |
| EE-VLSI / EC-ACT | 6 | 12 |
| BT / Intg. MTech | 2 | 3 |
| MTech | 0 | 3 |

`batch_year`: 2023 → 538, 2022 → 39, 2025 → 7, 2024 → 3, 2021 → 2,
`None` → 37 (exactly the JUIT rolls).

**Open items — reported, deliberately NOT "fixed", because the numbers must
stay verbatim:**

1. **`22803xxx` (12 rolls) resolve to `"Other"`.** The reference's `202627`
   config puts Intg. MTech CSE at `22903000-22904000`, but no live roll starts
   with `229` — they are `22803001…22803031`. By the pattern of the `202526`
   config (`218 03xxx` = Intg CSE) the range looks like it should be
   `22803000-22804000`. Needs a decision on the reference numbers.
2. **`21103186`, `21104026` (2021 admits) → `"Other"`** — no `2021` config
   exists in the reference either.
3. **`99`-prefixed 2025 rolls (`9925101700xx`) → `"Other"`** — expected:
   `2025` admission year is not configured yet. `resolve_batch_year` still
   returns `2025`, so the data will slot in once ranges are added.
4. **9-digit rolls (7) → `"JUIT"`** and 18 alpha-bearing rolls → `"JUIT"`,
   exactly as the reference decides, even though several look like ordinary
   2023 CSE rolls with a stray digit (`231030016`).
5. **`startswith("24")` is hardcoded** — a genuine 4-year 2024 admit
   (`241030016`) would be labelled `MTech`. The reference does the same; no
   `24xxxxxx` range exists in any config year. Generifying it would need a
   decision on the reference's intent.
6. Two reference implementations disagree on precedence —
   `helpers.get_branch_for_year` checks `"24"` before the 9-digit rule,
   `service._get_branch:71-95` checks it after. **`helpers.py:84-121` is the
   one ported** (the range named in the task).

### Why the two fields are separate — agreement rate

`offer_students.branch` (extraction-sourced) vs `fn_branch_from_roll_v1` over
the 654 `offer_students` rows that carry both a roll and an extracted branch:

```
agree 558 / 639 = 87.3%     disagree 81 = 12.7%
```

Top disagreement pairs:

| extracted | from roll | n | nature |
|---|---|---:|---|
| `cse` | `Other` | 21 | finding 1/2/3 — unconfigured ranges |
| `cse` | `JUIT` | 20 | finding 4 — 9-digit / alpha rolls |
| `ece-cs` | `ECE` | 18 | **label granularity**, not a conflict |
| `bca` | `MTech` | 6 | config has no BCA/BCA range; `24` prefix rule |
| `ece` | `Intg. MTech` | 4 | **label granularity** |
| `mca` | `Other` | 4 | **config has no MCA range at all** |
| `ee -vlsi` | `EE-VLSI` | 3 | **formatting** (internal space) |
| `it` | `Other` | 2 | unconfigured range |
| `biotechnology` | `BT` | 1 | naming |
| `computer science engineering (cse)` | `CSE` | 1 | naming verbosity |

So roughly a third of the "disagreements" are vocabulary/whitespace, and the
rest are genuine coverage gaps (MCA and BCA are not in the reference config
under any year). Keeping the fields separate means none of this was papered
over into the existing `branch` column.

## 7. Evidence

```
python -m pytest -q                 -> 315 passed, 50 warnings   (was 304, +11)
python scripts/run_backend_validation.py -> RESULT: PASS, golden checks 33/33
python scripts/phase1_regression.py  -> 598/598 ok, idempotent=True,
                                        jobsMatched 43, mappings 500
python scripts/email_extraction_report.py -> exit 0, WARN unchanged
npx tsc --noEmit                    -> exit 0
npx vite build                      -> 186 modules transformed, exit 0
cross-repo compare vs reference     -> identical-year context: 0 mismatches / 30
GET .../placed-students             -> HTTP 200, all 19 old keys + batchyear,
                                        branchfromroll
```

The cross-repo compare also reports 9 mismatches under the *reference's own
default-year* context — every one is a `202627` roll that the reference calls
`"Other"` because its `get_branch()` hardcodes `202526`. That is the intended
improvement from §3, not porting drift.
