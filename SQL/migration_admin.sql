-- ================================================================
-- Admin workflow: single source of truth for the job count.
-- Used by GET /api/admin/jobs/count and by the sync coordinator
-- to capture the before/after totals of every synchronization.
-- ================================================================

CREATE OR REPLACE FUNCTION fn_api_count_jobs_v001() RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _total integer;
BEGIN
    SELECT COUNT(*) INTO _total FROM jobs;
    RETURN json_build_object('totalJobs', _total);
END;
$function$;
