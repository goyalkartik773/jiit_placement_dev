-- Migration: Update jobdocuments table for local file storage
-- Adds documentpath, contenttype, filesize columns
-- Drops documenturl (temporary signed URLs should not be stored permanently)

-- 1. Add new columns
ALTER TABLE jobdocuments ADD COLUMN IF NOT EXISTS documentpath text NOT NULL DEFAULT '';
ALTER TABLE jobdocuments ADD COLUMN IF NOT EXISTS contenttype text NOT NULL DEFAULT 'application/octet-stream';
ALTER TABLE jobdocuments ADD COLUMN IF NOT EXISTS filesize bigint NOT NULL DEFAULT 0;

-- 2. Update existing rows: copy documenturl to documentpath where documentpath is empty
UPDATE jobdocuments SET documentpath = documenturl WHERE documentpath = '' AND documenturl != '';

-- 3. Drop the old documenturl column
ALTER TABLE jobdocuments DROP COLUMN IF EXISTS documenturl;

-- 4. Drop and recreate the function with new parameters
DROP FUNCTION IF EXISTS fn_api_post_jobdocument_v001;

CREATE OR REPLACE FUNCTION fn_api_post_jobdocument_v001(
    _sysjobuuid text,
    _documentidentifier text,
    _documentname text,
    _documentpath text,
    _contenttype text,
    _filesize bigint
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _newid text;
BEGIN
    IF _sysjobuuid IS NULL OR TRIM(_sysjobuuid) = '' THEN
        RETURN json_build_object('status','ERROR','message','Job UUID is required');
    END IF;

    -- UPSERT: update if exists, insert if new
    INSERT INTO jobdocuments (id, sysjobuuid, documentidentifier, documentname, documentpath, contenttype, filesize, status, posteddatetime)
    VALUES (gen_random_uuid()::text, _sysjobuuid, COALESCE(_documentidentifier,''), COALESCE(_documentname,''), COALESCE(_documentpath,''), COALESCE(_contenttype,'application/octet-stream'), COALESCE(_filesize, 0), 'Active', NOW())
    ON CONFLICT (documentidentifier)
    DO UPDATE SET
        documentname = EXCLUDED.documentname,
        documentpath = EXCLUDED.documentpath,
        contenttype = EXCLUDED.contenttype,
        filesize = EXCLUDED.filesize,
        updateddatetime = NOW()
    RETURNING id INTO _newid;

    IF _newid IS NULL THEN
        SELECT id INTO _newid FROM jobdocuments WHERE documentidentifier = _documentidentifier;
    END IF;

    RETURN json_build_object('status','SUCCESS','message','Document saved','id', _newid);
END;
$function$;

-- 5. Add a check constraint to ensure documentpath is never an absolute path (optional safety)
-- ALTER TABLE jobdocuments ADD CONSTRAINT chk_documentpath_relative CHECK (documentpath NOT LIKE 'D:\%' AND documentpath NOT LIKE '/%');
