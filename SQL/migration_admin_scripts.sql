-- ================================================================
-- Migration: admin script runs (console-script history + accuracy)
--
-- Gives the admin console a real, API-driven backbone:
--   * admin_script_runs       : one row per admin operation (login, logout,
--                               job sync, gmail sync, offer sync, deletes).
--                               Stores the real counters (jsonb) AND the
--                               console output the run produced (jsonb) so any
--                               past run can be replayed in the script console.
--   * fn_api_script_run_begin_v1 / _finish_v1 : write the row
--   * fn_api_select_script_runs_v1            : history / timeline feed
--   * fn_api_admin_overview_v1                : live counts + accuracy + last login
--   * fn_api_offer_sync_changes_v1            : delta of a run ("what changed")
--   * fn_api_delete_all_gmail_v001            : wipe the synced mailbox
--   * fn_api_delete_all_placed_students_v001  : wipe the job<->student mapping
--
-- Nothing here is estimated: every number is counted from a table.
-- ================================================================

-- 1. One row per admin operation -------------------------------------
CREATE TABLE IF NOT EXISTS admin_script_runs (
    id text NOT NULL DEFAULT (gen_random_uuid()::text),
    script text NOT NULL,
    status text NOT NULL,
    username text,
    message text,
    counters jsonb,
    output jsonb,
    error text,
    durationms integer,
    startedat timestamp with time zone NOT NULL DEFAULT NOW(),
    finishedat timestamp with time zone,
    CONSTRAINT PK_admin_script_runs PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS IX_admin_script_runs_startedat ON admin_script_runs (startedat DESC);
CREATE INDEX IF NOT EXISTS IX_admin_script_runs_script ON admin_script_runs (script, startedat DESC);

-- 2. Open a run (called before the work starts) ----------------------
CREATE OR REPLACE FUNCTION fn_api_script_run_begin_v1(
    _script text, _username text, _message text) RETURNS text AS $function$
DECLARE _newid text;
BEGIN
    INSERT INTO admin_script_runs (id, script, status, username, message, startedat)
    VALUES (gen_random_uuid()::text, _script, 'running',
            NULLIF(TRIM(COALESCE(_username, '')), ''), _message, NOW())
    RETURNING id INTO _newid;

    RETURN json_build_object('status', 'SUCCESS', 'id', _newid)::text;
END;
$function$ LANGUAGE plpgsql;

-- 2b. Log a one-shot action in one call (login / logout / rejected start) --
--     _counters / _output arrive as text and are cast here, so callers never
--     depend on PostgreSQL's text -> json coercion rules.
CREATE OR REPLACE FUNCTION fn_api_script_run_log_v1(
    _script text, _status text, _username text, _message text,
    _counters text, _output text, _durationms integer) RETURNS text AS $function$
DECLARE _newid text;
BEGIN
    INSERT INTO admin_script_runs
        (id, script, status, username, message, counters, output, durationms, startedat, finishedat)
    VALUES (gen_random_uuid()::text, _script, COALESCE(NULLIF(_status, ''), 'completed'),
            NULLIF(TRIM(COALESCE(_username, '')), ''), _message,
            NULLIF(COALESCE(_counters, ''), '')::jsonb,
            NULLIF(COALESCE(_output, ''), '')::jsonb,
            _durationms, NOW(), NOW())
    RETURNING id INTO _newid;

    RETURN json_build_object('status', 'SUCCESS', 'id', _newid)::text;
END;
$function$ LANGUAGE plpgsql;

-- 3. Close a run with its real counters + console output -------------
CREATE OR REPLACE FUNCTION fn_api_script_run_finish_v1(
    _id text, _status text, _message text,
    _counters text, _output text, _error text, _durationms integer) RETURNS text AS $function$
DECLARE _updated integer;
BEGIN
    UPDATE admin_script_runs
    SET status = _status,
        message = _message,
        counters = NULLIF(COALESCE(_counters, ''), '')::jsonb,
        output = NULLIF(COALESCE(_output, ''), '')::jsonb,
        error = NULLIF(TRIM(COALESCE(_error, '')), ''),
        durationms = _durationms,
        finishedat = NOW()
    WHERE id = _id AND status = 'running';

    GET DIAGNOSTICS _updated = ROW_COUNT;

    RETURN json_build_object(
        'status', CASE WHEN _updated = 1 THEN 'SUCCESS' ELSE 'ERROR' END,
        'message', CASE WHEN _updated = 1 THEN 'Run recorded'
                        ELSE 'Run not found or already finished' END)::text;
END;
$function$ LANGUAGE plpgsql;

-- 4. History feed (newest first) -------------------------------------
--    _script = '' returns every action (the timeline), otherwise one script.
CREATE OR REPLACE FUNCTION fn_api_select_script_runs_v1(
    _page integer, _pagesize integer, _script text) RETURNS text AS $function$
DECLARE _total integer; _offset integer; _result json;
BEGIN
    _offset := (_page - 1) * _pagesize;

    SELECT COUNT(*) INTO _total
    FROM admin_script_runs
    WHERE _script = '' OR script = _script;

    SELECT json_agg(row_to_json(r)) INTO _result
    FROM (
        SELECT id, script, status, username, message, counters, output, error,
               durationms, startedat, finishedat
        FROM admin_script_runs
        WHERE _script = '' OR script = _script
        ORDER BY startedat DESC, id DESC
        LIMIT _pagesize OFFSET _offset
    ) r;

    RETURN json_build_object(
        'Items', COALESCE(_result, '[]'::json),
        'TotalCount', _total,
        'Page', _page,
        'PageSize', _pagesize,
        'TotalPages', CEIL(_total::numeric / _pagesize))::text;
END;
$function$ LANGUAGE plpgsql;

-- 5. What changed in a run: mappings inserted since a timestamp -------
CREATE OR REPLACE FUNCTION fn_api_offer_sync_changes_v1(
    _since timestamp with time zone) RETURNS text AS $function$
BEGIN
    RETURN (
        WITH new_rows AS (
            SELECT company_name, student_roll_no
            FROM job_placed_students
            WHERE placed_at >= _since
        )
        SELECT json_build_object(
            'mappingsInserted', (SELECT COUNT(*) FROM new_rows),
            'studentsAdded', (SELECT COUNT(DISTINCT student_roll_no) FROM new_rows),
            'companiesTouched', (SELECT COUNT(DISTINCT company_name) FROM new_rows),
            'changes', COALESCE((
                SELECT json_agg(x ORDER BY x.students DESC, x.company)
                FROM (SELECT company_name AS company, COUNT(*) AS students
                      FROM new_rows GROUP BY company_name) x), '[]'::json)
        )
    )::text;
END;
$function$ LANGUAGE plpgsql;

-- 6. Delete the synced mailbox ---------------------------------------
--    gmailmessages / gmailattachments / emailextractions carry no FKs, so
--    children go first inside one transaction. The parsed email corpus
--    (emails, offers, ...) and job_placed_students are NOT touched here.
CREATE OR REPLACE FUNCTION fn_api_delete_all_gmail_v001() RETURNS text AS $function$
DECLARE
    _started timestamp with time zone := clock_timestamp();
    _attachments integer; _extractions integer; _messages integer;
    _attachments_before integer; _messages_before integer; _extractions_before integer;
BEGIN
    SELECT COUNT(*) INTO _attachments_before FROM gmailattachments;
    SELECT COUNT(*) INTO _extractions_before FROM emailextractions;
    SELECT COUNT(*) INTO _messages_before FROM gmailmessages;

    DELETE FROM gmailattachments;
    GET DIAGNOSTICS _attachments = ROW_COUNT;

    DELETE FROM emailextractions;
    GET DIAGNOSTICS _extractions = ROW_COUNT;

    DELETE FROM gmailmessages;
    GET DIAGNOSTICS _messages = ROW_COUNT;

    RETURN json_build_object(
        'status', 'SUCCESS',
        'message', 'Synced mailbox deleted',
        'messagesBefore', _messages_before,
        'attachmentsBefore', _attachments_before,
        'extractionsBefore', _extractions_before,
        'messagesDeleted', _messages,
        'attachmentsDeleted', _attachments,
        'extractionsDeleted', _extractions,
        'durationMs', EXTRACT(EPOCH FROM (clock_timestamp() - _started)) * 1000)::text;
END;
$function$ LANGUAGE plpgsql;

-- 7. Delete every job <-> student mapping ----------------------------
CREATE OR REPLACE FUNCTION fn_api_delete_all_placed_students_v001() RETURNS text AS $function$
DECLARE
    _started timestamp with time zone := clock_timestamp();
    _rows integer;
    _students integer;
    _companies integer;
    _before integer;
BEGIN
    SELECT COUNT(*),
           COUNT(DISTINCT student_roll_no),
           COUNT(DISTINCT company_name)
    INTO _before, _students, _companies
    FROM job_placed_students;

    DELETE FROM job_placed_students;
    GET DIAGNOSTICS _rows = ROW_COUNT;

    RETURN json_build_object(
        'status', 'SUCCESS',
        'message', 'Job to student mappings deleted',
        'mappingsBefore', _before,
        'mappingsDeleted', _rows,
        'studentsCleared', _students,
        'companiesCleared', _companies,
        'durationMs', EXTRACT(EPOCH FROM (clock_timestamp() - _started)) * 1000)::text;
END;
$function$ LANGUAGE plpgsql;

-- 8. Admin overview: live counts, accuracy ratios, session, last runs --
CREATE OR REPLACE FUNCTION fn_api_admin_overview_v1() RETURNS text AS $function$
DECLARE
    _mailbox_total integer;
    _result json;
BEGIN
    SELECT COUNT(*) INTO _mailbox_total FROM gmailmessages;

    SELECT json_build_object(
        'counts', (
            SELECT json_build_object(
                'jobs', (SELECT COUNT(*) FROM jobs),
                'jobsActive', (SELECT COUNT(*) FROM jobs WHERE status = 'Active'),
                'notices', (SELECT COUNT(*) FROM notices),
                'gmailMessages', (SELECT COUNT(*) FROM gmailmessages),
                'gmailAttachments', (SELECT COUNT(*) FROM gmailattachments),
                'emails', (SELECT COUNT(*) FROM emails),
                'emailsCanonical', (SELECT COUNT(*) FROM emails WHERE is_canonical = TRUE),
                'offers', (SELECT COUNT(*) FROM offers),
                'offerStudents', (SELECT COUNT(*) FROM offer_students),
                'mappings', (SELECT COUNT(*) FROM job_placed_students),
                'shortlistEvents', (SELECT COUNT(*) FROM shortlist_events),
                'shortlistStudents', (SELECT COUNT(*) FROM shortlist_students),
                'opportunities', (SELECT COUNT(*) FROM opportunities)
            )
        ),
        'mailbox', (
            SELECT json_build_object(
                'total', _mailbox_total,
                'processed', COUNT(*) FILTER (WHERE processingstatus = 'PROCESSED'),
                'reviewRequired', COUNT(*) FILTER (WHERE processingstatus = 'REVIEW_REQUIRED'),
                'irrelevant', COUNT(*) FILTER (WHERE processingstatus = 'IRRELEVANT'),
                'received', COUNT(*) FILTER (WHERE processingstatus = 'RECEIVED'),
                'failed', COUNT(*) FILTER (WHERE processingstatus NOT IN
                        ('PROCESSED', 'REVIEW_REQUIRED', 'IRRELEVANT', 'RECEIVED')),
                'finishedRate', CASE WHEN _mailbox_total = 0 THEN NULL ELSE
                    ROUND(100.0 * COUNT(*) FILTER (WHERE processingstatus IN ('PROCESSED', 'IRRELEVANT'))
                          / _mailbox_total, 1) END,
                'reviewRate', CASE WHEN _mailbox_total = 0 THEN NULL ELSE
                    ROUND(100.0 * COUNT(*) FILTER (WHERE processingstatus = 'REVIEW_REQUIRED')
                          / _mailbox_total, 1) END
            )
            FROM gmailmessages
        ),
        'classification', (
            SELECT json_build_object(
                'canonical', (SELECT COUNT(*) FROM emails WHERE is_canonical = TRUE),
                'classified', (SELECT COUNT(*) FROM emails
                               WHERE is_canonical = TRUE AND classification IS NOT NULL),
                'coverage', CASE
                    WHEN (SELECT COUNT(*) FROM emails WHERE is_canonical = TRUE) = 0 THEN NULL
                    ELSE ROUND(100.0 * (SELECT COUNT(*) FROM emails
                                        WHERE is_canonical = TRUE AND classification IS NOT NULL)
                               / (SELECT COUNT(*) FROM emails WHERE is_canonical = TRUE), 1) END,
                'shortlistedStudents', (SELECT COUNT(*) FROM shortlist_students)
            )
        ),
        'matching', (
            SELECT json_build_object(
                'studentsConsidered', (SELECT COUNT(DISTINCT TRIM(roll_no)) FROM offer_students
                                       WHERE roll_no IS NOT NULL AND TRIM(roll_no) <> ''),
                'studentsMapped', (SELECT COUNT(DISTINCT student_roll_no) FROM job_placed_students),
                'jobsMatched', (SELECT COUNT(DISTINCT job_id) FROM job_placed_students),
                'jobsWithoutPlacements', (SELECT GREATEST((SELECT COUNT(*) FROM jobs)
                                            - (SELECT COUNT(DISTINCT job_id) FROM job_placed_students), 0)),
                'companiesMatched', (SELECT COUNT(DISTINCT company_name) FROM job_placed_students),
                'companiesSkipped', (
                    SELECT COUNT(*) FROM (
                        SELECT DISTINCT fn_norm_company_v1(c.name) AS ckey
                        FROM offer_students os
                        JOIN offers o ON o.id = os.offer_id
                        JOIN companies c ON c.id = o.company_id
                        WHERE os.roll_no IS NOT NULL AND TRIM(os.roll_no) <> ''
                    ) oc
                    WHERE NOT EXISTS (SELECT 1 FROM jobs j WHERE fn_norm_company_v1(j.company) = oc.ckey)
                ),
                'lastRunAt', (SELECT MAX(startedat) FROM admin_script_runs WHERE script = 'offer_sync')
            )
        ),
        'integrity', (
            SELECT json_build_object(
                'orphanMappings', (SELECT COUNT(*) FROM job_placed_students jps
                                   WHERE NOT EXISTS (SELECT 1 FROM jobs j WHERE j.id = jps.job_id)),
                'orphanOffers', (SELECT COUNT(*) FROM job_placed_students jps
                                 WHERE NOT EXISTS (SELECT 1 FROM emails e WHERE e.id = jps.offer_email_id)),
                'duplicateMappings', (SELECT COUNT(*) FROM (
                    SELECT job_id, student_roll_no FROM job_placed_students
                    GROUP BY job_id, student_roll_no HAVING COUNT(*) > 1) d),
                'blankRolls', (SELECT COUNT(*) FROM job_placed_students
                               WHERE student_roll_no IS NULL OR TRIM(student_roll_no) = '')
            )
        ),
        'session', (
            SELECT json_build_object(
                'lastLogin', (SELECT startedat FROM admin_script_runs
                              WHERE script = 'login' AND status = 'completed'
                              ORDER BY startedat DESC LIMIT 1),
                'previousLogin', (SELECT startedat FROM (
                    SELECT startedat FROM admin_script_runs
                    WHERE script = 'login' AND status = 'completed'
                    ORDER BY startedat DESC OFFSET 1 LIMIT 1) p),
                'lastLogout', (SELECT startedat FROM admin_script_runs
                               WHERE script = 'logout'
                               ORDER BY startedat DESC LIMIT 1),
                'logins', (SELECT COUNT(*) FROM admin_script_runs
                           WHERE script = 'login' AND status = 'completed')
            )
        ),
        'lastRuns', (
            SELECT COALESCE(json_agg(row_to_json(l) ORDER BY l.startedat DESC), '[]'::json)
            FROM (
                SELECT DISTINCT ON (script) script, status, message, durationms, startedat, finishedat
                FROM admin_script_runs
                WHERE script <> 'login' AND script <> 'logout'
                ORDER BY script, startedat DESC
            ) l
        )
    ) INTO _result;

    RETURN _result::text;
END;
$function$ LANGUAGE plpgsql;
