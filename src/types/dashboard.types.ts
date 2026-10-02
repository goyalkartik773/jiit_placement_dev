/**
 * ============================================================================
 * EXACT backend API contract - DO NOT invent fields.
 * ============================================================================
 *
 * Source of truth (traced live against http://localhost:5104):
 *   Backend -> JIITPlacement/Controllers/PlacementController.cs
 *              JIITPlacement/Controllers/NoticeController.cs
 *
 * Endpoint map:
 *   GET /api/placements/company-wise?page&pageSize&search -> CompanyWiseListData
 *   GET /api/placements/jobs/{jobId}/placed-students      -> ApiEnvelope<PlacedStudentsData>
 *                                                            (404 -> { status:false,
 *                                                              Message:"Job not found" })
 *   GET /api/notices/email?page&pageSize&search&type      -> EmailNoticeListData
 *   GET /api/notices?page&pageSize&search                 -> SupersetNoticeListData
 *
 * All four answer with the shared wrapper { status, Message, Data }
 * (ApiEnvelope<T> from job.types.ts) - Data may be null with status = true.
 *
 * NOTE: the `type` filter of the email feed must be sent UPPERCASE
 * (e.g. "SHORTLIST"); `Facets` reflect the current `search` but ignore `type`.
 * The email feed intentionally EXCLUDES congratulation / final-offer emails - 
 * that data is surfaced by GET /api/placements/company-wise instead.
 *
 * The admin offer-student sync (POST /api/admin/jobs/sync-offer-students)
 * answers with { success, message, ... } and lives in admin.types.ts.
 */

/** Query params accepted by GET /api/placements/company-wise (all server-side). */
export interface CompanyWiseParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

/** One job row nested under a company (jobs table subset). */
export interface CompanyJob {
  id: string;
  company: string;
  jobprofile: string;
  /** Annual CTC in INR (0 = undisclosed, e.g. 5600000). */
  package: number;
  packageinfo: string;
  location: string;
  deadline: string | null;
  status: string;
  posteddatetime: string | null;
}

/** Offered role breakdown for one company (aggregated over offer students). */
export interface CompanyRole {
  role: string;
  students: number;
  /** Highest CTC seen for this role, in INR (may be null). */
  ctcmax: number | null;
}

/**
 * Branch / campus breakdown for one company.
 *
 * Both are resolved per DISTINCT (company, student) - i.e. they always sum to
 * `placedstudents`, never to the raw `job_placed_students` row count.
 * `branch` is the enrollment-range rule, with the email's own ``Branch`` cell
 * filling the ranges the config does not cover. `campus` is the
 * roll's `99` campus prefix (Sector 62 / Sector 128), overridden only when the
 * ``University`` cell names a different institution (JUET Guna).
 */
export interface CompanyBreakdown {
  branch?: string;
  campus?: string;
  students: number;
}

/** GET /api/placements/company-wise item - one company + its jobs + its roles. */
export interface CompanyRow {
  company: string;
  jobcount: number;
  activejobs: number;
  placedstudents: number;
  /** Null while the company has no placed student yet. */
  firstplacedat: string | null;
  lastplacedat: string | null;
  jobs: CompanyJob[] | null;
  roles: CompanyRole[] | null;
  /**
   * Branch split of the placed students. Optional: older backends omit it,
   * and it is `[]` while nothing is mapped yet.
   */
  branches?: CompanyBreakdown[] | null;
  /** Campus split (Sector 62 / Sector 128 / JUIT / JUET Guna). */
  campuses?: CompanyBreakdown[] | null;
}

/** GET /api/placements/company-wise -> Data */
export interface CompanyWiseListData {
  Items: CompanyRow[] | null;
  TotalCount: number;
  Page: number;
  PageSize: number;
  TotalPages: number;
}

