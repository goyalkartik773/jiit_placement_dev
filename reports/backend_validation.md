# Backend validation report

Generated: 2026-09-28T18:35:04+00:00  
Golden samples: 33  
Support seeds (revision parent, not scored): `19fdbe578d2f0ea7`  
Mode: deterministic (rule-based); LLM fallback disabled

## 1. Summary

| Suite | Result |
|---|---|
| Pipeline parser GT (18 samples) | 18/18 samples, 99/99 checks |
| Golden taxonomy + DB rows | 33/33 samples, 99/99 checks |
| Reprocess idempotency (golden) | identical derived row counts |

**Overall: PASS**

## 2. Golden taxonomy samples

| # | gmail id | taxonomy GT | actual | checks | verdict | subject |
|---|---|---|---|---|---|---|
| 1 | `1a07f91284991c5c` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 37=ok; company == Infosys=ok | PASS | Infosys Niche Roles (SP & DSE) Full-Time Hiring for Batch 2027 - Offer |
| 2 | `19e024fd393cbd5c` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 3=ok; company == Amazon=ok | PASS | Amazon - SDE intern (six months July-Dec 2026 ) hiring - Batch 2027 -  |
| 3 | `1a0a93a7210d64bd` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 54=ok; company == Cognizant=ok | PASS | Cognizant Mass Recruitment Drive-Hiring for Full Time Role from 2027 B |
| 4 | `1a0a47528181e0b2` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 5=ok; company == ZS Associates=ok | PASS | ZS Associates-Pre Placement Offer From Batch 2027 |
| 5 | `1a0af47cccbc929a` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 8=ok; company == smartShift Technologies=ok | PASS | smartShift Technologies - Hiring Interns from 2027 Batch - To Be Conve |
| 6 | `1a0b7ee6e5486c2a` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 4=ok; company == Keyence India=ok | PASS | Keyence India - Hiring for Full Time Role from 2027 Batch - Offers |
| 7 | `19ed55cde526a30b` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 4=ok; company == LTIMindtree=ok | PASS | Notification Regarding LTIMindtree (LTM) 2026 Batch Offers |
| 8 | `19ef8e389b433689` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students == 232=ok; company == Infosys=ok | PASS | HackWithInfy 2026 -Batch 2027 - Selection Status on 24 June 2026 |
| 9 | `1a02449f9b4a752f` | HACKATHON | HACKATHON | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; deadline == 2026-08-24=ok; links >= 1=ok; company == Decimal Point Analytics=ok | PASS | Decimal Point Analytics - DPA Vivechana 2026 – National Level Hackatho |
| 10 | `19fdbfcbc7fffaf1` | HACKATHON | HACKATHON | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; deadline == 2026-08-08=ok; revision_of -> 19fdbe578d2f0ea7=ok; company == Decimal Point Analytics=ok | PASS | Revised: Decimal Point Analytics - DPA Vivechana 2026 – National Level |
| 11 | `19efd53ceb632706` | EVENT | EVENT | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; link contains teams.microsoft.com=ok; company == LTIMindtree=ok | PASS | Reminder: LTIMindtree Guest Lecture : Enhance Your Corporate Communica |
| 12 | `19bd9bcddb127a67` | GENERAL_PLACEMENT_NOTICE | GENERAL_PLACEMENT_NOTICE | classification=ok | PASS | Placement Policy - 2027 Graduating Batches; Engineering and MCA |
| 13 | `1a06fde8ade47eab` | REGISTRATION | REGISTRATION | classification=ok; funnel counts == [393]=ok; company == Accenture=ok | PASS | Accenture-Mass Recruitment Drive - Hiring for Full Time Role from 2027 |
| 14 | `19f22a0d0b4f11e3` | HACKATHON | HACKATHON | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; deadline == 2026-07-03=ok; links >= 1=ok; link contains forms.gle=ok; company == Flipkart=ok | PASS | Flipkart GRiD 8.0 "Prompt the Future" - Batch 2027 & 2028 – Apply by 0 |
| 15 | `19f646701c4545ce` | SHORTLIST | SHORTLIST | classification=ok; shortlist_students == 1069=ok; company == Infosys=ok | PASS | Infosys - Niche Roles (SP & DSE) Hiring Drive - 2027 Batch - Registere |
| 16 | `19fe5f62bdf7f608` | SHORTLIST | SHORTLIST | classification=ok; shortlist_students == 128=ok; company == HyperVerge=ok | PASS | HyperVerge - ​Batch 2027 - Campus ​d​rive details – Shortlisted Studen |
| 17 | `19cb2021fb447e5f` | SHORTLIST | SHORTLIST | classification=ok; funnel counts == [141]=ok; company == Amazon=ok | PASS | Amazon - Hiring for Six Months Non-SDE Intern Only (Jul-Dec 2026) From |
| 18 | `19f2c3c4c248cc76` | SHORTLIST | SHORTLIST | classification=ok; shortlist_students == 50=ok; company == HCLTech=ok | PASS | HCLTech AMPlified: The AI Challenge - Shortlist received from AMPlifie |
| 19 | `1a0a9be6c4886917` | SHORTLIST | SHORTLIST | classification=ok; shortlist_students >= 1=ok; company == smartShift Technologies=ok | PASS | Reminder: smartShift Technologies - 2027 Batch - Interviews Scheduled  |
| 20 | `1a0de1fbffbe288f` | REGISTRATION | REGISTRATION | classification=ok | PASS | LTM 2027 Batch Mass Recruitment Drive \| Eligible Candidates & Registr |
| 21 | `19e5e9dccd5c44df` | REGISTRATION | REGISTRATION | classification=ok | PASS | Reminder: Amazon WoW Program - Batch 2027 - Complete Registration by 8 |
| 22 | `1977da221a01947f` | WEBINAR | WEBINAR | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok | PASS | Reminder to Join: NXP - Virtual Technical Session - MS Teams Link to A |
| 23 | `19ef835253e4abb2` | WEBINAR | WEBINAR | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; company == Tata Technologies=ok | PASS | Reminder: Tata Technologies InnoVent-27 \| Exclusive Webinar on "AI at |
| 24 | `19ef8235d0f7f88a` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students >= 1=ok | PASS | Convexicon India: Hiring interns from BTech 2027 Batch - To Be Convert |
| 25 | `1a01489d56b0abf2` | FINAL_SELECTION | FINAL_SELECTION | classification=ok; offer_students >= 1=ok | PASS | Progress Software: Hiring Interns from Batch 2027 to be converted to a |
| 26 | `1a08c0be2839d372` | SELECTION_PROCESS_NOTICE | SELECTION_PROCESS_NOTICE | classification=ok | PASS | ZS Associates-Hiring For FT Role From Batch 2027-Selection Process and |
| 27 | `1a0cf78367ab19d8` | JOB_OPPORTUNITY | JOB_OPPORTUNITY | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok | PASS | LTM - Hiring for Full Time Role from 2027 Graduating Batch - Apply for |
| 28 | `19feb02d5deaf7d1` | JOB_OPPORTUNITY | JOB_OPPORTUNITY | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok; company == Accenture=ok | PASS | Accenture - Mass Recruitment Drive - Hiring for Full Time Role from 20 |
| 29 | `19c936a5d065cb19` | UNKNOWN | UNKNOWN | classification=ok | PASS | Swiggy - Women’s Day initiative - Nominations invited from Girl Studen |
| 30 | `19fa237e5be9b398` | WORKSHOP | WORKSHOP | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok | PASS | Quokka Labs Virtual One Hour Workshop on Hands-On AI Security - Apply  |
| 31 | `19fd18f003ea816b` | INTERNSHIP_OPPORTUNITY | INTERNSHIP_OPPORTUNITY | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok | PASS | Amazon - Hiring for Six Months Non-SDE Intern Only (Jan-June 2027) Fro |
| 32 | `1a03921a2eb2c90e` | HACKATHON | HACKATHON | classification=ok; opportunity row=ok; opportunity.event_type == gt=ok | PASS | HCLTech AMPlified: The AI Challenge – Batch 2027 & 2028 - Round 1 - Re |
| 33 | `19ceb40eacf5406f` | WEBINAR | WEBINAR | classification=ok | PASS | Bounteous x Accolite - 2027 - Webinar on "Beginners guide to working w |

