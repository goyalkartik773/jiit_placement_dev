-- ============================================================================
-- Branch-wise placement statistics for ONE graduating batch (2026-27).
--
--   GET /api/placements/branch-stats   ->   fn_api_select_branch_stats_v1()
--
-- PURELY ADDITIVE migration: it creates one function and touches no existing
-- table, column, function or row.  Everything below reads
--   job_placed_students  (the .NET sync write path, unchanged)
--   offers               (ctc_total - the only trustworthy money figure)
--   emails               (received_at - the only real timestamp)
--   fn_branch_from_roll_v1 / fn_batch_year_from_roll_v1 (roll -> branch/year)
-- ----------------------------------------------------------------------------
-- DATA CONTRACT (all four points were decided with the product owner before
-- any code was written - see placement_pipeline/docs/roll_to_branch_mapping.md):
--
--  1. DENOMINATOR.  `totalstudents` per branch is the reference repo's
--     hardcoded head-count (tashifkhan/JIIT-placement-alerts,
--     app/services/placement/analysis/config.py:169-195, key "202627"),
--     summed over its campus / sub-branch keys and copied verbatim:
--         CSE 386+323=709   ECE 217+108=325   EC-ACT 52   EE-VLSI 62
--         IT 62   BT 55   Intg. MTech 31+15+11=57        -> total 1322
--     It is deliberately NOT computed from our data: our tables only contain
--     students who appeared in at least one offer email, so a computed
--     denominator would inflate every placement rate.
--
--  2. BRANCH SCOPE.  All seven branches the reference reports, in its order.
--
--  3. PACKAGE.  ONLY `offers.ctc_total`, taken as MAX per student (one figure
--     per head, never a sum).  `jobs.package` is NOT used - it mixes annual
--     CTC with monthly stipends (e.g. Amazon's 70000 is a stipend, 28/216
--     jobs disagree with ctc_total).  ctc_total is in RUPEES; every package
--     field below is in LPA (rounded to 2 decimals).  Offers that never
--     spelled out a figure are counted in `studentswithpackage`'s
--     complement and reported as the "Not disclosed" band instead of 0.
--
--  4. COHORT.  Graduating batch 2027 = 4-year BTech admits of 2023
--     (23101/23102/23103/23104/23118/23119, Sector 128 992310x) plus 5-year
--     Intg. MTech admits of 2022 (22801 BT / 22802 ECE / 22803 CSE).
--     2022 BTech admits graduate in 2026 and are OUT; JUIT, MTech and
--     unresolved rolls are OUT as well.
--
-- TIMELINE.  `job_placed_students.placed_at` is unusable (every row reads
-- 2026-09-30, the backfill timestamp), so the timeline is bucketed by
-- `emails.received_at` - the moment the offer mail actually landed.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_api_select_branch_stats_v1() RETURNS text AS $function$
DECLARE
    _result json;