/** One job as returned by the placed-students endpoint. */
export interface PlacedJob {
  id: string;
  supersetjobidentifier: string;
  company: string;
  jobprofile: string;
  /** Annual CTC in INR (0 = undisclosed). */
  package: number;
  packageinfo: string;
  location: string;
  deadline: string | null;
  status: string;
  posteddatetime: string | null;
}

/** One student matched to an offer email. Nullable columns stay nullable. */
export interface PlacedStudent {
  id: string;
  rollno: string;
  studentname: string;
  companyname: string;
  placedat: string;
  offeremailid: string;
  branch: string | null;
  /**
   * Derived server-side from `rollno` by the enrollment-range lookup, never
   * stored (`fn_branch_from_roll_v1`). Added as an OPTIONAL field alongside the
   * extraction-sourced `branch` above so the two can be compared. Older rows /
   * older backends simply omit it.
   */
  branchfromroll?: string | null;
  /** Admission / batch year derived from the roll prefix (2023, 2024, ...). */
  batchyear?: number | null;
  /**
   * Campus derived from the roll's two-digit `99` prefix (Sector 62 vs
   * Sector 128), overridden only when the offer table's ``University`` cell
   * names a different institution (JUET Guna). This is the display value.
   */
  campus?: string | null;
  /** Roll-rule answer alone, kept so it can be compared with `campus`. */
  campusfromroll?: string | null;
  /** The ``University`` cell exactly as the email carried it (may be blank). */
  campusextracted?: string | null;
  /**
   * `role` canonicalised for grouping (`fn_norm_role_v1`): wrapped cells are
   * rejoined and "(L1, L2, L3)" becomes "(L1 / L2 / L3)", so the same role
   * family renders as one row instead of two identical-looking ones.
   */
  rolelevel?: string | null;
  program: string | null;
  email: string | null;
  role: string | null;
  /** Raw CTC text from the offer mail, e.g. "INR 21 LPA". */
  ctcraw: string | null;
  ctctotal: number | null;
  ctcbasis: string | null;
  stipend: number | null;
  employmenttype: string | null;
  offersubject: string | null;
  offerreceivedat: string | null;
}

/** GET /api/placements/jobs/{jobId}/placed-students -> Data */
export interface PlacedStudentsData {
  job: PlacedJob;
  placedCount: number;
  students: PlacedStudent[] | null;
}

/** Query params accepted by GET /api/notices/email (all server-side). */
export interface EmailNoticeParams {
  page?: number;
  pageSize?: number;
  search?: string;
  /** Uppercase classification (e.g. "SHORTLIST"); empty = all types. */
  type?: string;
}

/** One facet bucket returned alongside the email notices. */
export interface NoticeFacet {
  classification: string;
  count: number;
}

/** One parsed placement email (congratulation / final-offer mail excluded). */
export interface EmailNotice {
  id: string;
  gmailmessageid: string;
  subject: string;
  snippet: string;
  sender: string;
  senderemail: string;
  receivedat: string;
  classification: string;
  /** Human label for `classification` (e.g. "Shortlist"). */
  classificationlabel: string;
  confidence: number | null;
  method: string;
  hasattachments: boolean;
  isrevision: boolean;
  company: string | null;
  headline: string | null;
  /** Date-only string (e.g. "2026-09-28") or null. */
  deadline: string | null;
  link: string | null;
  studentcount: number | null;
  rounds: NoticeRound[] | null;
}

/** One stage of the selection funnel attached to an email notice. */
export interface NoticeRound {
  round: string;
  count: number;
}

/** GET /api/notices/email -> Data */
export interface EmailNoticeListData {
  Items: EmailNotice[] | null;
  TotalCount: number;
  Page: number;
  PageSize: number;
  TotalPages: number;
  Facets: NoticeFacet[] | null;
}

/** One student named inside a shortlist email (`shortlist_students`). */
export interface NoticeStudent {
  rollno: string | null;
  name: string | null;
  branch: string | null;
  program: string | null;
  college: string | null;
  /** Raw status cell from the email ("Registered", "Not Registered", ...). */
  status: string | null;
}

