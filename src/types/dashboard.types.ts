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