BEGIN
    WITH
    -- Head-count denominators - see DATA CONTRACT (1).  `ord` is the display
    -- order the reference uses; it rides along into the response array order.
    denominators(ord, branch, totalstudents) AS (
        VALUES (1, 'CSE',         709),
               (2, 'ECE',         325),
               (3, 'IT',           62),
               (4, 'BT',           55),
               (5, 'Intg. MTech',  57),
               (6, 'EC-ACT',       52),
               (7, 'EE-VLSI',      62)
    ),
    -- JIIT's three official CTC bands plus our honest "never said" bucket.
    -- Thresholds are rupees: 6.00 L = 600000, 13.00 L = 1300000.
    bands(ord, band) AS (
        VALUES (1, 'Upto 5.99 L'),
               (2, '6.00 - 12.99 L'),
               (3, '13.00 L and above'),
               (4, 'Not disclosed')
    ),

    -- One row per placed (student, company) pair straight out of the sync table.
    placed AS (
        SELECT btrim(jps.student_roll_no) AS roll,
               jps.company_name,
               jps.offer_email_id
        FROM job_placed_students jps
        WHERE jps.student_roll_no IS NOT NULL
          AND btrim(jps.student_roll_no) <> ''
    ),
    -- Same rows tagged by the roll rule - an IMMUTABLE pure function of the
    -- roll, so one roll always yields one branch.
    cohort AS (
        SELECT p.roll,
               p.company_name,
               p.offer_email_id,
               fn_branch_from_roll_v1(p.roll)       AS branch,
               fn_batch_year_from_roll_v1(p.roll)   AS batch_year
        FROM placed p
    ),
    focus AS (
        SELECT c.*
        FROM cohort c
        WHERE c.branch IN ('CSE','ECE','IT','BT','EC-ACT','EE-VLSI','Intg. MTech')
          AND (c.batch_year = 2023
               OR (c.branch = 'Intg. MTech' AND c.batch_year = 2022))
    ),

    -- DISTINCT roll in the cohort + its branch (one branch per roll, so this
    -- is the "one row per head" spine every per-student figure hangs off).
    roll_branch AS (
        SELECT DISTINCT roll, branch FROM focus
    ),
    -- Best disclosed CTC per student, in rupees.  Joining offers on
    -- email_id can return several offers for one mail, which MAX folds away.
    best AS (
        SELECT f.roll, MAX(o.ctc_total) AS ctc
        FROM focus f
        JOIN offers o ON o.email_id = f.offer_email_id
        WHERE o.ctc_total IS NOT NULL AND o.ctc_total > 0
        GROUP BY f.roll
    ),
    -- One row per student, its branch, and the band it falls into.
    student_rows AS (
        SELECT rb.roll,
               rb.branch,
               b.ctc,
               CASE WHEN b.ctc IS NULL               THEN 4
                    WHEN b.ctc <  600000             THEN 1
                    WHEN b.ctc < 1300000             THEN 2
                    ELSE 3 END AS bno
        FROM roll_branch rb
        LEFT JOIN best b ON b.roll = rb.roll
    ),

    -- ---- per-branch aggregates -------------------------------------------
    branch_counts AS (
        SELECT f.branch,
               COUNT(DISTINCT f.roll)      AS placedstudents,
               COUNT(*)                    AS totaloffers,
               COUNT(DISTINCT f.company_name) AS companies
        FROM focus f
        GROUP BY f.branch
    ),
    branch_pkg AS (
        -- AVG / median / MAX all run over ONE value per head (s.ctc), never
        -- over the offer rows - otherwise a student with 4 offers would be
        -- counted four times in the average.
        SELECT s.branch,
               COUNT(s.ctc)                                             AS studentswithpackage,
               ROUND(AVG(s.ctc) / 100000, 2)                            AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY s.ctc::double precision))::numeric
                     / 100000, 2)                                       AS medianpackage,
               ROUND(MAX(s.ctc)::numeric / 100000, 2)                   AS highestpackage
        FROM student_rows s
        WHERE s.ctc IS NOT NULL
        GROUP BY s.branch
    ),
    total_pkg AS (
        SELECT COUNT(s.ctc)                                             AS studentswithpackage,
               ROUND(AVG(s.ctc) / 100000, 2)                            AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY s.ctc::double precision))::numeric
                     / 100000, 2)                                       AS medianpackage,
               ROUND(MAX(s.ctc)::numeric / 100000, 2)                   AS highestpackage
        FROM student_rows s
        WHERE s.ctc IS NOT NULL
    ),

    -- ---- distribution ------------------------------------------------------
    -- The spine is denominators x bands, so a branch with zero placed
    -- students still returns all four bands at 0 instead of an empty array.
    dist_branch AS (
        SELECT d.branch, b.band, b.ord,
               COALESCE(n.students, 0) AS students
        FROM denominators d
        CROSS JOIN bands b
        LEFT JOIN (SELECT s.branch, s.bno, COUNT(*) AS students
                   FROM student_rows s
                   GROUP BY s.branch, s.bno) n
               ON n.branch = d.branch AND n.bno = b.ord
    ),
    dist_total AS (
        SELECT b.band, b.ord, COALESCE(n.students, 0) AS students
        FROM bands b
        LEFT JOIN (SELECT s.bno, COUNT(*) AS students
                   FROM student_rows s
                   GROUP BY s.bno) n ON n.bno = b.ord
    ),

    -- ---- timeline (months are ISO YYYY-MM, sorted lexicographically) -------
    timeline AS (
        SELECT to_char(date_trunc('month', e.received_at), 'YYYY-MM') AS month,
               COUNT(*)                AS offers,
               COUNT(DISTINCT f.roll)  AS students,
               COUNT(DISTINCT f.company_name) AS companies
        FROM focus f
        JOIN emails e ON e.id = f.offer_email_id
        GROUP BY 1
    ),
    branch_timeline AS (
        SELECT f.branch,
               to_char(date_trunc('month', e.received_at), 'YYYY-MM') AS month,
               COUNT(*)               AS offers,
               COUNT(DISTINCT f.roll) AS students
        FROM focus f
        JOIN emails e ON e.id = f.offer_email_id
        GROUP BY 1, 2
    ),

    -- ---- final per-branch rows --------------------------------------------
    branch_rows AS (
        SELECT d.ord,
               d.branch,
               d.totalstudents,
               COALESCE(cc.placedstudents, 0) AS placedstudents,
               COALESCE(cc.totaloffers,   0)  AS totaloffers,
               COALESCE(cc.companies,      0)  AS companies,
               COALESCE(bp.studentswithpackage, 0) AS studentswithpackage,
               bp.averagepackage,
               bp.medianpackage,
               bp.highestpackage
        FROM denominators d
        LEFT JOIN branch_counts cc ON cc.branch = d.branch
        LEFT JOIN branch_pkg    bp ON bp.branch = d.branch
    ),
    totals AS (
        SELECT (SELECT SUM(totalstudents) FROM denominators) AS totalstudents,
               (SELECT COUNT(DISTINCT roll)  FROM focus)     AS placedstudents,
               (SELECT COUNT(*)              FROM focus)     AS totaloffers,
               (SELECT COUNT(DISTINCT company_name) FROM focus) AS companies,
               tp.*
        FROM total_pkg tp
    )

    -- No FROM clause -> exactly one row, so INTO takes the whole object.
    SELECT json_build_object(
        'batch',            '2026-27',
        'graduatingbatch',  2027,
        'generatedat',      NOW(),
        'currency',         'LPA',
        'branches', (
            SELECT COALESCE(json_agg(json_build_object(
                       'branch',               br.branch,
                       'totalstudents',        br.totalstudents,
                       'placedstudents',       br.placedstudents,
                       'placementpercentage',  CASE WHEN br.totalstudents > 0
                                                    THEN ROUND(br.placedstudents * 100.0
                                                               / br.totalstudents, 2)
                                                    ELSE 0 END,
                       'totaloffers',          br.totaloffers,
                       'companies',            br.companies,
                       'studentswithpackage',  br.studentswithpackage,
                       'averagepackage',       br.averagepackage,
                       'medianpackage',        br.medianpackage,
                       'highestpackage',       br.highestpackage,
                       'distribution', (
                           SELECT COALESCE(json_agg(json_build_object(
                                      'band', d.band, 'students', d.students)
                                      ORDER BY d.ord), '[]'::json)
                           FROM dist_branch d WHERE d.branch = br.branch
                       )) ORDER BY br.ord), '[]'::json)
            FROM branch_rows br
        ),
        'totals', (
            SELECT json_build_object(
                       'totalstudents',        t.totalstudents,
                       'placedstudents',       t.placedstudents,
                       'placementpercentage',  CASE WHEN t.totalstudents > 0
                                                    THEN ROUND(t.placedstudents * 100.0
                                                               / t.totalstudents, 2)
                                                    ELSE 0 END,
                       'totaloffers',          t.totaloffers,
                       'companies',            t.companies,
                       'studentswithpackage',  t.studentswithpackage,
                       'averagepackage',       t.averagepackage,
                       'medianpackage',        t.medianpackage,
                       'highestpackage',       t.highestpackage,
                       'distribution', (
                           SELECT COALESCE(json_agg(json_build_object(
                                      'band', d.band, 'students', d.students)
                                      ORDER BY d.ord), '[]'::json)
                           FROM dist_total d)
            ) FROM totals t
        ),
        'timeline', (
            SELECT COALESCE(json_agg(json_build_object(
                       'month', tl.month, 'offers', tl.offers,
                       'students', tl.students, 'companies', tl.companies)
                       ORDER BY tl.month), '[]'::json)
            FROM timeline tl
        ),
        'branchtimeline', (
            SELECT COALESCE(json_agg(json_build_object(
                       'branch', bl.branch, 'month', bl.month,
                       'offers', bl.offers, 'students', bl.students)
                       ORDER BY bl.branch, bl.month), '[]'::json)
            FROM branch_timeline bl
        )
    ) INTO _result;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;