/** One funnel count with the source sentence it was parsed from. */
export interface NoticeRoundDetail extends NoticeRound {
  evidence: string | null;
}

/** One attachment carried by the email (metadata only - no download API). */
export interface NoticeAttachment {
  filename: string | null;
  mimetype: string | null;
  filesize: number | null;
}

/** Miss-shape of GET /api/notices/email/{id} for an unknown id. */
export interface EmailNoticeDetailMiss {
  found: false;
}

/**
 * GET /api/notices/email/{id} -> Data (the "Read more" payload).
 * Everything the list ships, PLUS the full body (capped server-side at
 * 60,000 chars - compare `bodylength` to detect truncation), recipients,
 * the parsed student rows, funnel counts with evidence and attachments.
 */
export interface EmailNoticeDetail extends EmailNotice {
  found: true;
  recipient: string | null;
  cc: string | null;
  /** Full body text (quote-stripped), capped at 60,000 chars. */
  body: string;
  /** Length of the untouched body, before the cap. */
  bodylength: number;
  /** Normalized stage enum ("SHORTLISTED", "TEST_SHORTLISTED", ...). */
  stage: string | null;
  /** Stage exactly as the email worded it. */
  stageraw: string | null;
  /** ISO datetimes of interviews / reporting mentioned in the email. */
  interviewdates: string[] | null;
  /** Sentence(s) the shortlist extraction came from. */
  evidence: string | null;
  careernote: string | null;
  /** Ordered stage labels of an opportunity email ("Round 1", ...). */
  stages: string[] | null;
  eligibility: string[] | null;
  rounds: NoticeRoundDetail[] | null;
  students: NoticeStudent[] | null;
  attachments: NoticeAttachment[] | null;
}

/** Query params accepted by GET /api/notices (all server-side). */
export interface SupersetNoticeParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

