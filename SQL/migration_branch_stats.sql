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
-- ANALYTICS EXTENSION (product owner approved; ADDITIVE ONLY).
-- Nothing that existed before changed shape, name or meaning, so older
-- clients keep working:
--
--   * branches[].finedistribution + totals.finedistribution
--       15 FIXED buckets (0-3 ... 50+ LPA, then "Not disclosed"), counted in
--       OFFERS - the distribution chart's y-axis is offers, not heads.  The
--       older `distribution` (4 official JIIT bands, counted in students) is
--       untouched and still fed to the Dashboard.
--   * timeline[].studentswithpackage / averagepackage / medianpackage
--       package stats over that month's OWN offers, one figure per head per
--       month (never a cross-month leak of a later better offer).
--   * timeline[].cumstudentswithpackage / cumaveragepackage / cummedianpackage
--       and the same three on daily[] - the CUMULATIVE twin, rebuilt from the
--       raw per-student pool at each cutoff rather than derived from the
--       per-bucket numbers (an average of monthly averages, and especially of
--       monthly MEDIANS, would both be wrong).
--   * daily[] - same counters bucketed by day (54 buckets), for the timeline
--       chart's Month/Day switch.
-- Band edges are plain rupee thresholds in `fine_bands`; they are FIXED, not
-- configurable - see the approved data contract in the header above.
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
    -- Fine-grained buckets for the Analytics distribution chart.  FIXED
    -- edges, approved as-is: 0-3, 3-4, 4-5, 5-6, 6-8, 8-10, 10-12, 12-15,
    -- 15-20, 20-25, 25-30, 30-40, 40-50, 50+ (LPA), then the honest
    -- "Not disclosed" tail so the columns still sum to `totaloffers`.
    -- `lo`/`hi` are RUPEES and exclusive at the top; NULL means no edge.
    fine_bands(ord, band, lo, hi) AS (
        VALUES (1,  '0 - 3 L',    0::numeric,   300000::numeric),
               (2,  '3 - 4 L',         300000,        400000),
               (3,  '4 - 5 L',         400000,        500000),
               (4,  '5 - 6 L',         500000,        600000),
               (5,  '6 - 8 L',         600000,        800000),
               (6,  '8 - 10 L',        800000,      1000000),
               (7,  '10 - 12 L',      1000000,      1200000),
               (8,  '12 - 15 L',      1200000,      1500000),
               (9,  '15 - 20 L',      1500000,      2000000),
               (10, '20 - 25 L',      2000000,      2500000),
               (11, '25 - 30 L',      2500000,      3000000),
               (12, '30 - 40 L',      3000000,      4000000),
               (13, '40 - 50 L',      4000000,      5000000),
               (14, '50+ L',          5000000, 999999999999),
               (15, 'Not disclosed',  NULL,          NULL)
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

    -- ---- fine-grained offer bands (ANALYTICS EXTENSION) -------------------
    -- ONE row per offer (the `focus` key), with that offer's OWN figure - an
    -- e-mail may carry several roles, so MAX folds them.  Deliberately NOT
    -- the per-student max: this chart counts offers, not heads.
    offer_rows AS (
        SELECT rb.branch,
               f.roll,
               f.company_name,
               f.offer_email_id,
               MAX(o.ctc_total) FILTER (WHERE o.ctc_total > 0) AS ctc
        FROM focus f
        JOIN roll_branch rb ON rb.roll = f.roll
        LEFT JOIN offers o  ON o.email_id = f.offer_email_id
        GROUP BY rb.branch, f.roll, f.company_name, f.offer_email_id
    ),
    -- `fine_bands` is the single source of truth for the edges.  Band 15 has
    -- no edges, so it can only be reached by COALESCE below - which is exactly
    -- the "no figure was ever disclosed" answer.
    fine_offer AS (
        SELECT r.branch,
               r.roll,
               COALESCE(fb.ord, 15) AS fbno
        FROM offer_rows r
        LEFT JOIN fine_bands fb
          ON r.ctc IS NOT NULL
         AND r.ctc >= fb.lo
         AND (fb.hi IS NULL OR r.ctc < fb.hi)
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

    -- ---- fine-grained distribution (ANALYTICS EXTENSION, counted in OFFERS)
    -- Spine is denominators x fine_bands so an empty branch still returns all
    -- fifteen columns at 0 rather than a short array (chart axis stability).
    fine_dist_branch AS (
        SELECT d.branch, fb.band, fb.ord, COALESCE(n.offers, 0) AS offers
        FROM denominators d
        CROSS JOIN fine_bands fb
        LEFT JOIN (SELECT x.branch, x.fbno, COUNT(*) AS offers
                   FROM fine_offer x
                   GROUP BY x.branch, x.fbno) n
               ON n.branch = d.branch AND n.fbno = fb.ord
    ),
    fine_dist_total AS (
        SELECT fb.band, fb.ord, COALESCE(n.offers, 0) AS offers
        FROM fine_bands fb
        LEFT JOIN (SELECT x.fbno, COUNT(*) AS offers
                   FROM fine_offer x
                   GROUP BY x.fbno) n ON n.fbno = fb.ord
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

    -- ---- timeline package overlays (ANALYTICS EXTENSION) ------------------
    -- One figure per head PER BUCKET: a student who appears twice in a month
    -- contributes their best offer of that month once.  The bucket is chosen
    -- from the SAME received_at that buckets the bar, so a later, better offer
    -- can never leak backwards into an earlier month's line.
    timeline_pkg AS (
        SELECT to_char(date_trunc('month', e.received_at), 'YYYY-MM') AS month,
               f.roll,
               MAX(o.ctc_total) FILTER (WHERE o.ctc_total > 0) AS ctc
        FROM focus f
        JOIN emails e ON e.id = f.offer_email_id
        LEFT JOIN offers o ON o.email_id = f.offer_email_id
        GROUP BY 1, f.roll
    ),
    timeline_stats AS (
        SELECT t.month,
               COUNT(t.ctc)                                    AS studentswithpackage,
               ROUND(AVG(t.ctc) / 100000, 2)                   AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY t.ctc::double precision))::numeric
                     / 100000, 2)                              AS medianpackage
        FROM timeline_pkg t
        GROUP BY 1
    ),
    -- Same three numbers bucketed by day - feeds the Month/Day switch.
    daily AS (
        SELECT to_char(date_trunc('day', e.received_at), 'YYYY-MM-DD') AS day,
               COUNT(*)               AS offers,
               COUNT(DISTINCT f.roll) AS students,
               COUNT(DISTINCT f.company_name) AS companies
        FROM focus f
        JOIN emails e ON e.id = f.offer_email_id
        GROUP BY 1
    ),
    daily_pkg AS (
        SELECT to_char(date_trunc('day', e.received_at), 'YYYY-MM-DD') AS day,
               f.roll,
               MAX(o.ctc_total) FILTER (WHERE o.ctc_total > 0) AS ctc
        FROM focus f
        JOIN emails e ON e.id = f.offer_email_id
        LEFT JOIN offers o ON o.email_id = f.offer_email_id
        GROUP BY 1, f.roll
    ),
    daily_stats AS (
        SELECT d.day,
               COUNT(d.ctc)                       AS studentswithpackage,
               ROUND(AVG(d.ctc) / 100000, 2)      AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY d.ctc::double precision))::numeric
                     / 100000, 2)                 AS medianpackage
        FROM daily_pkg d
        GROUP BY 1
    ),
    -- ---- CUMULATIVE overlays (ANALYTICS EXTENSION) ------------------------
    -- For cutoff `c` the pool is every figure that had already landed by the
    -- END of `c`, folded to ONE per head (their best so far), then averaged
    -- and medianed over that pool.  Rebuilt from the raw per-student figures
    -- on purpose: an average of per-bucket averages and - worse - an average
    -- of per-bucket MEDIANS would both be wrong, so the cumulative line never
    -- derives from the individual line.
    cum_month AS (
        SELECT c.month AS cutoff, p.roll, MAX(p.ctc) AS ctc
        FROM (SELECT DISTINCT month FROM timeline) c
        JOIN timeline_pkg p ON p.month <= c.month
        GROUP BY 1, 2
    ),
    cum_month_stats AS (
        SELECT m.cutoff                                AS month,
               COUNT(m.ctc)                            AS studentswithpackage,
               ROUND(AVG(m.ctc) / 100000, 2)           AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY m.ctc::double precision))::numeric
                     / 100000, 2)                      AS medianpackage
        FROM cum_month m
        GROUP BY 1
    ),
    cum_day AS (
        SELECT c.day AS cutoff, p.roll, MAX(p.ctc) AS ctc
        FROM (SELECT DISTINCT day FROM daily) c
        JOIN daily_pkg p ON p.day <= c.day
        GROUP BY 1, 2
    ),
    cum_day_stats AS (
        SELECT d.cutoff                          AS day,
               COUNT(d.ctc)                      AS studentswithpackage,
               ROUND(AVG(d.ctc) / 100000, 2)     AS averagepackage,
               ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY d.ctc::double precision))::numeric
                     / 100000, 2)                AS medianpackage
        FROM cum_day d
        GROUP BY 1
    ),
    -- Cumulative COUNTERS.  `cumoffers` is a plain running sum (every offer
    -- lands in exactly one bucket), but `cumstudents` has to be a genuine
    -- COUNT(DISTINCT roll): a running sum of the per-month unique counts would
    -- count a student once per month they appear in - 360 here, against a
    -- cohort of 345 - so it would overstate the bar every single month.
    cum_counts_month AS (
        SELECT c.cutoff,
               COUNT(*)               AS offers,
               COUNT(DISTINCT f.roll) AS students
        FROM (SELECT DISTINCT month AS cutoff FROM timeline) c
        CROSS JOIN focus f
        JOIN emails e ON e.id = f.offer_email_id
        WHERE to_char(date_trunc('month', e.received_at), 'YYYY-MM') <= c.cutoff
        GROUP BY 1
    ),
    cum_counts_day AS (
        SELECT c.cutoff,
               COUNT(*)               AS offers,
               COUNT(DISTINCT f.roll) AS students
        FROM (SELECT DISTINCT day AS cutoff FROM daily) c
        CROSS JOIN focus f
        JOIN emails e ON e.id = f.offer_email_id
        WHERE to_char(date_trunc('day', e.received_at), 'YYYY-MM-DD') <= c.cutoff
        GROUP BY 1
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
                       ),
                       'finedistribution', (
                           SELECT COALESCE(json_agg(json_build_object(
                                      'band', d.band, 'offers', d.offers)
                                      ORDER BY d.ord), '[]'::json)
                           FROM fine_dist_branch d WHERE d.branch = br.branch
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
                           FROM dist_total d),
                       'finedistribution', (
                           SELECT COALESCE(json_agg(json_build_object(
                                      'band', d.band, 'offers', d.offers)
                                      ORDER BY d.ord), '[]'::json)
                           FROM fine_dist_total d)
            ) FROM totals t
        ),
        'timeline', (
            SELECT COALESCE(json_agg(json_build_object(
                       'month', tl.month, 'offers', tl.offers,
                       'students', tl.students, 'companies', tl.companies,
                       'cumoffers', COALESCE(cm.offers, 0),
                       'cumstudents', COALESCE(cm.students, 0),
                       'studentswithpackage', COALESCE(ts.studentswithpackage, 0),
                       'averagepackage', ts.averagepackage,
                       'medianpackage', ts.medianpackage,
                       'cumstudentswithpackage', COALESCE(cs.studentswithpackage, 0),
                       'cumaveragepackage', cs.averagepackage,
                       'cummedianpackage', cs.medianpackage)
                       ORDER BY tl.month), '[]'::json)
            FROM timeline tl
            LEFT JOIN timeline_stats ts ON ts.month = tl.month
            LEFT JOIN cum_month_stats cs ON cs.month = tl.month
            LEFT JOIN cum_counts_month cm ON cm.cutoff = tl.month
        ),
        'daily', (
            SELECT COALESCE(json_agg(json_build_object(
                       'day', d.day, 'offers', d.offers,
                       'students', d.students, 'companies', d.companies,
                       'cumoffers', COALESCE(cm.offers, 0),
                       'cumstudents', COALESCE(cm.students, 0),
                       'studentswithpackage', COALESCE(ds.studentswithpackage, 0),
                       'averagepackage', ds.averagepackage,
                       'medianpackage', ds.medianpackage,
                       'cumstudentswithpackage', COALESCE(cds.studentswithpackage, 0),
                       'cumaveragepackage', cds.averagepackage,
                       'cummedianpackage', cds.medianpackage)
                       ORDER BY d.day), '[]'::json)
            FROM daily d
            LEFT JOIN daily_stats ds ON ds.day = d.day
            LEFT JOIN cum_day_stats cds ON cds.day = d.day
            LEFT JOIN cum_counts_day cm ON cm.cutoff = d.day
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
