-- ================================================================
-- Backend revamp: database cleanup (every statement dependency-audited)
--
-- DROPS — verified before execution:
--   fn_api_post_supersetaccount_v001(text,text,text,text,text)
--     No reference in any .cs file; the only pg_proc body mentioning
--     "supersetaccounts" is this function itself.
--   fn_api_update_studentplacement_status_v001(text,text)
--     Defined by SQL/migration_placements.sql but never called from
--     backend code (grep-verified); no other function references it.
--   TABLE supersetaccounts
--     0 rows, no views, no foreign keys, and no remaining function
--     references it once the function above is dropped.
--
-- TRUNCATE — fetched job-sync data only (schema, indexes and
--   constraints preserved; nothing here is configuration/admin data).
--   All rows regenerate through the admin "Sync New Jobs" workflow.
--   The database has NO foreign keys, so this order is safe without
--   CASCADE. NOT truncated: gmailmessages, gmailattachments,
--   emailextractions, studentplacements (different subsystem),
--   __EFMigrationsHistory (schema bookkeeping).
-- ================================================================

DROP FUNCTION IF EXISTS fn_api_post_supersetaccount_v001(text, text, text, text, text);
DROP FUNCTION IF EXISTS fn_api_update_studentplacement_status_v001(text, text);

DROP TABLE IF EXISTS supersetaccounts;

TRUNCATE TABLE
    jobs,
    jobdocuments,
    jobeligibilities,
    jobeligibilitycourses,
    jobgenders,
    jobhiringflows,
    jobskills,
    notices
RESTART IDENTITY;
