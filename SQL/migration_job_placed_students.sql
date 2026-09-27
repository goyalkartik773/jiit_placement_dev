-- ================================================================
-- Migration: Job <-> Offered-Student mapping (admin-triggered sync)
--
-- Task 1 of the dashboard work:
--   * job_placed_students  : relation table (job x placed student)
--   * fn_api_sync_offer_students_v1()              : the matching run
--   * fn_api_select_placed_students_v1(_jobid)     : students of one job
--   * fn_api_select_company_placements_v1(...)     : company-wise rollup
--   * fn_api_select_email_notices_v1(...)          : Gmail notices feed
--
-- Matching rules (agreed):
--   * company match only - NEVER create/guess a job. An offer company that
--     has no row in "jobs" is counted in "companiesSkipped" and ignored.
--   * company comparison is normalised (trim + collapse spaces + lowercase
--     + drop ONE trailing parenthetical, e.g. "Josh Technology Group (JTG)"
--     == "Josh Technology Group"). A job row IS a company listing, so an
--     offered student maps to every job row of that company.
--   * idempotent: UNIQUE (job_id, student_roll_no) + ON CONFLICT DO NOTHING,
--     so re-running the sync never inserts a duplicate mapping.
-- ================================================================

-- 1. Normalised company key (single source of truth for both sides)
CREATE OR REPLACE FUNCTION fn_norm_company_v1(_name text) RETURNS text AS $function$
BEGIN
    RETURN lower(regexp_replace(
        regexp_replace(trim(COALESCE(_name, '')), '\s+', ' ', 'g'),
        '\s*\([^()]*\)$', ''));
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 2. Relation table
CREATE TABLE IF NOT EXISTS job_placed_students (
    id text NOT NULL DEFAULT (gen_random_uuid()::text),
    job_id text NOT NULL,
    student_roll_no text NOT NULL,
    student_name text,
    offer_email_id text NOT NULL,
    company_name text,
    placed_at timestamp with time zone NOT NULL DEFAULT NOW(),
    CONSTRAINT PK_job_placed_students PRIMARY KEY (id),
    CONSTRAINT UQ_job_placed_students UNIQUE (job_id, student_roll_no),
    CONSTRAINT FK_job_placed_students_jobs FOREIGN KEY (job_id)
        REFERENCES jobs(id) ON DELETE CASCADE,
    CONSTRAINT FK_job_placed_students_emails FOREIGN KEY (offer_email_id)
        REFERENCES emails(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS IX_job_placed_students_job_id ON job_placed_students (job_id);
CREATE INDEX IF NOT EXISTS IX_job_placed_students_roll_no ON job_placed_students (student_roll_no);
CREATE INDEX IF NOT EXISTS IX_job_placed_students_offer_email_id ON job_placed_students (offer_email_id);
CREATE INDEX IF NOT EXISTS IX_job_placed_students_company_name ON job_placed_students (company_name);
CREATE INDEX IF NOT EXISTS IX_job_placed_students_placed_at ON job_placed_students (placed_at);

-- 3. Sync: map every offered student onto the Jobs rows of his/her company.
--    Returns the run statistics as JSON.
CREATE OR REPLACE FUNCTION fn_api_sync_offer_students_v1() RETURNS text AS $function$
DECLARE
    _jobs_total integer;
    _students_considered integer;
    _companies_total integer;
    _companies_matched integer;
    _companies_skipped integer;
    _candidates integer := 0;
    _inserted integer := 0;
    _duplicates integer := 0;
    _jobs_matched integer := 0;
    _students_mapped integer := 0;
    _total_mappings integer := 0;
    _result json;
BEGIN
    SELECT COUNT(*) INTO _jobs_total FROM jobs;

    -- Distinct students we could even consider (blank roll numbers are unusable)
    SELECT COUNT(DISTINCT trim(os.roll_no)) INTO _students_considered
    FROM offer_students os
    WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> '';

    -- Offer companies that exist / do not exist in the Jobs table
    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE EXISTS (
               SELECT 1 FROM jobs j WHERE fn_norm_company_v1(j.company) = oc.ckey))
    INTO _companies_total, _companies_matched
    FROM (SELECT DISTINCT fn_norm_company_v1(c.name) AS ckey
          FROM offer_students os
          JOIN offers o ON o.id = os.offer_id
          JOIN companies c ON c.id = o.company_id
          WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> '') oc;

    _companies_skipped := _companies_total - _companies_matched;

    -- Candidate (job, student) pairs - identical select is run again for the
    -- insert below so the two can never drift apart.
    SELECT COUNT(*) INTO _candidates
    FROM (
        SELECT j.id AS job_id, o_row.roll_no
        FROM (SELECT id, fn_norm_company_v1(company) AS ckey FROM jobs) j
        JOIN (
            SELECT DISTINCT ON (fn_norm_company_v1(c.name), trim(os.roll_no))
                   fn_norm_company_v1(c.name) AS ckey,
                   trim(os.roll_no) AS roll_no
            FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            JOIN companies c ON c.id = o.company_id
            WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> ''
              AND o.email_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM emails e WHERE e.id = o.email_id)
            ORDER BY fn_norm_company_v1(c.name), trim(os.roll_no), o.created_at, o.id
        ) o_row ON o_row.ckey = j.ckey
    ) c;

    -- Insert (idempotent - the UNIQUE (job_id, student_roll_no) is the guard)
    INSERT INTO job_placed_students (job_id, student_roll_no, student_name, offer_email_id, company_name, placed_at)
    SELECT picked.job_id,
           picked.roll_no,
           picked.student_name,
           picked.offer_email_id,
           picked.company_name,
           NOW()
    FROM (
        SELECT j.id AS job_id,
               o_row.roll_no,
               o_row.student_name,
               o_row.offer_email_id,
               o_row.company_name
        FROM (SELECT id, fn_norm_company_v1(company) AS ckey FROM jobs) j
        JOIN (
            SELECT DISTINCT ON (fn_norm_company_v1(c.name), trim(os.roll_no))
                   fn_norm_company_v1(c.name) AS ckey,
                   trim(os.roll_no) AS roll_no,
                   NULLIF(trim(os.name), '') AS student_name,
                   o.email_id AS offer_email_id,
                   c.name AS company_name
            FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            JOIN companies c ON c.id = o.company_id
            WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> ''
              AND o.email_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM emails e WHERE e.id = o.email_id)
            ORDER BY fn_norm_company_v1(c.name), trim(os.roll_no), o.created_at, o.id
        ) o_row ON o_row.ckey = j.ckey
    ) picked
    ON CONFLICT (job_id, student_roll_no) DO NOTHING;

    GET DIAGNOSTICS _inserted = ROW_COUNT;
    _duplicates := GREATEST(_candidates - _inserted, 0);

    SELECT COUNT(DISTINCT job_id), COUNT(DISTINCT student_roll_no), COUNT(*)
    INTO _jobs_matched, _students_mapped, _total_mappings
    FROM job_placed_students;

    SELECT json_build_object(
        'status', 'SUCCESS',
        'message', 'Offer-student sync completed',
        'jobsTotal', _jobs_total,
        'jobsMatched', _jobs_matched,
        'jobsWithoutPlacements', GREATEST(_jobs_total - _jobs_matched, 0),
        'studentsConsidered', _students_considered,
        'studentsMapped', _students_mapped,
        'mappingsInserted', _inserted,
        'duplicatesSkipped', _duplicates,
        'companiesMatched', _companies_matched,
        'companiesSkipped', _companies_skipped,
        'totalMappings', _total_mappings,
        'lastRunAt', NOW()
    ) INTO _result;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;

