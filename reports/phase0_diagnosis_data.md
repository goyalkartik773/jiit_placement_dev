# Phase 0 - diagnosis: `FINAL_SELECTED` / `OFFERED` vs the source email

Read-only cross-check of every `offer_students` row that feeds a `FINAL_SELECTED` / `OFFERED` event, matched back to the student's own line inside the real email body.

## Headline numbers

- offer rows examined (source email classified `FINAL_SELECTION`): **822**
- rows the source email really does present as an offer: **604**
- rows wrongly presented as an offer: **218** (26.5%)
- distinct students whose *only* `FINAL_SELECTED`/`OFFERED` evidence is such a wrong row: **119**
- `job_placed_students` rows served to the college UI today: **906**

## Confirmed misclassifications by failure mode

| # | Failure mode | Rows | Notes |
|---|---|---|---|
| 1 | C: row from a non-offer section (pending/round-progress table) has no status cell and defaulted to FINAL_SELECTED | 198 | see per-email table below |
| 2 | C: status cell denies offer, row still defaulted to FINAL_SELECTED/OFFERED | 20 | see per-email table below |

## Affected source emails

| Email | Subject | Wrong rows | OK rows |
|---|---|---|---|
| `f179d24d5b15` | HackWithInfy 2026 -Batch 2027 - Selection Status on 24 June 2026 | 208 | 5 |
| `3dcef64dc086` | Fwd: HackWithInfy 2026 -Batch 2027 - Selection Status on 31 August 2026 | 10 | 6 |

## Failure-mode probes (corpus-wide)

- body says "selected for the next round" / "students selected for", by classification: `{}`
- subject says shortlist, by classification: `{'SHORTLIST': 84, 'SELECTION_PROCESS_NOTICE': 2}`
- per-row status cells that deny an offer, and what the pipeline wrote:

| Status cell in email | Written as | Rows |
|---|---|---|
| `REJECTED NA` | `REJECTED` | 34 |
| `NO_SHOW NA` | `FINAL_SELECTED` | 20 |
| `REJECTED` | `REJECTED` | 17 |

- emails with `dedup_of`/`revision_of`/non-canonical: `[21]` (non-canonical emails holding offer rows: 9)
- students holding both a `final_selection` and an `offer` event for the same company (dedup merge candidates): `18`
- marked students whose evidence came from a non-canonical / dedup / revision copy of a message: `74`
- marked events that no longer join back to an `offer_students` row: `18`
- `job_placed_students` mappings built from a row whose status cell denies an offer (REJECTED / NO_SHOW): `109`

### Classification rules that fired, by classification

