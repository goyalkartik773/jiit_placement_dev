-- ================================================================
-- Gmail Integration Tables and Functions
-- ================================================================

-- 1. Gmail Messages Table
CREATE TABLE IF NOT EXISTS gmailmessages (
    id text NOT NULL,
    gmailmessageid text NOT NULL,
    gmailthreadid text NOT NULL DEFAULT '',
    sourcegroup text,
    sourcegroupemail text,
    sender text,
    recipient text,
    cc text,
    bcc text,
    replyto text,
    subject text,
    receivedat text,
    bodytext text,
    bodyhtml text,
    snippet text,
    hasattachments boolean NOT NULL DEFAULT false,
    labelids text,
    rawpayload text,
    processingstatus text NOT NULL DEFAULT 'RECEIVED',
    createdat timestamp with time zone NOT NULL DEFAULT NOW(),
    updatedat timestamp with time zone,
    CONSTRAINT PK_GmailMessages PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS IX_GmailMessages_GmailMessageId ON gmailmessages (gmailmessageid);
CREATE INDEX IF NOT EXISTS IX_GmailMessages_SourceGroup ON gmailmessages (sourcegroup);
CREATE INDEX IF NOT EXISTS IX_GmailMessages_ProcessingStatus ON gmailmessages (processingstatus);

-- 2. Gmail Attachments Table
CREATE TABLE IF NOT EXISTS gmailattachments (
    id text NOT NULL,
    sysgmailmessageuuid text NOT NULL,
    gmailattachmentid text NOT NULL,
    filename text NOT NULL,
    mimetype text NOT NULL DEFAULT 'application/octet-stream',
    filesize bigint NOT NULL DEFAULT 0,
    filepath text,
    extractedtext text,
    status text NOT NULL DEFAULT 'Active',
    createdat timestamp with time zone NOT NULL DEFAULT NOW(),
    updatedat timestamp with time zone,
    CONSTRAINT PK_GmailAttachments PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS IX_GmailAttachments_SysGmailMessageUuid ON gmailattachments (sysgmailmessageuuid);
CREATE UNIQUE INDEX IF NOT EXISTS IX_GmailAttachments_GmailAttachmentId ON gmailattachments (gmailattachmentid);

-- 3. Email Extractions Table
CREATE TABLE IF NOT EXISTS emailextractions (
    id text NOT NULL,
    sysgmailmessageuuid text NOT NULL,
    category text NOT NULL DEFAULT 'irrelevant',
    isrelevant boolean NOT NULL DEFAULT false,
    rejectionreason text,
    title text,
    content text,
    source text,
    company text,
    role text,
    packagelpa numeric,
    packagedetails text,
    jobtype text,
    location text,
    joiningdate text,
    deadline text,
    interviewdate text,
    round text,
    venue text,
    eventname text,
    topic text,
    speaker text,
    startdate text,
    enddate text,
    registrationdeadline text,
    registrationlink text,
    prizepool text,
    teamsize text,
    organizer text,
    eligibilitycriteria text,
    hiringflow text,
    students text,
    totalstudents integer NOT NULL DEFAULT 0,
    links text,
    additionalinfo text,
    processingstatus text NOT NULL DEFAULT 'RECEIVED',
    validationmessage text,
    createdat timestamp with time zone NOT NULL DEFAULT NOW(),
    updatedat timestamp with time zone,
    CONSTRAINT PK_EmailExtractions PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS IX_EmailExtractions_SysGmailMessageUuid ON emailextractions (sysgmailmessageuuid);
CREATE INDEX IF NOT EXISTS IX_EmailExtractions_Category ON emailextractions (category);
CREATE INDEX IF NOT EXISTS IX_EmailExtractions_ProcessingStatus ON emailextractions (processingstatus);

-- ================================================================
-- PostgreSQL Functions
-- ================================================================

-- fn_api_insert_gmailmessage_v001
CREATE OR REPLACE FUNCTION fn_api_insert_gmailmessage_v001(
    _gmailmessageid text,
    _gmailthreadid text,
    _sourcegroup text,
    _sourcegroupemail text,
    _sender text,
    _recipient text,
    _cc text,
    _bcc text,
    _replyto text,
    _subject text,
    _receivedat text,
    _bodytext text,
    _bodyhtml text,
    _snippet text,
    _hasattachments boolean,
    _labelids text,
    _rawpayload text
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _newid text;
DECLARE _existingid text;
BEGIN
    IF _gmailmessageid IS NULL OR TRIM(_gmailmessageid) = '' THEN
        RETURN json_build_object('status','ERROR','message','Gmail message ID is required');
    END IF;

    -- Check if already exists
    SELECT id INTO _existingid FROM gmailmessages WHERE gmailmessageid = _gmailmessageid;

    IF _existingid IS NOT NULL THEN
        -- Update existing
        UPDATE gmailmessages SET
            gmailthreadid = COALESCE(NULLIF(_gmailthreadid,''), gmailthreadid),
            sourcegroup = COALESCE(NULLIF(_sourcegroup,''), sourcegroup),
            sourcegroupemail = COALESCE(NULLIF(_sourcegroupemail,''), sourcegroupemail),
            sender = COALESCE(NULLIF(_sender,''), sender),
            recipient = COALESCE(NULLIF(_recipient,''), recipient),
            cc = COALESCE(NULLIF(_cc,''), cc),
            bcc = COALESCE(NULLIF(_bcc,''), bcc),
            replyto = COALESCE(NULLIF(_replyto,''), replyto),
            subject = COALESCE(NULLIF(_subject,''), subject),
            receivedat = COALESCE(NULLIF(_receivedat,''), receivedat),
            bodytext = COALESCE(NULLIF(_bodytext,''), bodytext),
            bodyhtml = COALESCE(NULLIF(_bodyhtml,''), bodyhtml),
            snippet = COALESCE(NULLIF(_snippet,''), snippet),
            hasattachments = COALESCE(_hasattachments, hasattachments),
            labelids = COALESCE(NULLIF(_labelids,''), labelids),
            rawpayload = COALESCE(NULLIF(_rawpayload,''), rawpayload),
            updatedat = NOW()
        WHERE gmailmessageid = _gmailmessageid
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Gmail message updated','id', _newid);
    ELSE
        -- Insert new
        INSERT INTO gmailmessages (id, gmailmessageid, gmailthreadid, sourcegroup, sourcegroupemail,
            sender, recipient, cc, bcc, replyto, subject, receivedat,
            bodytext, bodyhtml, snippet, hasattachments, labelids, rawpayload,
            processingstatus, createdat)
        VALUES (gen_random_uuid()::text, _gmailmessageid, COALESCE(NULLIF(_gmailthreadid,''), ''),
            NULLIF(_sourcegroup,''), NULLIF(_sourcegroupemail,''), NULLIF(_sender,''), NULLIF(_recipient,''),
            NULLIF(_cc,''), NULLIF(_bcc,''), NULLIF(_replyto,''), NULLIF(_subject,''), NULLIF(_receivedat,''),
            NULLIF(_bodytext,''), NULLIF(_bodyhtml,''), NULLIF(_snippet,''), COALESCE(_hasattachments, false),
            NULLIF(_labelids,''), NULLIF(_rawpayload,''), 'RECEIVED', NOW())
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Gmail message created','id', _newid);
    END IF;
END;
$function$;

-- fn_api_update_gmailmessage_status_v001
CREATE OR REPLACE FUNCTION fn_api_update_gmailmessage_status_v001(
    _messageuuid text,
    _status text
) RETURNS text
LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE gmailmessages
    SET processingstatus = _status,
        updatedat = NOW()
    WHERE id = _messageuuid;

    IF FOUND THEN
        RETURN json_build_object('status','SUCCESS','message','Status updated');
    ELSE
        RETURN json_build_object('status','ERROR','message','Message not found');
    END IF;
END;
$function$;

-- fn_api_select_gmailmessages_v1
CREATE OR REPLACE FUNCTION fn_api_select_gmailmessages_v1(
    _page integer DEFAULT 1,
    _pagesize integer DEFAULT 20,
    _sourcegroup text DEFAULT '',
    _processingstatus text DEFAULT '',
    _search text DEFAULT ''
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _total integer; _offset integer; _result json;
BEGIN
    _offset := (_page - 1) * _pagesize;
    SELECT COUNT(*) INTO _total FROM gmailmessages
    WHERE (_sourcegroup = '' OR sourcegroup ILIKE '%' || _sourcegroup || '%')
      AND (_processingstatus = '' OR processingstatus = _processingstatus)
      AND (_search = '' OR subject ILIKE '%' || _search || '%' OR sender ILIKE '%' || _search || '%');

    SELECT json_agg(row_to_json(m)) INTO _result FROM (
        SELECT id, gmailmessageid, gmailthreadid, sourcegroup, sourcegroupemail,
            sender, subject, receivedat, snippet, hasattachments, processingstatus,
            createdat, updatedat
        FROM gmailmessages
        WHERE (_sourcegroup = '' OR sourcegroup ILIKE '%' || _sourcegroup || '%')
          AND (_processingstatus = '' OR processingstatus = _processingstatus)
          AND (_search = '' OR subject ILIKE '%' || _search || '%' OR sender ILIKE '%' || _search || '%')
        ORDER BY createdat DESC NULLS LAST
        LIMIT _pagesize OFFSET _offset
    ) m;

    RETURN json_build_object('Items', COALESCE(_result, '[]'::json),
        'TotalCount', _total, 'Page', _page, 'PageSize', _pagesize);
END;
$function$;

-- fn_api_select_gmailmessage_v1
CREATE OR REPLACE FUNCTION fn_api_select_gmailmessage_v1(_messageid text) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _msg json; _attachments json; _extraction json; _uuid text;
BEGIN
    SELECT row_to_json(m), m.id INTO _msg, _uuid FROM (
        SELECT * FROM gmailmessages WHERE id = _messageid OR gmailmessageid = _messageid LIMIT 1
    ) m;

    IF _msg IS NULL THEN
        RETURN json_build_object('status','ERROR','message','Gmail message not found');
    END IF;

    SELECT json_agg(row_to_json(a)) INTO _attachments FROM (
        SELECT * FROM gmailattachments WHERE sysgmailmessageuuid = _uuid
    ) a;

    SELECT row_to_json(e) INTO _extraction FROM (
        SELECT * FROM emailextractions WHERE sysgmailmessageuuid = _uuid
        ORDER BY createdat DESC LIMIT 1
    ) e;

    RETURN json_build_object(
        'status', 'SUCCESS',
        'data', _msg,
        'attachments', COALESCE(_attachments, '[]'::json),
        'extraction', _extraction
    );
END;
$function$;

-- fn_api_insert_gmailattachment_v001
CREATE OR REPLACE FUNCTION fn_api_insert_gmailattachment_v001(
    _sysgmailmessageuuid text,
    _gmailattachmentid text,
    _filename text,
    _mimetype text,
    _filesize bigint,
    _filepath text,
    _extractedtext text
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _newid text;
BEGIN
    IF _sysgmailmessageuuid IS NULL OR TRIM(_sysgmailmessageuuid) = '' THEN
        RETURN json_build_object('status','ERROR','message','Gmail message UUID is required');
    END IF;

    INSERT INTO gmailattachments (id, sysgmailmessageuuid, gmailattachmentid, filename, mimetype, filesize, filepath, extractedtext, status, createdat)
    VALUES (gen_random_uuid()::text, _sysgmailmessageuuid, COALESCE(_gmailattachmentid,''), COALESCE(_filename,''), COALESCE(_mimetype,'application/octet-stream'), COALESCE(_filesize, 0), _filepath, _extractedtext, 'Active', NOW())
    ON CONFLICT (gmailattachmentid)
    DO UPDATE SET
        filename = EXCLUDED.filename,
        mimetype = EXCLUDED.mimetype,
        filesize = EXCLUDED.filesize,
        filepath = EXCLUDED.filepath,
        extractedtext = CASE WHEN EXCLUDED.extractedtext IS NOT NULL AND EXCLUDED.extractedtext != ''
            THEN EXCLUDED.extractedtext ELSE gmailattachments.extractedtext END,
        updatedat = NOW()
    RETURNING id INTO _newid;

    IF _newid IS NULL THEN
        SELECT id INTO _newid FROM gmailattachments WHERE gmailattachmentid = _gmailattachmentid;
    END IF;

    RETURN json_build_object('status','SUCCESS','message','Attachment saved','id', _newid);
END;
$function$;

-- fn_api_save_emailextraction_v001
CREATE OR REPLACE FUNCTION fn_api_save_emailextraction_v001(
    _sysgmailmessageuuid text,
    _category text,
    _isrelevant boolean,
    _rejectionreason text,
    _title text,
    _content text,
    _source text,
    _company text,
    _role text,
    _packagelpa numeric,
    _packagedetails text,
    _jobtype text,
    _location text,
    _joiningdate text,
    _deadline text,
    _interviewdate text,
    _round text,
    _venue text,
    _eventname text,
    _topic text,
    _speaker text,
    _startdate text,
    _enddate text,
    _registrationdeadline text,
    _registrationlink text,
    _prizepool text,
    _teamsize text,
    _organizer text,
    _eligibilitycriteria text,
    _hiringflow text,
    _students text,
    _totalstudents integer,
    _links text,
    _additionalinfo text,
    _processingstatus text,
    _validationmessage text
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _newid text; _existingid text;
BEGIN
    IF _sysgmailmessageuuid IS NULL OR TRIM(_sysgmailmessageuuid) = '' THEN
        RETURN json_build_object('status','ERROR','message','Gmail message UUID is required');
    END IF;

    -- Check if extraction exists
    SELECT id INTO _existingid FROM emailextractions WHERE sysgmailmessageuuid = _sysgmailmessageuuid;

    IF _existingid IS NOT NULL THEN
        UPDATE emailextractions SET
            category = COALESCE(_category, category),
            isrelevant = COALESCE(_isrelevant, isrelevant),
            rejectionreason = _rejectionreason,
            title = _title,
            content = _content,
            source = _source,
            company = _company,
            role = _role,
            packagelpa = _packagelpa,
            packagedetails = _packagedetails,
            jobtype = _jobtype,
            location = _location,
            joiningdate = _joiningdate,
            deadline = _deadline,
            interviewdate = _interviewdate,
            round = _round,
            venue = _venue,
            eventname = _eventname,
            topic = _topic,
            speaker = _speaker,
            startdate = _startdate,
            enddate = _enddate,
            registrationdeadline = _registrationdeadline,
            registrationlink = _registrationlink,
            prizepool = _prizepool,
            teamsize = _teamsize,
            organizer = _organizer,
            eligibilitycriteria = _eligibilitycriteria,
            hiringflow = _hiringflow,
            students = _students,
            totalstudents = COALESCE(_totalstudents, 0),
            links = _links,
            additionalinfo = _additionalinfo,
            processingstatus = COALESCE(_processingstatus, processingstatus),
            validationmessage = _validationmessage,
            updatedat = NOW()
        WHERE id = _existingid
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Extraction updated','id', _newid);
    ELSE
        INSERT INTO emailextractions (id, sysgmailmessageuuid, category, isrelevant, rejectionreason,
            title, content, source, company, role, packagelpa, packagedetails, jobtype, location,
            joiningdate, deadline, interviewdate, round, venue, eventname, topic, speaker,
            startdate, enddate, registrationdeadline, registrationlink, prizepool, teamsize,
            organizer, eligibilitycriteria, hiringflow, students, totalstudents, links,
            additionalinfo, processingstatus, validationmessage, createdat)
        VALUES (gen_random_uuid()::text, _sysgmailmessageuuid, COALESCE(_category,'irrelevant'),
            COALESCE(_isrelevant, false), _rejectionreason, _title, _content, _source, _company, _role,
            _packagelpa, _packagedetails, _jobtype, _location, _joiningdate, _deadline, _interviewdate,
            _round, _venue, _eventname, _topic, _speaker, _startdate, _enddate, _registrationdeadline,
            _registrationlink, _prizepool, _teamsize, _organizer, _eligibilitycriteria, _hiringflow,
            _students, COALESCE(_totalstudents, 0), _links, _additionalinfo,
            COALESCE(_processingstatus,'RECEIVED'), _validationmessage, NOW())
        RETURNING id INTO _newid;

        RETURN json_build_object('status','SUCCESS','message','Extraction saved','id', _newid);
    END IF;
END;
$function$;

-- fn_api_select_emailextraction_v1
CREATE OR REPLACE FUNCTION fn_api_select_emailextraction_v1(_messageid text) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _extraction json;
BEGIN
    SELECT row_to_json(e) INTO _extraction FROM (
        SELECT e2.* FROM emailextractions e2
        WHERE e2.sysgmailmessageuuid = _messageid
        ORDER BY e2.createdat DESC LIMIT 1
    ) e;

    IF _extraction IS NULL THEN
        RETURN json_build_object('status','ERROR','message','Extraction not found');
    END IF;

    RETURN json_build_object('status','SUCCESS','data', _extraction);
END;
$function$;

-- fn_api_select_reviewqueue_v1
CREATE OR REPLACE FUNCTION fn_api_select_reviewqueue_v1(
    _page integer DEFAULT 1,
    _pagesize integer DEFAULT 20
) RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _total integer; _offset integer; _result json;
BEGIN
    _offset := (_page - 1) * _pagesize;
    SELECT COUNT(*) INTO _total FROM emailextractions WHERE processingstatus = 'REVIEW_REQUIRED';

    SELECT json_agg(row_to_json(r)) INTO _result FROM (
        SELECT e.id, e.sysgmailmessageuuid, e.category, e.title, e.company, e.role,
            e.packagelpa, e.processingstatus, e.validationmessage, e.createdat,
            m.sender, m.subject, m.receivedat, m.sourcegroup
        FROM emailextractions e
        INNER JOIN gmailmessages m ON m.id = e.sysgmailmessageuuid
        WHERE e.processingstatus = 'REVIEW_REQUIRED'
        ORDER BY e.createdat DESC NULLS LAST
        LIMIT _pagesize OFFSET _offset
    ) r;

    RETURN json_build_object('Items', COALESCE(_result, '[]'::json),
        'TotalCount', _total, 'Page', _page, 'PageSize', _pagesize);
END;
$function$;

-- fn_api_select_dashboard_v1 (update to include gmail stats)
CREATE OR REPLACE FUNCTION fn_api_select_dashboard_v1() RETURNS text
LANGUAGE plpgsql
AS $function$
DECLARE _result json;
BEGIN
    SELECT json_build_object(
        'totalJobs', (SELECT COUNT(*) FROM jobs WHERE status = 'Active'),
        'totalNotices', (SELECT COUNT(*) FROM notices WHERE status = 'Active'),
        'totalGmailMessages', (SELECT COUNT(*) FROM gmailmessages),
        'gmailProcessed', (SELECT COUNT(*) FROM gmailmessages WHERE processingstatus = 'PROCESSED'),
        'gmailReviewRequired', (SELECT COUNT(*) FROM emailextractions WHERE processingstatus = 'REVIEW_REQUIRED'),
        'totalExtractions', (SELECT COUNT(*) FROM emailextractions),
        'placementOffers', (SELECT COUNT(*) FROM emailextractions WHERE category = 'placement_offer' AND isrelevant = true),
        'jobPostings', (SELECT COUNT(*) FROM emailextractions WHERE category = 'job_posting' AND isrelevant = true)
    ) INTO _result;

    RETURN _result;
END;
$function$;
