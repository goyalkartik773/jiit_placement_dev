-- ================================================================
-- Migration: Student Placement Mapping System
-- Maps congratulations emails to jobs and students
-- ================================================================

-- 1. Student Placements table
CREATE TABLE IF NOT EXISTS studentplacements (
    id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
    gmailmessageid text,
    gmailmessageuuid text,
    sourcegroup text,
    sourcegroupemail text,
    studentname text,
    studentemail text,
    companyname text,
    jobprofile text,
    package text,
    location text,
    batch text,
    placementtype text,
    status text DEFAULT 'EXTRACTED',
    notes text,
    createdat timestamp with time zone DEFAULT NOW(),
    updatedat timestamp with time zone
);

CREATE INDEX IF NOT EXISTS idx_studentplacements_company ON studentplacements(companyname);
CREATE INDEX IF NOT EXISTS idx_studentplacements_student ON studentplacements(studentname);
CREATE INDEX IF NOT EXISTS idx_studentplacements_jobuuid ON studentplacements(jobuuid);
CREATE INDEX IF NOT EXISTS idx_studentplacements_messageid ON studentplacements(gmailmessageid);

-- 2. Add jobuuid column to link placement to a job
ALTER TABLE studentplacements ADD COLUMN IF NOT EXISTS jobuuid text;

-- 3. fn_api_insert_studentplacement_v001: Insert a student placement
CREATE OR REPLACE FUNCTION fn_api_insert_studentplacement_v001(
    _gmailmessageid text,
    _gmailmessageuuid text,
    _sourcegroup text,
    _sourcegroupemail text,
    _studentname text,
    _studentemail text,
    _companyname text,
    _jobprofile text,
    _package text,
    _location text,
    _batch text,
    _placementtype text,
    _jobuuid text,
    _notes text
) RETURNS text AS $function$
DECLARE _newid text;
DECLARE _existingid text;
BEGIN
    IF _gmailmessageid IS NULL OR TRIM(_gmailmessageid) = '' THEN
        RETURN json_build_object('status','ERROR','message','Gmail message ID is required');
    END IF;

    -- Check if already exists for this message + student combo
    SELECT id INTO _existingid FROM studentplacements 
    WHERE gmailmessageid = _gmailmessageid 
    AND LOWER(TRIM(studentname)) = LOWER(TRIM(COALESCE(_studentname, '')));

    IF _existingid IS NOT NULL THEN
        -- Update existing
        UPDATE studentplacements SET
            companyname = COALESCE(NULLIF(_companyname,''), companyname),
            jobprofile = COALESCE(NULLIF(_jobprofile,''), jobprofile),
            package = COALESCE(NULLIF(_package,''), package),
            location = COALESCE(NULLIF(_location,''), location),
            batch = COALESCE(NULLIF(_batch,''), batch),
            placementtype = COALESCE(NULLIF(_placementtype,''), placementtype),
            jobuuid = COALESCE(NULLIF(_jobuuid,''), jobuuid),
            notes = COALESCE(NULLIF(_notes,''), notes),
            updatedat = NOW()
        WHERE id = _existingid
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Student placement updated','id', _newid);
    ELSE
        -- Insert new
        INSERT INTO studentplacements (id, gmailmessageid, gmailmessageuuid, sourcegroup, sourcegroupemail,
            studentname, studentemail, companyname, jobprofile, package, location, batch, placementtype,
            jobuuid, notes, status, createdat)
        VALUES (gen_random_uuid()::text, _gmailmessageid, NULLIF(_gmailmessageuuid,''), 
            NULLIF(_sourcegroup,''), NULLIF(_sourcegroupemail,''),
            NULLIF(_studentname,''), NULLIF(_studentemail,''),
            NULLIF(_companyname,''), NULLIF(_jobprofile,''), NULLIF(_package,''),
            NULLIF(_location,''), NULLIF(_batch,''), NULLIF(_placementtype,''),
            NULLIF(_jobuuid,''), NULLIF(_notes,''), 'EXTRACTED', NOW())
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Student placement created','id', _newid);
    END IF;
END;
$function$ LANGUAGE plpgsql;

