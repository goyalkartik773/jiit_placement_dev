-- Rename columns to lowercase for ALL tables

-- Jobs table
ALTER TABLE jobs RENAME COLUMN "Id" TO id;
ALTER TABLE jobs RENAME COLUMN "SuperSetJobIdentifier" TO supersetjobidentifier;
ALTER TABLE jobs RENAME COLUMN "Company" TO company;
ALTER TABLE jobs RENAME COLUMN "JobProfile" TO jobprofile;
ALTER TABLE jobs RENAME COLUMN "PlacementCategory" TO placementcategory;
ALTER TABLE jobs RENAME COLUMN "PlacementCategoryCode" TO placementcategorycode;
ALTER TABLE jobs RENAME COLUMN "Content" TO content;
ALTER TABLE jobs RENAME COLUMN "CreatedAt" TO createdat;
ALTER TABLE jobs RENAME COLUMN "Deadline" TO deadline;
ALTER TABLE jobs RENAME COLUMN "Location" TO location;
ALTER TABLE jobs RENAME COLUMN "Package" TO package;
ALTER TABLE jobs RENAME COLUMN "PackageInfo" TO packageinfo;
ALTER TABLE jobs RENAME COLUMN "JobDescription" TO jobdescription;
ALTER TABLE jobs RENAME COLUMN "PlacementType" TO placementtype;
ALTER TABLE jobs RENAME COLUMN "Status" TO status;
ALTER TABLE jobs RENAME COLUMN "posteddatetime" TO posteddatetime;
ALTER TABLE jobs RENAME COLUMN "updateddatetime" TO updateddatetime;

-- Notices table
ALTER TABLE notices RENAME COLUMN "Id" TO id;
ALTER TABLE notices RENAME COLUMN "SuperSetIdentifier" TO supersetidentifier;
ALTER TABLE notices RENAME COLUMN "Title" TO title;
ALTER TABLE notices RENAME COLUMN "Content" TO content;
ALTER TABLE notices RENAME COLUMN "Author" TO author;
ALTER TABLE notices RENAME COLUMN "CreatedAt" TO createdat;
ALTER TABLE notices RENAME COLUMN "UpdatedAt" TO updatedat;
ALTER TABLE notices RENAME COLUMN "Status" TO status;
ALTER TABLE notices RENAME COLUMN "posteddatetime" TO posteddatetime;
ALTER TABLE notices RENAME COLUMN "updateddatetime" TO updateddatetime;

-- JobEligibilities table
ALTER TABLE jobeligibilities RENAME COLUMN "Id" TO id;
ALTER TABLE jobeligibilities RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobeligibilities RENAME COLUMN "Level" TO level;
ALTER TABLE jobeligibilities RENAME COLUMN "Criteria" TO criteria;
ALTER TABLE jobeligibilities RENAME COLUMN "Status" TO status;
ALTER TABLE jobeligibilities RENAME COLUMN "posteddatetime" TO posteddatetime;

-- JobEligibilityCourses table
ALTER TABLE jobeligibilitycourses RENAME COLUMN "Id" TO id;
ALTER TABLE jobeligibilitycourses RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobeligibilitycourses RENAME COLUMN "CourseName" TO coursename;
ALTER TABLE jobeligibilitycourses RENAME COLUMN "Status" TO status;
ALTER TABLE jobeligibilitycourses RENAME COLUMN "posteddatetime" TO posteddatetime;

-- JobGenders table
ALTER TABLE jobgenders RENAME COLUMN "Id" TO id;
ALTER TABLE jobgenders RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobgenders RENAME COLUMN "Gender" TO gender;
ALTER TABLE jobgenders RENAME COLUMN "Status" TO status;
ALTER TABLE jobgenders RENAME COLUMN "posteddatetime" TO posteddatetime;

-- JobHiringFlows table
ALTER TABLE jobhiringflows RENAME COLUMN "Id" TO id;
ALTER TABLE jobhiringflows RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobhiringflows RENAME COLUMN "Sequence" TO sequence;
ALTER TABLE jobhiringflows RENAME COLUMN "StageName" TO stagename;
ALTER TABLE jobhiringflows RENAME COLUMN "Status" TO status;
ALTER TABLE jobhiringflows RENAME COLUMN "posteddatetime" TO posteddatetime;

-- JobSkills table
ALTER TABLE jobskills RENAME COLUMN "Id" TO id;
ALTER TABLE jobskills RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobskills RENAME COLUMN "SkillName" TO skillname;
ALTER TABLE jobskills RENAME COLUMN "Status" TO status;
ALTER TABLE jobskills RENAME COLUMN "posteddatetime" TO posteddatetime;

-- JobDocuments table
ALTER TABLE jobdocuments RENAME COLUMN "Id" TO id;
ALTER TABLE jobdocuments RENAME COLUMN "SysJobUuid" TO sysjobuuid;
ALTER TABLE jobdocuments RENAME COLUMN "DocumentIdentifier" TO documentidentifier;
ALTER TABLE jobdocuments RENAME COLUMN "DocumentName" TO documentname;
ALTER TABLE jobdocuments RENAME COLUMN "DocumentUrl" TO documenturl;
ALTER TABLE jobdocuments RENAME COLUMN "Status" TO status;
ALTER TABLE jobdocuments RENAME COLUMN "posteddatetime" TO posteddatetime;

-- SupersetAccounts table
ALTER TABLE supersetaccounts RENAME COLUMN "Id" TO id;
ALTER TABLE supersetaccounts RENAME COLUMN "Email" TO email;
ALTER TABLE supersetaccounts RENAME COLUMN "Name" TO name;
ALTER TABLE supersetaccounts RENAME COLUMN "Uuid" TO uuid;
ALTER TABLE supersetaccounts RENAME COLUMN "CollegeCode" TO collegecode;
ALTER TABLE supersetaccounts RENAME COLUMN "Batch" TO batch;
ALTER TABLE supersetaccounts RENAME COLUMN "Status" TO status;
ALTER TABLE supersetaccounts RENAME COLUMN "posteddatetime" TO posteddatetime;
ALTER TABLE supersetaccounts RENAME COLUMN "updateddatetime" TO updateddatetime;