| Classification | Rule | Emails |
|---|---|---|
| FINAL_SELECTION | parser:body:offer-evidence ('Congratulations') | 86 |
| SHORTLIST | parser:subject:shortlist-shortlist | 84 |
| HACKATHON | parser:subject:opportunity-event | 43 |
| EVENT | parser:subject:opportunity-event | 27 |
| INTERNSHIP_OPPORTUNITY | parser:subject:opportunity-apply | 20 |
| HACKATHON | parser:subject:opportunity-register | 18 |
| REGISTRATION | parser:subject:shortlist-registration-stage | 17 |
| WEBINAR | parser:subject:opportunity-event | 17 |
| SHORTLIST | parser:subject:shortlist-assessment | 16 |
| HACKATHON | parser:subject:opportunity-apply | 16 |
| JOB_OPPORTUNITY | parser:subject:opportunity-hiring | 15 |
| SHORTLIST | parser:subject:shortlist-list-of-students | 14 |
| UNKNOWN | parser:subject:admin ('Internship Joining From') | 14 |
| EVENT | parser:subject:opportunity-register | 10 |
| GENERAL_PLACEMENT_NOTICE | parser:fallback:other | 9 |
| SHORTLIST | parser:subject:shortlist-interview-round | 8 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Interaction with Head') | 8 |
| REGISTRATION | parser:subject:opportunity-apply | 7 |
| HACKATHON | parser:subject:opportunity-challenge-season | 7 |
| REGISTRATION | parser:subject:opportunity-register | 6 |
| REGISTRATION | parser:subject:shortlist-list-of-students | 5 |
| SHORTLIST | parser:subject:shortlist-physical-process | 5 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Submit Summer Internship') | 5 |
| UNKNOWN | parser:fallback:other | 5 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('PLACEMENT ACTIVITIES') | 4 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-registration-stage | 4 |
| JOB_OPPORTUNITY | parser:subject:opportunity-register | 4 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-assessment | 4 |
| SELECTION_PROCESS_NOTICE | parser:body:list-label ('Reporting Time') | 4 |
| INTERNSHIP_OPPORTUNITY | parser:subject:opportunity-hiring | 4 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-selection-status | 3 |
| UNKNOWN | parser:subject:admin ('Internshala') | 3 |
| SELECTION_PROCESS_NOTICE | parser:subject:admin ('Mock Interview') | 3 |
| REGISTRATION | parser:subject:shortlist-company-registration | 3 |
| WORKSHOP | parser:subject:opportunity-event | 3 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-interview-round | 3 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Soft Skills') | 3 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Nomination') | 3 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Submission of') | 3 |
| SELECTION_PROCESS_NOTICE | parser:fallback:other | 3 |
| REGISTRATION | parser:subject:opportunity-event | 3 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Industrial Visit') | 3 |
| EVENT | parser:subject:opportunity-hiring | 3 |
| SHORTLIST | parser:body:list-label ('reporting time') | 2 |
| UNKNOWN | parser:subject:admin ('Debarr') | 2 |
| SHORTLIST | parser:subject:shortlist-lab-allocation | 2 |
| WORKSHOP | parser:body:opportunity ('to register') | 2 |
| EVENT | parser:subject:opportunity-opportunity | 2 |
| UNKNOWN | parser:subject:opportunity-register | 2 |
| FINAL_SELECTION | parser:body:offer-evidence ('have been offered') | 2 |
| UNKNOWN | parser:subject:admin ('Industrial Visit') | 2 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('ADMINISTRATIVE INSTRUCTIONS') | 2 |
| HACKATHON | parser:subject:opportunity-volunteer | 2 |
| FINAL_SELECTION | parser:body:offer-evidence ('has been offered') | 2 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-shortlist | 2 |
| FINAL_SELECTION | parser:subject:offer-offers | 2 |
| HACKATHON | parser:body:opportunity ('Click here to register') | 2 |
| SHORTLIST | parser:subject:shortlist-invited | 2 |
| SHORTLIST | parser:body:list-label ('Following students') | 2 |
| REGISTRATION | parser:subject:opportunity-prep | 2 |
| UNKNOWN | parser:subject:admin ('Submission of') | 1 |
| FINAL_SELECTION | parser:body:offer-evidence ('congratulations') | 1 |
| WEBINAR | parser:subject:opportunity-volunteer | 1 |
| UNKNOWN | parser:subject:admin ('Nomination') | 1 |
| EVENT | parser:subject:opportunity-volunteer | 1 |
| UNKNOWN | parser:subject:admin ('SAP Learning') | 1 |
| JOB_OPPORTUNITY | parser:subject:opportunity-apply | 1 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('Placement Policy') | 1 |
| FINAL_SELECTION | parser:body:offer-evidence ('CONGRATULATIONS') | 1 |
| SHORTLIST | parser:subject:shortlist-drive-labs | 1 |
| UNKNOWN | parser:subject:admin ('Updating Personal') | 1 |
| INTERNSHIP_OPPORTUNITY | parser:subject:opportunity-register | 1 |
| HACKATHON | parser:subject:opportunity-opportunity | 1 |
| INTERNSHIP_OPPORTUNITY | parser:subject:opportunity-event | 1 |
| INTERNSHIP_OPPORTUNITY | parser:subject:opportunity-opportunity | 1 |
| REGISTRATION | parser:subject:admin ('SAP Learning') | 1 |
| REGISTRATION | parser:fallback:other | 1 |
| WEBINAR | parser:subject:opportunity-register | 1 |
| GENERAL_PLACEMENT_NOTICE | parser:subject:admin ('MOOCs') | 1 |
| SHORTLIST | parser:body:list-label ('shortlisted students') | 1 |
| HACKATHON | parser:subject:opportunity-hiring | 1 |
| REGISTRATION | parser:subject:opportunity-challenge-season | 1 |
| SELECTION_PROCESS_NOTICE | parser:subject:admin ('Guidelines For') | 1 |
| WEBINAR | parser:subject:opportunity-apply | 1 |
| UNKNOWN | parser:subject:admin ('Guidelines for') | 1 |
| REGISTRATION | parser:subject:opportunity-hiring | 1 |
| REGISTRATION | parser:subject:shortlist-drive-labs | 1 |
| UNKNOWN | parser:subject:admin ('Submit Willingness') | 1 |
| UNKNOWN | parser:subject:admin ('Beyond the Degree') | 1 |
| EVENT | parser:subject:opportunity-apply | 1 |
| REGISTRATION | parser:body:opportunity ('participate in') | 1 |
| WEBINAR | parser:subject:admin ('Submit willingness') | 1 |
| UNKNOWN | parser:subject:admin ('Submit Summer Internship') | 1 |
| UNKNOWN | parser:subject:admin ('Instructions for') | 1 |
| UNKNOWN | parser:subject:admin ('Mock Interview') | 1 |
| UNKNOWN | parser:subject:admin ('Submit willingness') | 1 |
| SELECTION_PROCESS_NOTICE | parser:subject:shortlist-physical-process | 1 |