-- 4. fn_api_select_studentplacements_v001: Get placements with filters
CREATE OR REPLACE FUNCTION fn_api_select_studentplacements_v001(
    _page integer DEFAULT 1,
    _pagesize integer DEFAULT 50,
    _companyname text DEFAULT '',
    _studentname text DEFAULT '',
    _sourcegroup text DEFAULT '',
    _batch text DEFAULT '',
    _status text DEFAULT ''
) RETURNS text AS $function$
DECLARE _result jsonb;
BEGIN
    SELECT json_build_object(
        'items', COALESCE(json_agg(row_to_json(t)), '[]'::json),
        'total', (SELECT count(*) FROM studentplacements sp
                  WHERE (_companyname = '' OR LOWER(sp.companyname) LIKE '%' || LOWER(_companyname) || '%')
                  AND (_studentname = '' OR LOWER(sp.studentname) LIKE '%' || LOWER(_studentname) || '%')
                  AND (_sourcegroup = '' OR sp.sourcegroup = _sourcegroup)
                  AND (_batch = '' OR sp.batch = _batch)
                  AND (_status = '' OR sp.status = _status)),
        'page', _page,
        'pageSize', _pagesize
    ) INTO _result
    FROM (
        SELECT sp.*,
            j.company as job_company, j.jobprofile as job_profile, j.package as job_package
        FROM studentplacements sp
        LEFT JOIN jobs j ON j.id = sp.jobuuid
        WHERE (_companyname = '' OR LOWER(sp.companyname) LIKE '%' || LOWER(_companyname) || '%')
        AND (_studentname = '' OR LOWER(sp.studentname) LIKE '%' || LOWER(_studentname) || '%')
        AND (_sourcegroup = '' OR sp.sourcegroup = _sourcegroup)
        AND (_batch = '' OR sp.batch = _batch)
        AND (_status = '' OR sp.status = _status)
        ORDER BY sp.createdat DESC
        LIMIT _pagesize OFFSET (_page - 1) * _pagesize
    ) t;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;

-- 5. fn_api_select_placementsummary_v001: Summary by company
CREATE OR REPLACE FUNCTION fn_api_select_placementsummary_v001() RETURNS text AS $function$
DECLARE _result jsonb;
BEGIN
    SELECT json_build_object(
        'items', COALESCE(json_agg(row_to_json(t)), '[]'::json),
        'totalCompanies', (SELECT count(DISTINCT companyname) FROM studentplacements WHERE companyname IS NOT NULL),
        'totalStudents', (SELECT count(DISTINCT studentname) FROM studentplacements WHERE studentname IS NOT NULL),
        'totalPlacements', (SELECT count(*) FROM studentplacements)
    ) INTO _result
    FROM (
        SELECT 
            sp.companyname,
            count(DISTINCT sp.studentname) as student_count,
            count(*) as total_records,
            sp.jobprofile,
            sp.package,
            sp.sourcegroup
        FROM studentplacements sp
        WHERE sp.companyname IS NOT NULL AND sp.companyname != ''
        GROUP BY sp.companyname, sp.jobprofile, sp.package, sp.sourcegroup
        ORDER BY student_count DESC
    ) t;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;

-- 6. fn_api_select_placementstats_v001: Overall stats
CREATE OR REPLACE FUNCTION fn_api_select_placementstats_v001() RETURNS text AS $function$
DECLARE _result jsonb;
BEGIN
    SELECT json_build_object(
        'totalMessages', (SELECT count(*) FROM gmailmessages),
        'processedMessages', (SELECT count(*) FROM gmailmessages WHERE processingstatus = 'PROCESSED'),
        'totalPlacements', (SELECT count(*) FROM studentplacements),
        'uniqueStudents', (SELECT count(DISTINCT LOWER(TRIM(studentname))) FROM studentplacements WHERE studentname IS NOT NULL AND studentname != ''),
        'uniqueCompanies', (SELECT count(DISTINCT companyname) FROM studentplacements WHERE companyname IS NOT NULL AND companyname != ''),
        'bySourceGroup', (SELECT COALESCE(json_agg(row_to_json(gs)), '[]'::json) FROM (
            SELECT sourcegroup, count(*) as count FROM studentplacements GROUP BY sourcegroup
        ) gs),
        'byStatus', (SELECT COALESCE(json_agg(row_to_json(ss)), '[]'::json) FROM (
            SELECT status, count(*) as count FROM studentplacements GROUP BY status
        ) ss),
        'topCompanies', (SELECT COALESCE(json_agg(row_to_json(tc)), '[]'::json) FROM (
            SELECT companyname, count(DISTINCT studentname) as students 
            FROM studentplacements 
            WHERE companyname IS NOT NULL AND companyname != ''
            GROUP BY companyname ORDER BY students DESC LIMIT 10
        ) tc)
    ) INTO _result;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;

-- 7. fn_api_update_studentplacement_status_v001
CREATE OR REPLACE FUNCTION fn_api_update_studentplacement_status_v001(
    _placementid text, _status text
) RETURNS text AS $function$
BEGIN
    UPDATE studentplacements SET status = _status, updatedat = NOW() WHERE id = _placementid;
    IF FOUND THEN
        RETURN json_build_object('status','SUCCESS','message','Placement status updated');
    ELSE
        RETURN json_build_object('status','ERROR','message','Placement not found');
    END IF;
END;
$function$ LANGUAGE plpgsql;