-- 4. Students placed against one job (job id or superset identifier)
CREATE OR REPLACE FUNCTION fn_api_select_placed_students_v1(_jobid text) RETURNS text AS $function$
DECLARE
    _job json;
    _result json;
    _jobkey text;
BEGIN
    SELECT row_to_json(j) INTO _job
    FROM (SELECT id, supersetjobidentifier, company, jobprofile, package, packageinfo,
                 location, deadline, status, posteddatetime
          FROM jobs
          WHERE id = _jobid OR supersetjobidentifier = _jobid
          LIMIT 1) j;

    IF _job IS NULL THEN
        RETURN json_build_object('status', 'ERROR', 'message', 'Job not found');
    END IF;

    _jobkey := _job->>'id';

    SELECT json_build_object(
        'status', 'SUCCESS',
        'message', 'Placed students fetched successfully',
        'job', _job,
        'placedCount', (SELECT COUNT(DISTINCT student_roll_no)
                        FROM job_placed_students WHERE job_id = _jobkey),
        'students', COALESCE((
            SELECT json_agg(row_to_json(s) ORDER BY lower(COALESCE(s.studentname, '')), s.rollno)
            FROM (
                SELECT jps.id,
                       jps.student_roll_no AS rollno,
                       jps.student_name AS studentname,
                       jps.company_name AS companyname,
                       jps.placed_at AS placedat,
                       jps.offer_email_id AS offeremailid,
                       off.branch,
                       off.program,
                       off.email,
                       off.role,
                       off.ctcraw,
                       off.ctctotal,
                       off.ctcbasis,
                       off.stipend,
                       off.employmenttype,
                       em.subject AS offersubject,
                       em.received_at AS offerreceivedat
                FROM job_placed_students jps
                LEFT JOIN LATERAL (
                    SELECT os2.branch, os2.program, os2.email,
                           COALESCE(NULLIF(trim(os2.role), ''), NULLIF(trim(o2.role), '')) AS role,
                           o2.ctc_raw AS ctcraw, o2.ctc_total AS ctctotal, o2.ctc_basis AS ctcbasis,
                           o2.stipend AS stipend, o2.employment_type AS employmenttype
                    FROM offer_students os2
                    JOIN offers o2 ON o2.id = os2.offer_id
                    JOIN companies c2 ON c2.id = o2.company_id
                    WHERE trim(os2.roll_no) = jps.student_roll_no
                      AND fn_norm_company_v1(c2.name) = fn_norm_company_v1(jps.company_name)
                    ORDER BY o2.created_at, o2.id
                    LIMIT 1
                ) off ON TRUE
                LEFT JOIN emails em ON em.id = jps.offer_email_id
                WHERE jps.job_id = _jobkey
            ) s
        ), '[]'::json)
    ) INTO _result;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;