## 3. Pipeline parser ground truth (18 samples)

| # | gm id | checks passed | verdict |
|---|---|---|---|
| 1 | `1a07f91284991c5c` | 4/4 | PASS |
| 2 | `19e024fd393cbd5c` | 6/6 | PASS |
| 3 | `1a0a93a7210d64bd` | 6/6 | PASS |
| 4 | `1a0a47528181e0b2` | 6/6 | PASS |
| 5 | `1a0af47cccbc929a` | 5/5 | PASS |
| 6 | `1a0b7ee6e5486c2a` | 6/6 | PASS |
| 7 | `19ed55cde526a30b` | 4/4 | PASS |
| 8 | `19ef8e389b433689` | 5/5 | PASS |
| 9 | `1a02449f9b4a752f` | 8/8 | PASS |
| 10 | `19fdbfcbc7fffaf1` | 6/6 | PASS |
| 11 | `19efd53ceb632706` | 7/7 | PASS |
| 12 | `19bd9bcddb127a67` | 4/4 | PASS |
| 13 | `1a06fde8ade47eab` | 6/6 | PASS |
| 14 | `19f22a0d0b4f11e3` | 6/6 | PASS |
| 15 | `19f646701c4545ce` | 5/5 | PASS |
| 16 | `19fe5f62bdf7f608` | 5/5 | PASS |
| 17 | `19cb2021fb447e5f` | 6/6 | PASS |
| 18 | `19f2c3c4c248cc76` | 4/4 | PASS |

