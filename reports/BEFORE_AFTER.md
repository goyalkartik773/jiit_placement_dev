# Before / After — final reprocess + end-to-end gate

| | BEFORE | AFTER |
|---|---|---|
| snapshot | 2026-09-30 00:44:54 | 2026-09-30 02:23:32 |

## 1. Extraction & counting

| Metric | Before | After | Why |
|---|---|---|---|
| `emails` / processed | 600 / 600 | 600 / 600 | 3 transient FAILED recovered by retry |
| `offers` | 92 | **83** | 9 dedup copies no longer create their own offer |
| `offer_students` rows | 760 | **634** | −126 double-counted rows from those 9 copies |
| distinct `offer_students` rolls | 392 | **392** | **unchanged — zero students lost** |
| rows from dedup copies | 126 | **0** | `METHOD_DEDUP_COPY` skip |
| duplicate student inside one offer | 18 extra | **0** | keyed on `(offer_id, roll-or-name)` |
| duplicate `(email, roll, event_type)` events | 209 extra | **0** | same fix, verified over non-blank rolls |
| FAILED / PENDING emails | 3 | **0** | transient unique-violation, cleared on retry |

## 2. Field completeness (`offer_students`)

| Field | Before filled | After filled |
|---|---|---|
| Role | 723 / 760 (95.1%) | **606 / 634 (95.6%)** |
| College | 0 / 760 | **115 / 634** |
| Student email | 0 / 760 | **100 / 634** |
| distinct role strings | 60 | **64** |

College/email remain partial: `_det_row` restore only matches mails whose
deterministic row layout is recoverable. Flagged, not yet fixed.

## 3. `job_placed_students` (the read path the dashboard uses)

| Metric | Before | After |
|---|---|---|
| rows | 655 | **420** |
| distinct students | 371 | **382** |
| jobs | 52 | **50** |
| companies | 41 | **46** |
| **fan-out** (rows ÷ distinct `company+roll`) | **1.61** | **1.0000** |
| company-less rows | 0 | **0** |
| Infosys `Systems Engineer` over-claim | **88** | **0** |
| zero-mapped companies | **11 / 23 students** | **6 / 10 students** |

Fewer rows, *more* students: 655 rows were overstating 371 real placements;
420 rows now cover 382 distinct students. The 248 removed rows were pure
fan-out duplication (v1 linked one offer to every Jobs row of that company),
and 126 more came from dedup copies.

## 4. New tables / functions

- `student_branch_campus` — 2156 rows: Sector 62 948, JUIT 546,
  Sector 128 516, JUET Guna 146.
- `fn_api_sync_offer_students_v2` — one job per `(company_key, roll)`,
  `placed_at` earliest-date-wins preserved, idempotent
  (`0 inserted / 0 removed` on re-run).
- `fn_campus_resolved_v1`, `fn_role_job_score_v1`, `fn_norm_role_v1`.

## 5. Gates

| Gate | Before | After |
|---|---|---|
| `e2e_regression.py` | 5 of 11 FAIL | **12 / 12 PASS (exit 0)** |
| `run_backend_validation.py` | n/a (crashed on `gate=` kwarg) | **PASS — 18/18 parser, 33/33 golden, 8/8 integrity, fan_out 1.00** |
| `pytest` | 315 passed | **315 passed** |
| `tsc --noEmit` | exit 0 | **exit 0** |
| `vite build` | not run | **exit 0** |

### The data-trust gate

Every one of **19 034 `(email, roll)` pairs** is a literal substring of that
email's own body/attachments — 0 invented, 0 with no source text. The inverse
direction (rules parser keeps a student the DB lost) is 0 over 103 mails, and
**0 stored student sits on a line the mail marks `REJECTED`/`NO_SHOW`** — the
217 rejected HackWithInfy rows never reach a congratulations view.

## 6. Known limitations (accepted)

- **6 companies / 10 students intentionally unmapped**: LinkedIn (2),
  PayPal (2), Meritshot (2), Rockwell Automation (2), NXP (1),
  Penthara Technologies (1) — signed off as no `jobs` row; the gate carries
  them as an allow-list so a *new* unmapped company still fails.
- **`22803xxx` → `"Other"`** admission-year config gap (14 rolls), pinned as a
  deliberate PASS until the range itself is decided.
- **College/email fill ~18%/16%** — deterministic row restore only.
- DeepSeek 4/4 HTTP 402; one DeepSeek key was leaked into an older transcript
  and rotation was never confirmed.