-- 5. Company-wise rollup (one row per company that has at least one job)
CREATE OR REPLACE FUNCTION fn_api_select_company_placements_v1(
    _page integer, _pagesize integer, _search text) RETURNS text AS $function$
DECLARE
    _total integer;
    _offset integer;
    _result json;
BEGIN
    _offset := (_page - 1) * _pagesize;

    -- One row per distinct (normalised) company in the Jobs table
    SELECT COUNT(DISTINCT fn_norm_company_v1(company)) INTO _total
    FROM jobs
    WHERE _search = '' OR company ILIKE '%' || _search || '%';

    WITH job_company AS (
        SELECT id, company, jobprofile, package, packageinfo, location, deadline,
               status, posteddatetime, fn_norm_company_v1(company) AS ckey
        FROM jobs
    ),
    company_jobs AS (
        SELECT ckey,
               MIN(company) AS company,
               COUNT(*) AS jobcount,
               COUNT(*) FILTER (WHERE status = 'Active') AS activejobs,
               json_agg(json_build_object(
                   'id', j.id, 'company', j.company, 'jobprofile', j.jobprofile,
                   'package', j.package, 'packageinfo', j.packageinfo,
                   'location', j.location, 'deadline', j.deadline,
                   'status', j.status, 'posteddatetime', j.posteddatetime
               ) ORDER BY j.posteddatetime DESC NULLS LAST) AS jobs
        FROM job_company j
        GROUP BY ckey
    ),
    company_placed AS (
        SELECT jc.ckey,
               COUNT(DISTINCT jps.student_roll_no) AS placedstudents,
               MIN(jps.placed_at) AS firstplacedat,
               MAX(jps.placed_at) AS lastplacedat
        FROM job_company jc
        JOIN job_placed_students jps ON jps.job_id = jc.id
        GROUP BY jc.ckey
    ),
    company_role_counts AS (
        SELECT p.ckey,
               COALESCE(NULLIF(trim(p.role), ''), 'Not specified') AS role,
               COUNT(*) AS students,
               MAX(p.ctctotal) AS ctcmax
        FROM (
            -- one role per (company, student) - the earliest offer row wins
            SELECT DISTINCT ON (jc.ckey, jps.student_roll_no)
                   jc.ckey,
                   jps.student_roll_no,
                   COALESCE(NULLIF(trim(os.role), ''), NULLIF(trim(o.role), '')) AS role,
                   o.ctc_total AS ctctotal
            FROM job_placed_students jps
            JOIN job_company jc ON jc.id = jps.job_id
            JOIN offer_students os ON os.roll_no IS NOT NULL
                                  AND trim(os.roll_no) = jps.student_roll_no
            JOIN offers o ON o.id = os.offer_id
            JOIN companies c ON c.id = o.company_id
                             AND fn_norm_company_v1(c.name) = jc.ckey
            ORDER BY jc.ckey, jps.student_roll_no, o.created_at, o.id
        ) p
        GROUP BY p.ckey, 2
    ),
    company_roles AS (
        SELECT ckey,
               json_agg(json_build_object('role', role, 'students', students, 'ctcmax', ctcmax)
                        ORDER BY students DESC, role) AS roles
        FROM company_role_counts
        GROUP BY ckey
    )
    SELECT json_agg(row_to_json(t) ORDER BY t.placedstudents DESC, t.company) INTO _result
    FROM (
        SELECT cj.company,
               cj.jobcount,
               cj.activejobs,
               COALESCE(cp.placedstudents, 0) AS placedstudents,
               cp.firstplacedat,
               cp.lastplacedat,
               cj.jobs,
               COALESCE(cr.roles, '[]'::json) AS roles
        FROM company_jobs cj
        LEFT JOIN company_placed cp ON cp.ckey = cj.ckey
        LEFT JOIN company_roles cr ON cr.ckey = cj.ckey
        WHERE _search = '' OR cj.company ILIKE '%' || _search || '%'
        ORDER BY COALESCE(cp.placedstudents, 0) DESC, cj.company ASC
        LIMIT _pagesize OFFSET _offset
    ) t;

    RETURN json_build_object(
        'Items', COALESCE(_result, '[]'::json),
        'TotalCount', _total,
        'Page', _page,
        'PageSize', _pagesize,
        'TotalPages', CEIL(_total::numeric / _pagesize))::text;