## 4. Corpus classification distribution (all processed emails)

| classification | emails |
|---|---|
| SHORTLIST | 137 |
| FINAL_SELECTION | 91 |
| HACKATHON | 90 |
| REGISTRATION | 50 |
| EVENT | 44 |
| UNKNOWN | 43 |
| GENERAL_PLACEMENT_NOTICE | 42 |
| SELECTION_PROCESS_NOTICE | 28 |
| INTERNSHIP_OPPORTUNITY | 27 |
| WEBINAR | 21 |
| JOB_OPPORTUNITY | 20 |
| WORKSHOP | 5 |
| OFF_CAMPUS_OPPORTUNITY | 0 |
| IRRELEVANT | 0 |
| **total** | **598** |

Categories with zero corpus samples - rules are covered by unit tests only: `OFF_CAMPUS_OPPORTUNITY`, `IRRELEVANT`.

## 5. Derived row totals (entire database) after two golden reprocesses

| table | run 1 | run 2 | identical |
|---|---|---|---|
| offers | 91 | 91 | yes |
| offer_students | 909 | 909 | yes |
| shortlist_events | 185 | 185 | yes |
| shortlist_students | 19276 | 19276 | yes |
| funnel_counts | 12 | 12 | yes |
| opportunities | 229 | 229 | yes |

## 6. Recorded live-scale idempotency proofs

```
Sync run 1   : 1146 fetched, 364 new, 782 duplicates, 0 failed, 417.9s
Sync re-run  : 1146 fetched,   0 new, 1146 duplicates, 0 failed,  17.9s
Process runs : 596/596 twice, 0 failed; derived row counts identical
               offers 94, offer_students 895, shortlist_events 184,
               shortlist_students 19276, funnel_counts 12,
               opportunities 229, student_placement_events 20171
Error case   : Codestore 1a0c23cae824d3fb failed once (isolated),
               fixed parser edge case -> 596/596 on re-run
```