/** GET /api/notices item - a notice synced from the Superset job portal. */
export interface SupersetNotice {
  id: string;
  supersetidentifier: string;
  title: string;
  /**
   * Notice body. The contract calls it plain text, but live rows carry HTML
   * markup - convert with htmlToPlainText() before rendering (never with
   * dangerouslySetInnerHTML).
   */
  content: string;
  author: string;
  createdat: string | null;
  updatedat: string | null;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** GET /api/notices -> Data */
export interface SupersetNoticeListData {
  Items: SupersetNotice[] | null;
  TotalCount: number;
  Page: number;
  PageSize: number;
  TotalPages: number;
}

/* -------------------------------------------------------------------------- */
/* Branch-wise statistics — GET /api/placements/branch-stats                    */
/* All figures are computed by fn_api_select_branch_stats_v1.                   */
/* -------------------------------------------------------------------------- */

/**
 * One JIIT-official CTC band of the distribution. `students` counts DISTINCT
 * students (one figure each — their best disclosed offer), never offers.
 * Bands: "Upto 5.99 L" / "6.00 - 12.99 L" / "13.00 L and above" /
 * "Not disclosed" (no offer ever spelled out a CTC — NOT the same as 0).
 */
export interface BranchStatBand {
  band: string;
  students: number;
}

/**
 * One bucket of the Analytics distribution. Counted in OFFERS (the tab's
 * y-axis is offers, not heads), fifteen FIXED edges — 0-3 / 3-4 / 4-5 / 5-6 /
 * 6-8 / 8-10 / 10-12 / 12-15 / 15-20 / 20-25 / 25-30 / 30-40 / 40-50 / 50+
 * LPA, then the honest "Not disclosed" tail so the columns still sum to
 * `totaloffers`. Edges live in `fine_bands` in
 * `JIITPlacement/SQL/migration_branch_stats.sql` and are not configurable.
 */
export interface BranchStatFineBand {
  band: string;
  offers: number;
}

/** Shared shape of a branch row and of the all-branches `totals` row. */
export interface BranchStatsSummary {
  /** Hardcoded head-count denominator the placement rate is divided by. */
  totalstudents: number;
  placedstudents: number;
  /** 0–100, rounded server-side to 2 decimals. */
  placementpercentage: number;
  totaloffers: number;
  companies: number;
  /** How many of `placedstudents` had a disclosed CTC — the package figures
   *  are averaged over this subset only, so a low count means a wide spread. */
  studentswithpackage: number;
  /** LPA. Null when no offer in that group disclosed a CTC (render "—"). */
  averagepackage: number | null;
  medianpackage: number | null;
  highestpackage: number | null;
  distribution: BranchStatBand[];
  /** The fifteen fine CTC buckets above (Analytics). Additive: older payloads
   *  without it must still render — guard with `?? []`. */
  finedistribution?: BranchStatFineBand[];
}

export interface BranchStat extends BranchStatsSummary {
  /** One of CSE / ECE / IT / BT / Intg. MTech / EC-ACT / EE-VLSI. */
  branch: string;
}

/** One month bucketed on `emails.received_at` (ISO YYYY-MM, always sorted). */
export interface BranchTimelinePoint {
  month: string;
  offers: number;
  students: number;
  /** Overall timeline only; the per-branch series omits it. */
  companies?: number;
  /** Package overlay for this bucket ONLY — one figure per head per bucket,
   *  so a later better offer never leaks backwards into an earlier month.
   *  0 when nobody in the bucket disclosed a CTC; then the rates are null. */
  studentswithpackage?: number;
  /** LPA. Null when no offer in the bucket disclosed a CTC (render "—"). */
  averagepackage?: number | null;
  medianpackage?: number | null;
  /**
   * CUMULATIVE twin of the three above: every figure landed by the END of this
   * bucket, folded to one per head, then averaged / medianed over that pool.
   * Supplied by SQL rather than derived here on purpose — a cumulative median
   * cannot be recovered from per-month medians, and a cumulative average from
   * per-month averages would be wrong whenever the bucket sizes differ.
   */
  cumstudentswithpackage?: number;
  cumaveragepackage?: number | null;
  cummedianpackage?: number | null;
  /** Running total of offers up to and including this bucket (exact — every
   *  offer falls in exactly one bucket, so a plain prefix sum is correct). */
  cumoffers?: number;
  /** DISTINCT students up to and including this bucket. Also computed in SQL:
   *  prefix-summing the per-bucket `students` would double-count anyone who
   *  appears in two months (360 against a 345-student cohort). */
  cumstudents?: number;
}

/**
 * One day bucket (ISO YYYY-MM-DD) of the timeline's Day granularity. Same
 * counters and the same package overlay as {@link BranchTimelinePoint}; the
 * name only differs because the key is `day`.
 */
export interface BranchTimelineDayPoint {
  day: string;
  offers: number;
  students: number;
  companies?: number;
  studentswithpackage?: number;
  averagepackage?: number | null;
  medianpackage?: number | null;
  /** See {@link BranchTimelinePoint.cumaveragepackage}. */
  cumstudentswithpackage?: number;
  cumaveragepackage?: number | null;
  cummedianpackage?: number | null;
  /** See {@link BranchTimelinePoint.cumoffers} / {@link BranchTimelinePoint.cumstudents}. */
  cumoffers?: number;
  cumstudents?: number;
}

/** The same bucket tagged with its branch (one row per branch per month). */
export interface BranchTimelineSeriesPoint extends BranchTimelinePoint {
  branch: string;
}

/** GET /api/placements/branch-stats -> Data */
export interface BranchStatsData {
  batch: string;
  graduatingbatch: number;
  generatedat: string;
  /** Every package field in this payload is expressed in this unit ("LPA"). */
  currency: string;
  branches: BranchStat[];
  totals: BranchStatsSummary;
  timeline: BranchTimelinePoint[];
  /** Same counters at Day granularity (Analytics timeline's Month/Day switch). */
  daily?: BranchTimelineDayPoint[];
  branchtimeline: BranchTimelineSeriesPoint[];
}
