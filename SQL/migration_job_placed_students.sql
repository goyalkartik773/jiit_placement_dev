-- ================================================================
-- Migration: Job <-> Offered-Student mapping (admin-triggered sync)
--
-- Task 1 of the dashboard work:
--   * job_placed_students  : relation table (job x placed student)
--   * fn_api_sync_offer_students_v1()              : the matching run
--   * fn_api_select_placed_students_v1(_jobid)     : students of one job
--   * fn_api_select_company_placements_v1(...)     : company-wise rollup
--   * fn_api_select_email_notices_v1(...)          : Gmail notices feed
--   * fn_api_select_email_notice_detail_v1(...)    : one email, full detail
--   * fn_branch_from_roll_v1 / fn_batch_year_from_roll_v1 (section 1b)
--     -> READ-SIDE only: roll number -> branch + admission year. Additive,
--        no column, no write-path change. Mirrors the Python reader
--        placement_pipeline/app/domain/roll_mapper.py (keep in sync).
--
-- Matching rules (agreed):
--   * company match only - NEVER create/guess a job. An offer company that
--     has no row in "jobs" is counted in "companiesSkipped" and ignored.
--   * company comparison is normalised (lowercase + collapse spaces + drop
--     ONE trailing parenthetical + strip trailing corporate suffixes + strip
--     trailing punctuation), e.g.
--         "Josh Technology Group (JTG)"   == "Josh Technology Group"
--         "Technum Opus Private Limited"  == "Technum Opus"
--         "Deloitte USI"                  == "Deloitte"
--         "Grexa AI"                      == "Grexa"
--         "Vehant Technologies"           == "Vehant"
--         "Coforge."                      == "Coforge"
--     A job row IS a company listing, so an offered student maps to every
--     job row of that company.
--     Verified before shipping: 0 previously-matching pair broke, and every
--     key shared by two spellings was the same company (Juspay/JUSPAY,
--     MoveinSync/MoveInSync, Watchguard/WatchGuard Technologies, ...).
--   * one brand alias: SuperSet spells LTIMindtree as "LTM" (Graduate Engineer
--     Trainee, PAN INDIA, package 405233, mass recruitment) - folded to
--     "ltimindtree" here. Renaming jobs.company instead would be undone by the
--     next SuperSet sync.
--   * idempotent: UNIQUE (job_id, student_roll_no) + ON CONFLICT DO NOTHING,
--     so re-running the sync never inserts a duplicate mapping.
-- ================================================================

-- 1. Normalised company key (single source of truth for both sides)
CREATE OR REPLACE FUNCTION fn_norm_company_v1(_name text) RETURNS text AS $function$
DECLARE
    _key text;
BEGIN
    -- Fold case FIRST: the suffix pass below is written in lower case, so
    -- "Deloitte USI" would otherwise never match the literal 'usi'.
    _key := trim(regexp_replace(lower(COALESCE(_name, '')), '\s+', ' ', 'g'));

    -- Drop ONE trailing parenthetical: "Josh Technology Group (JTG)" -> base.
    _key := regexp_replace(_key, '\s*\([^()]*\)$', '');

    -- SuperSet brand alias (see the header comment of this file).
    IF _key = 'ltm' THEN
        _key := 'ltimindtree';
    END IF;

    -- Trailing corporate suffixes, several at once
    -- ("Technum Opus Private Limited", "Convexicon India Pvt. Ltd").
    _key := regexp_replace(_key,
        '(\s+(private limited|pvt limited|pvt\.?|ltd\.?|limited|inc\.?|llc|corp\.?|corporation|usi|co|technologies|technology|ai))+$',
        '');

    -- Punctuation left behind ("Coforge.", "ZopSmart Technology.").
    _key := regexp_replace(_key, '[.\s]+$', '');

    -- One more suffix pass for "Pvt. Ltd" style leftovers.
    _key := regexp_replace(_key,
        '(\s+(private limited|pvt limited|pvt\.?|ltd\.?|limited|inc\.?|llc|corp\.?|corporation|usi|co|technologies|technology|ai))+$',
        '');

    -- Canonical brand aliases.  One side of a SuperSet pair spells the brand
    -- and the other spells the descriptive name - or carries something the
    -- passes above deliberately do not strip (".io", or a hyphenated
    -- campaign name).  Without this the offer company never equals the job
    -- company, the sync skips the whole company and its students show up as
    -- "zero mapping" on the dashboard.  Pick ONE key per real company.
    IF _key IN ('cisco-code with cisco', 'code with cisco') THEN
        _key := 'cisco';
    ELSIF _key IN ('convexicon india', 'convexicon india pvt ltd') THEN
        _key := 'convexicon';
    ELSIF _key IN ('prosperr.io', 'prosperr io') THEN
        _key := 'prosperr';
    ELSIF _key IN ('indus valley partners', 'indus valley partners india') THEN
        _key := 'ivp';
    END IF;

    RETURN trim(_key);
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1b. READ-SIDE ONLY: roll number -> branch, and roll number -> admission year.
--
-- Mirrors placement_pipeline/app/domain/roll_mapper.py::resolve_branch, which
-- is a verbatim port of the reference repo
-- services/placement/analysis/helpers.py:84-121.
-- KEEP THE RANGE LIST BELOW IDENTICAL TO app/domain/enrollment_ranges.py:
-- app/tests/test_roll_mapper.py compares both implementations and fails on
-- any drift.
--
-- Decision order is the reference's, byte for byte:
--   falsy -> "Other" | alpha -> "JUIT" | digits like '24%' -> "MTech"
--   | 9 digits -> "JUIT" | no digits -> "Other" | half-open range lookup.
-- The ranges are mutually disjoint, so a single LIMIT 1 is unambiguous.
CREATE OR REPLACE FUNCTION fn_branch_from_roll_v1(_roll text) RETURNS text AS $function$
DECLARE
    _digits text;
    _num    bigint;