## Sample of wrongly-marked students

| Roll | Name | Written as | Status cell in email | Section title | Email |
|---|---|---|---|---|---|
| 9923103164 | Shaurya Goyal | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 9923103176 | Vansh N/a | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23102009 | Aayush Bansal | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23103222 | Krishna Seth | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23103061 | Aryan Kushwah | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23104019 | Ansh Pandey | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23102034 | Dhairya Pandey | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 9923103031 | Krishna Agarwal | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23103349 | Mukund Nigam | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 23104051 | Vaibhav Singh | FINAL_SELECTED | NO_SHOW NA | JU-Anoopshahr | `f179d24d5b15` |
| 22802014 | Hardik Singh | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803001 | Yuvraj Rathi | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803005 | Divyansh Bansal | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803013 | Praveen Kumar | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803014 | Tanmay Butta | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803015 | Lakshya Veer Singh | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803017 | Pranav Kumar | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803020 | Deepanshu Singhal | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803023 | Raghuvansh Rastogi | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 22803026 | Ashutosh Tandon | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102027 | Laukik Saxena | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102044 | Sameer Monga | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102079 | Nimisha Sharma | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102085 | Sumit Sourabh | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102088 | Priyanshu Bhardwaj | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102113 | Yash Chaudhary | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23102207 | Shivendra Kushwaha | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103021 | Arpit Saxena | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103022 | Arjun Gupta | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103036 | Tushar Jaiman | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103038 | Yashi Singh | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103042 | Yash Chaudhary | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103050 | Shivam Gupta | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103059 | Aritra Majee | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103064 | Uday Kumar | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103077 | Akshit Gupta | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103082 | Prish Keshari | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103102 | Dhruv Rawat | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103105 | Krishna Singhal | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |
| 23103107 | Dhruv Khanna | FINAL_SELECTED | (none) | List of Students' status of pending Interviews as on 24 June | `f179d24d5b15` |

_Generated by `scripts/phase0_diagnose.py` (read-only)._