END;
$function$ LANGUAGE plpgsql;

-- 6. Gmail notices feed (everything extracted from email EXCEPT the
--    congratulation / final-offer data, which lives in the placement view)
CREATE OR REPLACE FUNCTION fn_api_select_email_notices_v1(
    _page integer, _pagesize integer, _search text, _type text) RETURNS text AS $function$
DECLARE
    _total integer;
    _offset integer;
    _result json;
    _facets json;
BEGIN
    _offset := (_page - 1) * _pagesize;

    -- Count by classification (search applies, the type filter does not)
    SELECT COALESCE(json_agg(row_to_json(f) ORDER BY f.count DESC, f.classification), '[]'::json)
    INTO _facets
    FROM (
        SELECT COALESCE(e.classification, 'UNKNOWN') AS classification, COUNT(*) AS count
        FROM emails e
        WHERE e.is_canonical = TRUE
          AND e.dedup_of IS NULL
          AND COALESCE(e.classification, 'UNKNOWN') NOT IN ('FINAL_SELECTION', 'IRRELEVANT')
          AND (_search = '' OR e.subject ILIKE '%' || _search || '%'
               OR COALESCE(e.body_clean, e.body_text, '') ILIKE '%' || _search || '%'
               OR COALESCE(e.sender, '') ILIKE '%' || _search || '%')
        GROUP BY 1
    ) f;

    SELECT COUNT(*) INTO _total
    FROM emails e
    WHERE e.is_canonical = TRUE
      AND e.dedup_of IS NULL
      AND COALESCE(e.classification, 'UNKNOWN') NOT IN ('FINAL_SELECTION', 'IRRELEVANT')
      AND (_search = '' OR e.subject ILIKE '%' || _search || '%'
           OR COALESCE(e.body_clean, e.body_text, '') ILIKE '%' || _search || '%'
           OR COALESCE(e.sender, '') ILIKE '%' || _search || '%')
      AND (_type = '' OR COALESCE(e.classification, 'UNKNOWN') = _type);

    SELECT json_agg(row_to_json(n)) INTO _result
    FROM (
        SELECT e.id,
               e.gmail_message_id AS gmailmessageid,
               e.subject,
               LEFT(COALESCE(e.snippet, e.body_clean, e.body_text, ''), 300) AS snippet,
               e.sender,
               e.sender_email AS senderemail,
               e.received_at AS receivedat,
               COALESCE(e.classification, 'UNKNOWN') AS classification,
               e.classification_confidence AS confidence,
               e.classification_method AS method,
               e.has_attachments AS hasattachments,
               e.revision_of IS NOT NULL AS isrevision,
               CASE COALESCE(e.classification, 'UNKNOWN')
                   WHEN 'SHORTLIST' THEN 'Shortlist'
                   WHEN 'SELECTION_PROCESS_NOTICE' THEN 'Selection process'
                   WHEN 'HACKATHON' THEN 'Hackathon'
                   WHEN 'EVENT' THEN 'Event'
                   WHEN 'REGISTRATION' THEN 'Registration'
                   WHEN 'WEBINAR' THEN 'Webinar'
                   WHEN 'WORKSHOP' THEN 'Workshop'
                   WHEN 'INTERNSHIP_OPPORTUNITY' THEN 'Internship'
                   WHEN 'JOB_OPPORTUNITY' THEN 'Job opportunity'
                   WHEN 'GENERAL_PLACEMENT_NOTICE' THEN 'Placement notice'
                   ELSE 'Unclassified'
               END AS classificationlabel,
               co.name AS company,
               CASE
                   WHEN COALESCE(e.classification, 'UNKNOWN') = 'SHORTLIST' AND se.stage IS NOT NULL
                       THEN INITCAP(LOWER(REPLACE(se.stage, '_', ' ')))
                   ELSE NULLIF(op.event_name, '')
               END AS headline,
               COALESCE(se.deadline, op.deadline) AS deadline,
               NULLIF(op.registration_link, '') AS link,
               ssc.studentcount,
               fcg.rounds
        FROM emails e
        LEFT JOIN shortlist_events se ON se.email_id = e.id
        LEFT JOIN opportunities op ON op.email_id = e.id
        LEFT JOIN companies co ON co.id = COALESCE(se.company_id, op.company_id)
        LEFT JOIN LATERAL (
            SELECT CASE WHEN se.id IS NULL THEN NULL
                        ELSE (SELECT COUNT(*)
                              FROM shortlist_students ss
                              WHERE ss.shortlist_event_id = se.id) END AS studentcount
        ) ssc ON TRUE
        LEFT JOIN LATERAL (
            SELECT json_agg(json_build_object('round', fc.round_name, 'count', fc.count)
                            ORDER BY fc.round_order) AS rounds
            FROM funnel_counts fc
            WHERE fc.email_id = e.id
        ) fcg ON TRUE
        WHERE e.is_canonical = TRUE
          AND e.dedup_of IS NULL
          AND COALESCE(e.classification, 'UNKNOWN') NOT IN ('FINAL_SELECTION', 'IRRELEVANT')
          AND (_search = '' OR e.subject ILIKE '%' || _search || '%'
               OR COALESCE(e.body_clean, e.body_text, '') ILIKE '%' || _search || '%'
               OR COALESCE(e.sender, '') ILIKE '%' || _search || '%')
          AND (_type = '' OR COALESCE(e.classification, 'UNKNOWN') = _type)
        ORDER BY e.received_at DESC NULLS LAST, e.created_at DESC
        LIMIT _pagesize OFFSET _offset
    ) n;

    RETURN json_build_object(
        'Items', COALESCE(_result, '[]'::json),
        'TotalCount', _total,
        'Page', _page,
        'PageSize', _pagesize,
        'TotalPages', CEIL(_total::numeric / _pagesize),
        'Facets', COALESCE(_facets, '[]'::json))::text;
END;
$function$ LANGUAGE plpgsql;