BEGIN
    IF _roll IS NULL OR btrim(_roll) = '' THEN
        RETURN 'Other';
    END IF;

    IF _roll ~ '[[:alpha:]]' THEN
        RETURN 'JUIT';
    END IF;

    _digits := regexp_replace(_roll, '\D', '', 'g');

    IF _digits LIKE '24%' THEN
        RETURN 'MTech';
    END IF;

    IF length(_digits) = 9 THEN
        RETURN 'JUIT';
    END IF;

    IF _digits = '' THEN
        RETURN 'Other';
    END IF;

    BEGIN
        _num := _digits::bigint;
    EXCEPTION WHEN others THEN
        RETURN 'Other';
    END;

    RETURN COALESCE((
        SELECT r.branch
        FROM (
            VALUES ('CSE',         22103000::bigint,    22104000::bigint),
                   ('CSE',         9922103000::bigint,  9922104000::bigint),
                   ('ECE',         22102000::bigint,    22103000::bigint),
                   ('ECE',         9922102000::bigint,  9922103000::bigint),
                   ('IT',          22104000::bigint,    22105000::bigint),
                   ('BT',          22101000::bigint,    22102000::bigint),
                   ('Intg. MTech', 21803000::bigint,    21804000::bigint),
                   ('Intg. MTech', 21802000::bigint,    21803000::bigint),
                   ('Intg. MTech', 21801000::bigint,    21802000::bigint),
                   ('CSE',         23103000::bigint,    23104000::bigint),
                   ('CSE',         9923103000::bigint,  9923104000::bigint),
                   ('ECE',         23102000::bigint,    23103000::bigint),
                   ('ECE',         9923102000::bigint,  9923103000::bigint),
                   ('EC-ACT',      23119000::bigint,    23120000::bigint),
                   ('EE-VLSI',     23118000::bigint,    23119000::bigint),
                   ('IT',          23104000::bigint,    23105000::bigint),
                   ('BT',          23101000::bigint,    23102000::bigint),
                   ('Intg. MTech', 22903000::bigint,    22904000::bigint),
                   ('Intg. MTech', 22802000::bigint,    22803000::bigint),
                   ('Intg. MTech', 22801000::bigint,    22802000::bigint),
                   -- OUR ADDITION - mirrors CSE-22803 in
                   -- placement_pipeline/app/domain/enrollment_ranges.py.  The
                   -- reference's 22903xxx CSE series above matches zero live
                   -- rolls; the real 2022 Intg. MTech CSE series is
                   -- 22803001..22803031.  docs/roll_to_branch_mapping.md
                   -- open item 1.
                   ('Intg. MTech', 22803000::bigint,    22804000::bigint)
        ) AS r(branch, start_no, end_no)
        WHERE r.start_no <= _num AND _num < r.end_no
        LIMIT 1
    ), 'Other');
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1b(ii). Admission year from the roll prefix: 'YY.......' -> 20YY after
-- dropping a leading '99' campus prefix.  NOT in the reference repo - the
-- reference is handed a placement year by its caller instead - see
-- docs/roll_to_branch_mapping.md.  Returns NULL rather than guessing.
CREATE OR REPLACE FUNCTION fn_batch_year_from_roll_v1(_roll text) RETURNS integer AS $function$
DECLARE
    _digits text;
    _core   text;
    _year   integer;
BEGIN
    IF _roll IS NULL OR btrim(_roll) = '' THEN
        RETURN NULL;
    END IF;

    IF _roll ~ '[[:alpha:]]' THEN
        RETURN NULL;
    END IF;

    _digits := regexp_replace(_roll, '\D', '', 'g');

    -- Same precedence as fn_branch_from_roll_v1: the hardcoded MTech prefix
    -- wins over the 9-digit JUIT rule, so an MTech roll still gets a year.
    IF _digits LIKE '24%' THEN
        _core := _digits;
    ELSIF length(_digits) = 9 OR _digits = '' THEN
        RETURN NULL;
    ELSIF length(_digits) >= 10 AND _digits LIKE '99%' THEN
        -- '99' + 8 digits, or '99' + 10 digits: strip only when a real roll
        -- remains (>= 10 digits total), so '99999999' keeps its prefix.
        _core := substr(_digits, 3);
    ELSE
        _core := _digits;
    END IF;

    IF length(_core) < 2 THEN
        RETURN NULL;
    END IF;

    _year := 2000 + substring(_core FROM 1 FOR 2)::integer;

    IF _year < 2015 OR _year > 2035 THEN
        RETURN NULL;
    END IF;

    RETURN _year;
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1c. READ-SIDE ONLY: canonicalise a role so the dashboard groups one offer
--     family once instead of five times.  The model and the table cells emit
--     "Specialist Programmer (L1, L2, L3)" / "(L1, L2)" / "- L1" / a wrapped
--     "Digital\nSpecialist Engineer" for what is the same role family, and
--     fn_api_select_company_placements_v1 groups by the raw string - so the
--     Infosys rollup split 45 / 26 across two strings that render identically.
--     Deterministic, no keyword list: only the tier separator and the level
--     token are touched, so "Engineer, Senior" keeps its comma.
CREATE OR REPLACE FUNCTION fn_norm_role_v1(_role text) RETURNS text AS $function$
DECLARE
    _r text;
