CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

START TRANSACTION;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobDocuments" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "DocumentIdentifier" text NOT NULL,
        "DocumentName" text NOT NULL,
        "DocumentUrl" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobDocuments" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobEligibilities" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "Level" text NOT NULL,
        "Criteria" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobEligibilities" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobEligibilityCourses" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "CourseName" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobEligibilityCourses" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobGenders" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "Gender" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobGenders" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobHiringFlows" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "Sequence" text NOT NULL,
        "StageName" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobHiringFlows" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "Jobs" (
        "Id" text NOT NULL,
        "SuperSetJobIdentifier" text NOT NULL,
        "Company" text NOT NULL,
        "JobProfile" text NOT NULL,
        "PlacementCategory" text NOT NULL,
        "PlacementCategoryCode" text NOT NULL,
        "Content" text NOT NULL,
        "CreatedAt" timestamp with time zone,
        "Deadline" timestamp with time zone,
        "Location" text NOT NULL,
        "Package" real NOT NULL,
        "PackageInfo" text NOT NULL,
        "JobDescription" text NOT NULL,
        "PlacementType" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_Jobs" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "JobSkills" (
        "Id" text NOT NULL,
        "SysJobUuid" text NOT NULL,
        "SkillName" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_JobSkills" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "Notices" (
        "Id" text NOT NULL,
        "SuperSetIdentifier" text NOT NULL,
        "Title" text NOT NULL,
        "Content" text NOT NULL,
        "Author" text NOT NULL,
        "CreatedAt" timestamp with time zone,
        "UpdatedAt" timestamp with time zone,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_Notices" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE TABLE "SupersetAccounts" (
        "Id" text NOT NULL,
        "Email" text NOT NULL,
        "Name" text NOT NULL,
        "Uuid" text NOT NULL,
        "CollegeCode" text NOT NULL,
        "Batch" text NOT NULL,
        "Status" text NOT NULL,
        posteddatetime timestamp with time zone NOT NULL,
        updateddatetime timestamp with time zone,
        CONSTRAINT "PK_SupersetAccounts" PRIMARY KEY ("Id")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE UNIQUE INDEX "IX_JobDocuments_DocumentIdentifier" ON "JobDocuments" ("DocumentIdentifier");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobDocuments_SysJobUuid" ON "JobDocuments" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobEligibilities_SysJobUuid" ON "JobEligibilities" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobEligibilityCourses_SysJobUuid" ON "JobEligibilityCourses" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobGenders_SysJobUuid" ON "JobGenders" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobHiringFlows_SysJobUuid" ON "JobHiringFlows" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE UNIQUE INDEX "IX_Jobs_SuperSetJobIdentifier" ON "Jobs" ("SuperSetJobIdentifier");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE INDEX "IX_JobSkills_SysJobUuid" ON "JobSkills" ("SysJobUuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE UNIQUE INDEX "IX_Notices_SuperSetIdentifier" ON "Notices" ("SuperSetIdentifier");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE UNIQUE INDEX "IX_SupersetAccounts_Email" ON "SupersetAccounts" ("Email");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    CREATE UNIQUE INDEX "IX_SupersetAccounts_Uuid" ON "SupersetAccounts" ("Uuid");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260920064916_InitialCreate') THEN
    INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
    VALUES ('20260920064916_InitialCreate', '9.0.20');
    END IF;
END $EF$;
COMMIT;

