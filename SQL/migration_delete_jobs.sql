-- ================================================================
-- Admin workflow: delete every job and the documents it owns.
-- Used by DELETE /api/admin/jobs. The function runs as a single
-- transaction: it first captures the document paths, then removes
-- every job row (children before parents) and returns the counts
-- plus the captured paths so the API can clean up the files on disk.
-- Notices and Gmail data are NOT touched.
-- ================================================================

CREATE OR REPLACE FUNCTION fn_api_delete_all_jobs_v001() RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE
    _jobs integer;
    _doc_rows integer;
    _paths jsonb;
BEGIN
    SELECT COALESCE(jsonb_agg(documentpath), '[]'::jsonb)
      INTO _paths
      FROM jobdocuments
     WHERE documentpath IS NOT NULL AND documentpath <> '';

    DELETE FROM jobdocuments;
    GET DIAGNOSTICS _doc_rows = ROW_COUNT;
    DELETE FROM jobeligibilities;
    DELETE FROM jobeligibilitycourses;
    DELETE FROM jobgenders;
    DELETE FROM jobhiringflows;
    DELETE FROM jobskills;
    DELETE FROM jobs;
    GET DIAGNOSTICS _jobs = ROW_COUNT;

    RETURN json_build_object(
        'jobsDeleted', _jobs,
        'documentRowsDeleted', _doc_rows,
        'documentPaths', _paths);
END;
$function$;