BEGIN
    IF _role IS NULL OR btrim(_role) = '' THEN
        RETURN NULL;
    END IF;

    -- A non-breaking space survives every other strip (UTF-8, not regex \s).
    _r := replace(_role, chr(160), ' ');
    _r := btrim(regexp_replace(_r, '\s+', ' ', 'g'));

    -- "(Trainee)" names the contract PHASE, not a different seat.  The mail
    -- emits "Specialist Programmer - L1 (Trainee)" (8 Sep list) and
    -- "Specialist Programmer - L1" (21 Sep list) for the same offer, which
    -- rendered as two rows on the card.  Scoped to that one word - a bare
    -- "Systems Engineer Trainee" keeps its suffix, and "(L1, L2, L3)" is
    -- untouched because it is matched here first, before the tier split.
    _r := regexp_replace(_r, '\s*\(\s*[Tt][Rr][Aa][Ii][Nn][Ee][Ee]\s*\)', '', 'g');

    -- "(L1, L2, L3)" -> "(L1/L2/L3)".  Lookahead scope keeps an ordinary
    -- comma ("Engineer, Senior") out of the substitution.
    _r := regexp_replace(_r, '\s*,\s*(?=[Ll][0-9]+)', '/', 'g');

    -- l1 -> L1 wherever a lower-case level token survived the split.
    _r := regexp_replace(_r, '(^|[^A-Za-z0-9])[lL]([0-9]+)', '\1L\2', 'g');

    -- Wrapped cells leave " - " / " / " runs behind; canonicalise each.
    _r := regexp_replace(_r, '\s*/\s*', ' / ', 'g');
    _r := regexp_replace(_r, '\s*-\s*', ' - ', 'g');
    _r := btrim(regexp_replace(_r, '\s+', ' ', 'g'));

    -- "Specialist Programmer L3" (the job's own packageinfo) and "Specialist
    -- Programmer - L3" (the offer cell) are the same seat: pick the dashed
    -- form so both sides of the rollup land in one bucket.  "-" and "/" are
    -- excluded, so an already-dashed "- L1" is left alone and "L1 / L2" does
    -- not grow a second dash.
    _r := regexp_replace(_r, '(^|[^-/\s]) +L([0-9]+)', '\1 - L\2', 'g');
    _r := btrim(regexp_replace(_r, '\s+', ' ', 'g'));

    -- Trailing separator a wrapped first cell can leave ("DSE Engineer /").
    _r := btrim(_r, ' /-');

    IF _r = '' THEN
        RETURN NULL;
    END IF;
    RETURN _r;
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1d. Role -> job-profile overlap, used by the v2 sync to pick ONE job per
--     student.  v1 linked the offer's company to every Jobs row of that
--     company, which is what put all 88 Infosys students on "Systems
--     Engineer Trainee" although not one of them holds that offer.
--     Returns the count of shared significant tokens (>= 3 chars, minus
--     connectives); ties are broken by status/posting date in the caller.
CREATE OR REPLACE FUNCTION fn_role_job_score_v1(_role text, _profile text)
RETURNS integer AS $function$
DECLARE
    _prof text[];
BEGIN
    _prof := regexp_split_to_array(lower(COALESCE(fn_norm_role_v1(_profile), '')),
                                   '[^a-z0-9]+');

    RETURN (
        SELECT COUNT(DISTINCT u.t)
        FROM unnest(regexp_split_to_array(lower(COALESCE(fn_norm_role_v1(_role), '')),
                                          '[^a-z0-9]+')) AS u(t)
        WHERE length(u.t) >= 3
          AND u.t NOT IN ('the', 'and', 'for', 'with', 'any', 'our', 'job',
                          'role', 'post', 'opening', 'hire', 'hiring',
                          'position', 'vacancy')
          AND u.t = ANY(_prof)
    );
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1e. READ-SIDE ONLY: roll number -> campus.
--
-- enrollment_ranges keys every branch's ranges by campus - the literal keys
-- "62" and "128" - and enrollment_ranges.CAMPUS_PREFIX ("99") is what
-- separates a Sector 62 range from its Sector 128 twin (CSE
-- 22103000-22104000 vs 9922103000-9922104000).  JIIT has exactly two Noida
-- campuses: Sector 62 (main) and Sector 128 (Wish Town); alpha and
-- 9-digit rolls are JUIT Solan, per fn_branch_from_roll_v1.
-- Decision order mirrors fn_branch_from_roll_v1 so a roll can never land on
-- one branch here and a different campus there.
CREATE OR REPLACE FUNCTION fn_campus_from_roll_v1(_roll text) RETURNS text AS $function$
DECLARE
    _digits text;
BEGIN
    IF _roll IS NULL OR btrim(_roll) = '' THEN
        RETURN 'Other';
    END IF;

    IF _roll ~ '[[:alpha:]]' THEN
        RETURN 'JUIT';
    END IF;

    _digits := regexp_replace(_roll, '\D', '', 'g');

    IF _digits = '' THEN
        RETURN 'Other';
    END IF;

    -- The '99' two-digit campus prefix -> Sector 128 (Wish Town).
    IF length(_digits) >= 10 AND _digits LIKE '99%' THEN
        RETURN 'Sector 128';
    END IF;

    -- Same precedence as fn_branch_from_roll_v1: the MTech '24' prefix beats
    -- the 9-digit rule, so an MTech roll keeps its JIIT campus instead of
    -- being filed under JUIT Solan.
    IF length(_digits) = 9 AND _digits NOT LIKE '24%' THEN
        RETURN 'JUIT';
    END IF;

    -- Everything else - plain 8-digit JIIT rolls, the '24' MTech prefix and
    -- out-of-range years - is JIIT Noida.
    RETURN 'Sector 62';
END;
$function$ LANGUAGE plpgsql IMMUTABLE;

-- 1f. READ-SIDE ONLY: roll rule + the email's own ``University`` cell, merged
--     into one displayable campus.
--
-- Neither source is complete on its own:
--   * the ROLL RULE knows Sector 62 vs Sector 128 (the '99' prefix) but the
--     reference port maps every alpha roll to "JUIT", which is wrong - the
--     corpus contains JUET Guna students on rolls like 231B007 whose
--     ``University`` cell says "JUET Guna" outright;
--   * the CELL cannot tell Sector 62 from Sector 128 at all ("JIIT Noida").
-- So the cell only overrides when it names a DIFFERENT institution family;
-- for JIIT the roll stays authoritative.  Case/space noise in the cell
-- ("JIIT NOIDA" vs "JIIT Noida") is irrelevant because it never wins.
CREATE OR REPLACE FUNCTION fn_campus_resolved_v1(_roll text, _cell text)
RETURNS text AS $function$
DECLARE
    _c text;
BEGIN
    _c := upper(replace(COALESCE(_cell, ''), chr(160), ' '));
    _c := btrim(regexp_replace(_c, '\s+', ' ', 'g'));

    IF _c LIKE '%JUET%' THEN
        RETURN 'JUET Guna';
    END IF;
    -- "JIIT" is deliberately NOT matched here: J-I-I-T is never J-U-I-T.
    IF _c LIKE '%JUIT%' THEN
        RETURN 'JUIT';
    END IF;

    RETURN fn_campus_from_roll_v1(_roll);
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

-- 2b. Materialised roll -> branch / campus / batch-year lookup.
--
-- READ-SIDE CONVENIENCE ONLY: this table never feeds the sync and every one
-- of its values is re-derivable from the roll alone, so a stale row is a
-- reporting defect and can never become a data-integrity one.
--
-- `branch` / `campus` / `batch_year` are the roll-rule answers; the
-- `*_extracted` columns keep the value the email table actually carried
-- (``University`` for campus, ``Branch`` for branch) so the two can be
-- compared per student instead of being silently conflated - the rule wins
-- when the cell is missing, the cell wins when it is present.
CREATE TABLE IF NOT EXISTS student_branch_campus (
    roll_no            text NOT NULL,
    student_name       text,
    branch             text NOT NULL,
    branch_extracted   text,
    campus             text NOT NULL,
    campus_extracted   text,
    batch_year         integer,
    updated_at         timestamp with time zone NOT NULL DEFAULT NOW(),
    CONSTRAINT PK_student_branch_campus PRIMARY KEY (roll_no)
);

CREATE INDEX IF NOT EXISTS IX_student_branch_campus_branch ON student_branch_campus (branch);
CREATE INDEX IF NOT EXISTS IX_student_branch_campus_campus ON student_branch_campus (campus);
CREATE INDEX IF NOT EXISTS IX_student_branch_campus_batch  ON student_branch_campus (batch_year);

-- Idempotent upsert over every enrollment number the pipeline has ever seen.
-- `prio` orders the union so a roll known to the offer parser (the most
-- complete row) supplies the name and the extracted cells before a
-- shortlist-only or mapping-only sighting does.  Re-running without any new
-- mail touches zero rows.
CREATE OR REPLACE FUNCTION fn_refresh_student_branch_campus_v1() RETURNS text AS $function$
DECLARE
    _changed integer := 0;
BEGIN
    INSERT INTO student_branch_campus (
        roll_no, student_name, branch, branch_extracted,
        campus, campus_extracted, batch_year, updated_at
    )
    SELECT DISTINCT ON (s.roll_no)
           s.roll_no, s.student_name, s.branch, s.branch_extracted,
           s.campus, s.campus_extracted, s.batch_year, NOW()
    FROM (
        SELECT btrim(os.roll_no)                 AS roll_no,
               NULLIF(trim(os.name), '')         AS student_name,
               fn_branch_from_roll_v1(btrim(os.roll_no))  AS branch,
               NULLIF(trim(os.branch), '')       AS branch_extracted,
               fn_campus_resolved_v1(btrim(os.roll_no), os.college)  AS campus,
               NULLIF(trim(os.college), '')      AS campus_extracted,
               fn_batch_year_from_roll_v1(btrim(os.roll_no)) AS batch_year,
               0 AS prio
        FROM offer_students os
        WHERE os.roll_no IS NOT NULL AND btrim(os.roll_no) <> ''

        UNION ALL
        SELECT btrim(ss.roll_no), NULLIF(trim(ss.name), ''),
               fn_branch_from_roll_v1(btrim(ss.roll_no)), NULLIF(trim(ss.branch), ''),
               fn_campus_resolved_v1(btrim(ss.roll_no), ss.college), NULLIF(trim(ss.college), ''),
               fn_batch_year_from_roll_v1(btrim(ss.roll_no)), 1
        FROM shortlist_students ss
        WHERE ss.roll_no IS NOT NULL AND btrim(ss.roll_no) <> ''

        UNION ALL
        SELECT btrim(jps.student_roll_no), NULLIF(trim(jps.student_name), ''),
               fn_branch_from_roll_v1(btrim(jps.student_roll_no)), NULL,
               fn_campus_from_roll_v1(btrim(jps.student_roll_no)), NULL,
               fn_batch_year_from_roll_v1(btrim(jps.student_roll_no)), 2
        FROM job_placed_students jps
        WHERE jps.student_roll_no IS NOT NULL AND btrim(jps.student_roll_no) <> ''
    ) s
    ORDER BY s.roll_no, s.prio
    ON CONFLICT (roll_no) DO UPDATE
        SET student_name     = COALESCE(EXCLUDED.student_name,
                                        student_branch_campus.student_name),
            branch           = EXCLUDED.branch,
            branch_extracted = COALESCE(EXCLUDED.branch_extracted,
                                        student_branch_campus.branch_extracted),
            campus           = EXCLUDED.campus,
            campus_extracted = COALESCE(EXCLUDED.campus_extracted,
                                        student_branch_campus.campus_extracted),
            batch_year       = EXCLUDED.batch_year,
            updated_at       = NOW()
    WHERE student_branch_campus.branch          IS DISTINCT FROM EXCLUDED.branch
       OR student_branch_campus.campus          IS DISTINCT FROM EXCLUDED.campus
       OR student_branch_campus.batch_year      IS DISTINCT FROM EXCLUDED.batch_year
       OR student_branch_campus.student_name    IS DISTINCT FROM EXCLUDED.student_name
       OR student_branch_campus.branch_extracted IS DISTINCT FROM EXCLUDED.branch_extracted
       OR student_branch_campus.campus_extracted IS DISTINCT FROM EXCLUDED.campus_extracted;

    GET DIAGNOSTICS _changed = ROW_COUNT;

    RETURN json_build_object(
        'status', 'SUCCESS',
        'message', 'student_branch_campus refreshed',
        'rowsChanged', _changed,
        'rowsTotal', (SELECT COUNT(*) FROM student_branch_campus),
        'lastRunAt', NOW()
    )::text;
END;
$function$ LANGUAGE plpgsql;

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

-- 3b. Sync v2 - SAME statistics contract as v1, but exactly ONE job per
--     (company, student).
--
-- v1 linked an offer's company to EVERY Jobs row of that company, so a
-- company with 7 jobs (Procol) showed 140 placed rows for 20 students and
-- "Systems Engineer Trainee" showed all 88 Infosys students although not one
-- of them holds that offer.  v2 scores every candidate job of the company
-- against the offer's own role (fn_role_job_score_v1), keeps only the winner,
-- and drops the rows v1 wrote for jobs that student was never offered.
--
-- v1 is deliberately left untouched so the original behaviour stays
-- reproducible; this function is additive.
CREATE OR REPLACE FUNCTION fn_api_sync_offer_students_v2() RETURNS text AS $function$
DECLARE
    _jobs_total              integer;
    _students_considered     integer;
    _companies_total         integer;
    _companies_matched       integer;
    _companies_skipped       integer;
    _candidates              integer := 0;
    _removed                 integer := 0;
    _inserted                integer := 0;
    _jobs_matched            integer := 0;
    _students_mapped         integer := 0;
    _total_mappings          integer := 0;
    _result                  json;
BEGIN
    SELECT COUNT(*) INTO _jobs_total FROM jobs;

    SELECT COUNT(DISTINCT trim(os.roll_no)) INTO _students_considered
    FROM offer_students os
    WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> '';

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

    -- One statement, so `del` / `ins` / `keep` all read the SAME snapshot:
    -- `keep` can therefore still see the pre-delete placed_at, which is what
    -- preserves the earliest date when a student's job changes.
    WITH best AS (
        -- earliest offer per (company, student) -> exactly one winning job
        SELECT o_row.ckey,
               o_row.roll_no,
               o_row.student_name,
               o_row.offer_email_id,
               o_row.company_name,
               o_row.offer_role,
               picked.job_id,
               picked.score
        FROM (
            SELECT DISTINCT ON (fn_norm_company_v1(c.name), trim(os.roll_no))
                   fn_norm_company_v1(c.name) AS ckey,
                   trim(os.roll_no)           AS roll_no,
                   NULLIF(trim(os.name), '')  AS student_name,
                   o.email_id                 AS offer_email_id,
                   c.name                     AS company_name,
                   COALESCE(NULLIF(trim(os.role), ''),
                            NULLIF(trim(o.role), '')) AS offer_role
            FROM offer_students os
            JOIN offers o ON o.id = os.offer_id
            JOIN companies c ON c.id = o.company_id
            WHERE os.roll_no IS NOT NULL AND trim(os.roll_no) <> ''
              AND o.email_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM emails e WHERE e.id = o.email_id)
            ORDER BY fn_norm_company_v1(c.name), trim(os.roll_no),
                     o.created_at, o.id
        ) o_row
        CROSS JOIN LATERAL (
            SELECT j.id AS job_id,
                   fn_role_job_score_v1(o_row.offer_role, j.jobprofile) AS score
            FROM jobs j
            WHERE fn_norm_company_v1(j.company) = o_row.ckey
            ORDER BY 2 DESC,
                     (j.status = 'Active') DESC,
                     j.posteddatetime DESC NULLS LAST,
                     j.id
            LIMIT 1
        ) picked
    ),
    keep AS (
        -- earliest placed_at per (company, student), read pre-delete
        SELECT DISTINCT ON (jps.student_roll_no,
                            fn_norm_company_v1(jps.company_name))
               jps.student_roll_no AS roll_no,
               fn_norm_company_v1(jps.company_name) AS ckey,
               jps.placed_at
        FROM job_placed_students jps
        ORDER BY jps.student_roll_no,
                 fn_norm_company_v1(jps.company_name),
                 jps.placed_at, jps.id
    ),
    del AS (
        -- any row that is not the chosen job for that student: the fan-out
        DELETE FROM job_placed_students jps
        WHERE NOT EXISTS (
            SELECT 1 FROM best b
            WHERE b.roll_no = jps.student_roll_no
              AND b.job_id  = jps.job_id
        )
        RETURNING jps.id
    ),
    ins AS (
        INSERT INTO job_placed_students
               (job_id, student_roll_no, student_name, offer_email_id,
                company_name, placed_at)
        SELECT b.job_id, b.roll_no, b.student_name, b.offer_email_id,
               b.company_name,
               COALESCE((SELECT k.placed_at FROM keep k
                         WHERE k.roll_no = b.roll_no AND k.ckey = b.ckey),
                        NOW())
        FROM best b
        WHERE NOT EXISTS (
            SELECT 1 FROM job_placed_students j
            WHERE j.job_id = b.job_id
              AND j.student_roll_no = b.roll_no
        )
        ON CONFLICT (job_id, student_roll_no) DO NOTHING
        RETURNING job_placed_students.id
    )
    SELECT (SELECT COUNT(*) FROM best),
           (SELECT COUNT(*) FROM del),
           (SELECT COUNT(*) FROM ins)
    INTO _candidates, _removed, _inserted;

    SELECT COUNT(DISTINCT job_id), COUNT(DISTINCT student_roll_no), COUNT(*)
    INTO _jobs_matched, _students_mapped, _total_mappings
    FROM job_placed_students;

    SELECT json_build_object(
        'status', 'SUCCESS',
        'message', 'Offer-student sync completed',
        'syncVersion', 'v2',
        'jobsTotal', _jobs_total,
        'jobsMatched', _jobs_matched,
        'jobsWithoutPlacements', GREATEST(_jobs_total - _jobs_matched, 0),
        'studentsConsidered', _students_considered,
        'studentsMapped', _students_mapped,
        'mappingsInserted', _inserted,
        'mappingsRemoved', _removed,
        'duplicatesSkipped', GREATEST(_candidates - _inserted, 0),
        'candidatesScored', _candidates,
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
                       em.received_at AS offerreceivedat,
                       fn_branch_from_roll_v1(jps.student_roll_no) AS branchfromroll,
                       fn_batch_year_from_roll_v1(jps.student_roll_no) AS batchyear,
                       -- roll rule -> campus (Sector 62 / Sector 128 / JUIT)
                       fn_campus_from_roll_v1(jps.student_roll_no) AS campusfromroll,
                       -- the ``University`` cell the offer table actually
                       -- carried; blank until the LLM path stopped dropping it
                       off.campusextracted,
                       -- what the UI shows: rule, overridden only when the
                       -- cell names a different institution (JUET Guna)
                       fn_campus_resolved_v1(jps.student_roll_no,
                                             off.campusextracted) AS campus,
                       -- canonical grouping key for the raw off.role above
                       fn_norm_role_v1(off.role) AS rolelevel
                FROM job_placed_students jps
                LEFT JOIN LATERAL (
                    SELECT os2.branch, os2.program, os2.email,
                           os2.college AS campusextracted,
                           COALESCE(NULLIF(trim(os2.role), ''), NULLIF(trim(o2.role), '')) AS role,
                           o2.ctc_raw AS ctcraw, o2.ctc_total AS ctctotal, o2.ctc_basis AS ctcbasis,
                           o2.stipend AS stipend, o2.employment_type AS employmenttype
                    FROM offer_students os2
                    JOIN offers o2 ON o2.id = os2.offer_id
                    JOIN companies c2 ON c2.id = o2.company_id
                    WHERE trim(os2.roll_no) = jps.student_roll_no
                      AND fn_norm_company_v1(c2.name) = fn_norm_company_v1(jps.company_name)
                    -- WHICH offer represents this student on this job.
                    --
                    -- Ascending (the original) meant the FIRST row ever
                    -- ingested won forever, so a later mail never corrected
                    -- an earlier one. It also meant a student whose
                    -- per-student role was blank on that first row fell back
                    -- to the email-wide guess — which is how Arjun Gupta
                    -- (23103022) could be congratulated on Specialist
                    -- Programmer L1 while his row still read Digital
                    -- Specialist Engineer. 26 of the 420 placed rows were
                    -- wrong this way.
                    --
                    -- Descending: a later mail is a later decision, so a
                    -- corrected, upgraded or converted role supersedes the
                    -- original. On top of that, a role read off THIS
                    -- student's own row outranks recency — an email-level
                    -- role is one inference shared by everyone on that
                    -- message, and the extractor is fallible enough (14
                    -- blank roles, 16 blank rolls) that a newer row should
                    -- not be able to mask a known one.
                    --
                    -- Third, a row that actually names a package outranks
                    -- one that does not. This is not a trade of accuracy for
                    -- a number: the two Josh Technology rows for 9923103225
                    -- are the SAME forwarded mail extracted four seconds
                    -- apart, one capturing the package and the other the
                    -- fuller role title. Preferring the stated package keeps
                    -- ₹15,88,000 on screen instead of blanking it, and the
                    -- role it shows ("Software Developer") is exactly what
                    -- that message said.
                    --
                    -- Measured across all 420 placed rows: 26 roles change,
                    -- 6 blank roles become 0, 195 blank packages become
                    -- 186, and no row regresses.
                    ORDER BY (NULLIF(trim(os2.role), '') IS NULL),
                             (o2.ctc_total IS NULL
                              AND NULLIF(trim(o2.ctc_raw), '') IS NULL),
                             o2.created_at DESC,
                             o2.id DESC
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
               -- grouped on the CANONICAL role: raw strings like
               -- "(L1, L2, L3)" vs "(L1, L2)" used to render as two
               -- identical-looking rows (45 / 26 for Infosys)
               COALESCE(fn_norm_role_v1(p.role), 'Not specified') AS role,
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
    company_role_families AS (
        -- A role bucket reduced to its first two significant words, so that
        -- "Specialist Programmer - L1" and a packageinfo label saying
        -- "Specialist Programmer L3" can be seen as one family.
        SELECT ckey, role, students, ctcmax,
               regexp_replace(
                   btrim(regexp_replace(lower(role), '[^a-z0-9]+', ' ', 'g')),
                   '^([^ ]+ [^ ]+).*$', '\1') AS fam
        FROM company_role_counts
    ),
    company_role_catalog AS (
        -- The card must also show what the job ADVERTISES but nobody has
        -- landed yet, otherwise "Specialist Programmer - L3" is invisible
        -- even though the seat exists and holds zero students.  packageinfo
        -- is hand-written HTML, so a label qualifies only when it normalises
        -- to a role of a family that really does carry students: that one
        -- guard rejects all 41 labels elsewhere that are actually "Stipend
        -- during Internship", "Total CTC", "Duration of Internship", ...
        -- ``[^<]*`` keeps nested markup (which is always prose, never a
        -- role) out of the capture instead of tagging it back in.
        SELECT DISTINCT x.ck AS ckey, x.role
        FROM (
            SELECT jc.ckey AS ck,
                   fn_norm_role_v1(btrim(split_part(
                       replace(replace(m.mm[1], '&nbsp;', ' '), '&amp;', '&'),
                       ':', 1))) AS role
            FROM job_company jc
            CROSS JOIN LATERAL regexp_matches(
                       coalesce(jc.packageinfo, ''),
                       '<li[^>]*>([^<]*)</li>', 'gi') AS m(mm)
        ) x
        WHERE x.role IS NOT NULL AND length(x.role) <= 70
    ),
    company_roles AS (
        SELECT ckey,
               json_agg(json_build_object('role', role, 'students', students, 'ctcmax', ctcmax)
                        ORDER BY students DESC, role) AS roles
        FROM (
            SELECT ckey, role, students, ctcmax FROM company_role_families
            UNION ALL
            -- an advertised seat nobody has filled yet, shown as 0
            SELECT k.ckey, k.role, 0, NULL
            FROM company_role_catalog k
            WHERE NOT EXISTS (
                      SELECT 1 FROM company_role_families a
                      WHERE a.ckey = k.ckey AND a.role = k.role)
              AND EXISTS (
                      SELECT 1 FROM company_role_families b
                      WHERE b.ckey = k.ckey
                        AND b.fam = regexp_replace(
                                btrim(regexp_replace(lower(k.role),
                                                     '[^a-z0-9]+', ' ', 'g')),
                                '^([^ ]+ [^ ]+).*$', '\1'))
        ) u
        GROUP BY ckey
    ),
    -- One row per (company, student); branch / campus come from the roll
    -- rule, so these three arrays always sum to `placedstudents`.
    company_student AS (
        SELECT DISTINCT ON (jc.ckey, jps.student_roll_no)
               jc.ckey, jps.student_roll_no
        FROM job_placed_students jps
        JOIN job_company jc ON jc.id = jps.job_id
    ),
    company_branch_counts AS (
        -- The roll rule is canonical (CSE / ECE / IT / MTech …) and wins
        -- whenever it lands on a real branch.  "Other" and "JUIT" both mean
        -- "our ranges did not resolve this roll" (the 22803xxx series, and
        -- every alpha roll such as 231B007), so the branch the email itself
        -- named is what fills those holes.
        SELECT cs.ckey,
               CASE
                   WHEN fn_branch_from_roll_v1(cs.student_roll_no)
                        NOT IN ('Other', 'JUIT')
                       THEN fn_branch_from_roll_v1(cs.student_roll_no)
                   ELSE COALESCE(NULLIF(sbc.branch_extracted, ''),
                                 fn_branch_from_roll_v1(cs.student_roll_no))
               END AS branch,
               COUNT(*) AS students
        FROM company_student cs
        LEFT JOIN student_branch_campus sbc ON sbc.roll_no = cs.student_roll_no
        GROUP BY 1, 2
    ),
    company_campus_counts AS (
        -- Resolved campus: the roll's '99' prefix splits Sector 62 / 128,
        -- the ``University`` cell only overrides for a different institution
        -- (JUET Guna).  Falls back to the raw roll rule if the table has not
        -- been refreshed yet.
        SELECT cs.ckey,
               COALESCE(sbc.campus,
                        fn_campus_from_roll_v1(cs.student_roll_no)) AS campus,
               COUNT(*) AS students
        FROM company_student cs
        LEFT JOIN student_branch_campus sbc ON sbc.roll_no = cs.student_roll_no
        GROUP BY 1, 2
    ),
    company_branches AS (
        SELECT ckey,
               json_agg(json_build_object('branch', branch, 'students', students)
                        ORDER BY students DESC, branch) AS branches
        FROM company_branch_counts
        GROUP BY ckey
    ),
    company_campuses AS (
        SELECT ckey,
               json_agg(json_build_object('campus', campus, 'students', students)
                        ORDER BY students DESC, campus) AS campuses
        FROM company_campus_counts
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
               COALESCE(cr.roles, '[]'::json) AS roles,
               COALESCE(cbr.branches, '[]'::json) AS branches,
               COALESCE(ccm.campuses, '[]'::json) AS campuses
        FROM company_jobs cj
        LEFT JOIN company_placed cp ON cp.ckey = cj.ckey
        LEFT JOIN company_roles cr ON cr.ckey = cj.ckey
        LEFT JOIN company_branches cbr ON cbr.ckey = cj.ckey
        LEFT JOIN company_campuses ccm ON ccm.ckey = cj.ckey
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

-- 6b. Email notice detail - the "Read more" panel for ONE email.
--     Additive companion to fn_api_select_email_notices_v1 (the feed only
--     ships a 300-char snippet so the list stays light): full body, the
--     parsed shortlist student rows, funnel counts WITH their evidence
--     sentence, attachments and the event extras the feed has no room for.
--     Miss-shape for an unknown / non-canonical id: {"found": false}.
CREATE OR REPLACE FUNCTION fn_api_select_email_notice_detail_v1(
    _emailid text) RETURNS text AS $function$
DECLARE
    _e record;
    _body text;
    _bodylength integer;
    _students json;
    _rounds json;
    _attachments json;
BEGIN
    SELECT e.id,
           e.gmail_message_id AS gmailmessageid,
           e.subject,
           LEFT(COALESCE(e.snippet, e.body_clean, e.body_text, ''), 300) AS snippet,
           e.sender,
           e.sender_email AS senderemail,
           e.recipient,
           e.cc,
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
           se.stage AS stage,
           se.stage_raw AS stageraw,
           COALESCE(se.interview_dates, '[]'::json) AS interviewdates,
           NULLIF(se.evidence, '') AS evidence,
           NULLIF(op.career_note, '') AS careernote,
           COALESCE(op.stages, '[]'::json) AS opstages,
           COALESCE(op.eligibility, '[]'::json) AS eligibility,
           se.id AS eventid,
           COALESCE(e.body_clean, e.body_text, '') AS rawbody
    INTO _e
    FROM emails e
    LEFT JOIN shortlist_events se ON se.email_id = e.id
    LEFT JOIN opportunities op ON op.email_id = e.id
    LEFT JOIN companies co ON co.id = COALESCE(se.company_id, op.company_id)
    WHERE e.id = _emailid
      AND e.is_canonical = TRUE
      AND e.dedup_of IS NULL;

    IF NOT FOUND THEN
        RETURN json_build_object('found', FALSE)::text;
    END IF;

    -- Body ships whole but capped (live max: 139,129 chars); the untouched
    -- length travels along so the UI can disclose the truncation honestly.
    _body := LEFT(_e.rawbody, 60000);
    _bodylength := LENGTH(_e.rawbody);

    SELECT COALESCE(json_agg(json_build_object(
               'rollno', ss.roll_no, 'name', ss.name, 'branch', ss.branch,
               'program', ss.program, 'college', ss.college,
               'status', ss.status_raw)
               ORDER BY ss.roll_no NULLS LAST, ss.name), '[]'::json)
    INTO _students
    FROM shortlist_students ss
    WHERE ss.shortlist_event_id = _e.eventid;

    SELECT COALESCE(json_agg(json_build_object(
               'round', fc.round_name, 'count', fc.count,
               'evidence', fc.evidence)
               ORDER BY fc.round_order), '[]'::json)
    INTO _rounds
    FROM funnel_counts fc
    WHERE fc.email_id = _e.id;

    SELECT COALESCE(json_agg(json_build_object(
               'filename', a.filename, 'mimetype', a.mime_type,
               'filesize', a.file_size)
               ORDER BY a.file_size DESC NULLS LAST, a.filename), '[]'::json)
    INTO _attachments
    FROM email_attachments a
    WHERE a.email_id = _e.id;

    RETURN json_build_object(
        'found', TRUE,
        'id', _e.id,
        'gmailmessageid', _e.gmailmessageid,
        'subject', _e.subject,
        'snippet', _e.snippet,
        'sender', _e.sender,
        'senderemail', _e.senderemail,
        'recipient', _e.recipient,
        'cc', _e.cc,
        'receivedat', _e.receivedat,
        'classification', _e.classification,
        'classificationlabel', _e.classificationlabel,
        'confidence', _e.confidence,
        'method', _e.method,
        'hasattachments', _e.hasattachments,
        'isrevision', _e.isrevision,
        'company', _e.company,
        'headline', _e.headline,
        'deadline', _e.deadline,
        'link', _e.link,
        'stage', _e.stage,
        'stageraw', _e.stageraw,
        'interviewdates', _e.interviewdates,
        'evidence', _e.evidence,
        'careernote', _e.careernote,
        'stages', _e.opstages,
        'eligibility', _e.eligibility,
        'body', _body,
        'bodylength', _bodylength,
        'studentcount', json_array_length(_students),
        'students', _students,
        'rounds', _rounds,
        'attachments', _attachments)::text;
END;
$function$ LANGUAGE plpgsql;
