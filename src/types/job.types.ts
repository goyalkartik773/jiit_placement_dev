/**
 * ============================================================================
 * EXACT backend API contract — DO NOT invent fields.
 * ============================================================================
 *
 * Source of truth (traced live):
 *   Database  -> PostgreSQL fns: fn_api_select_jobs_v1 / fn_api_select_jobdetail_v1
 *   Backend   -> JIITPlacement/Controllers/JobController.cs
 *   Verified  -> live against http://localhost:5104
 *
 * Endpoint map:
 *   GET /api/jobs?page&pageSize&company&search   -> JobsListEnvelope
 *   GET /api/jobs/{id}                           -> JobDetailEnvelope (id = job UUID
 *                                                   or supersetjobidentifier)
 *   GET /api/jobs/{jobId}/documents/{documentId} -> raw file bytes
 *                                                  (Content-Disposition: attachment)
 *
 * NOTE: the backend spells the eligibility keys "eligiblitymarks" and
 * "eligiblitycourses" (missing "e"). These keys are used EXACTLY as returned.
 */

/** Standard backend response wrapper: { status, Message, Data } */
export interface ApiEnvelope<T> {
  status: boolean;
  Message: string;
  Data: T | null;
}

/** GET /api/jobs -> Data */
export interface JobsListData {
  Items: JobListItem[] | null;
  TotalCount: number;
  Page: number;
  PageSize: number;
  TotalPages: number;
}

/** GET /api/jobs/{id} -> Data */
export interface JobDetailEnvelope {
  status: string; // "SUCCESS" | "ERROR"
  message?: string;
  data: JobDetail;
}

/** Child row: jobeligibilities (returned as "eligiblitymarks") */
export interface EligibilityMark {
  id: string;
  sysjobuuid: string;
  level: string;
  criteria: string; // TEXT in DB, e.g. "6"
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Child row: jobeligibilitycourses (returned as "eligiblitycourses") */
export interface EligibilityCourse {
  id: string;
  sysjobuuid: string;
  coursename: string;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Child row: jobgenders */
export interface AllowedGender {
  id: string;
  sysjobuuid: string;
  gender: string;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Child row: jobskills */
export interface RequiredSkill {
  id: string;
  sysjobuuid: string;
  skillname: string;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Child row: jobhiringflows (ordered by sequence by the API) */
export interface HiringFlowStage {
  id: string;
  sysjobuuid: string;
  sequence: string; // TEXT in DB, e.g. "1"
  stagename: string;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Child row: jobdocuments */
export interface JobDocument {
  id: string;
  sysjobuuid: string;
  documentidentifier: string;
  documentname: string;
  documentpath: string; // server-relative path — never exposed as a link
  contenttype: string;
  filesize: number;
  status: string;
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** Fields shared by list items and the detail object (jobs table columns) */
export interface JobCore {
  id: string;
  supersetjobidentifier: string;
  company: string;
  jobprofile: string;
  placementcategory: string;
  placementcategorycode: string;
  content: string; // present in contract; currently empty for all jobs
  createdat: string | null;
  deadline: string | null;
  location: string;
  /** Annual CTC in INR (backend: "8 LPA" = 800000). May be 0. */
  package: number | null;
  packageinfo: string; // additional CTC info text (empty for most jobs)
  /** Full job description — rich HTML (present for every current job). */
  jobdescription: string;
  placementtype: string; // present in contract; currently empty for all jobs
  status: string; // e.g. "Active"
  posteddatetime: string | null;
  updateddatetime: string | null;
}

/** GET /api/jobs item — includes marks + documents, NOT the other child tables */
export interface JobListItem extends JobCore {
  eligiblitymarks: EligibilityMark[] | null;
  documents: JobDocument[] | null;
}

/** GET /api/jobs/{id} -> Data.data — every child table included */
export interface JobDetail extends JobCore {
  eligiblitymarks: EligibilityMark[] | null;
  eligiblitycourses: EligibilityCourse[] | null;
  allowedgenders: AllowedGender[] | null;
  requiredskills: RequiredSkill[] | null;
  hiringflow: HiringFlowStage[] | null;
  documents: JobDocument[] | null;
}

/** Query params accepted by GET /api/jobs (server-side) */
export interface JobListParams {
  page?: number;
  pageSize?: number;
  company?: string;
  search?: string;
}
