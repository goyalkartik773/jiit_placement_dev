using System.Text.Json.Serialization;

namespace JIITPlacement.Models
{
    // ================================================================
    // File Storage Options (config from appsettings.json)
    // ================================================================
    public class FileStorageOptions
    {
        public const string SectionName = "FileStorage";
        public string RootPath { get; set; } = string.Empty;
    }

    // ================================================================
    // SuperSet Options (config from appsettings.json)
    // ================================================================
    public class SuperSetOptions
    {
        public const string SectionName = "SuperSet";
        public string BaseUrl { get; set; } = string.Empty;
        public string ApiBasePath { get; set; } = "/tnpsuite-core";
        public string Username { get; set; } = string.Empty;
        public string Password { get; set; } = string.Empty;
        public string TenantId { get; set; } = string.Empty;
        public string TenantType { get; set; } = "STUDENT";
        public string StudentUuid { get; set; } = string.Empty;
        public string ApiBaseUrl => $"{BaseUrl}{ApiBasePath}";
        public string RsaPublicKeyBase64 { get; set; } = string.Empty;
    }

    // ================================================================
    // Admin Sync Request
    // ================================================================
    public class SuperSetSyncRequest
    {
        /// <summary>
        /// Sync jobs from SuperSet. Set to true to fetch and upsert job listings.
        /// </summary>
        public bool SyncJobs { get; set; } = true;

        /// <summary>
        /// Sync notices from SuperSet. Set to true to fetch and upsert notices.
        /// </summary>
        public bool SyncNotices { get; set; } = true;
    }

    // ================================================================
    // SuperSet API Login DTOs
    // ================================================================
    public class SuperSetLoginRequest
    {
        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("password")]
        public string Password { get; set; } = string.Empty;
    }

    public class SuperSetLoginResponse
    {
        [JsonPropertyName("userId")]
        public long UserId { get; set; }

        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("emailHash")]
        public string EmailHash { get; set; } = string.Empty;

        [JsonPropertyName("sessionKey")]
        public string SessionKey { get; set; } = string.Empty;

        [JsonPropertyName("uuid")]
        public string Uuid { get; set; } = string.Empty;

        [JsonPropertyName("refreshToken")]
        public string RefreshToken { get; set; } = string.Empty;

        [JsonPropertyName("userProfilePhotoId")]
        public string UserProfilePhotoId { get; set; } = string.Empty;

        [JsonPropertyName("userModes")]
        public List<string> UserModes { get; set; } = new();

        [JsonPropertyName("permissions")]
        public List<string> Permissions { get; set; } = new();

        [JsonPropertyName("emailVerified")]
        public bool EmailVerified { get; set; }

        [JsonPropertyName("message")]
        public string? Message { get; set; }

        [JsonPropertyName("enableMfa")]
        public bool EnableMfa { get; set; }
    }

    // ================================================================
    // SuperSet Notice DTO
    // ================================================================
    public class SuperSetNoticeDto
    {
        [JsonPropertyName("identifier")]
        public string Identifier { get; set; } = string.Empty;

        [JsonPropertyName("title")]
        public string Title { get; set; } = string.Empty;

        [JsonPropertyName("content")]
        public string Content { get; set; } = string.Empty;

        [JsonPropertyName("lastModifiedByUserName")]
        public string LastModifiedByUserName { get; set; } = string.Empty;

        [JsonPropertyName("lastModifiedOn")]
        public long? LastModifiedOn { get; set; }

        [JsonPropertyName("publishedAt")]
        public long? PublishedAt { get; set; }
    }

    // ================================================================
    // SuperSet Job Basic DTO (list view)
    // ================================================================
    public class SuperSetJobBasicDto
    {
        [JsonPropertyName("jobProfileIdentifier")]
        public string JobProfileIdentifier { get; set; } = string.Empty;

        [JsonPropertyName("jobProfileTitle")]
        public string JobProfileTitle { get; set; } = string.Empty;

        [JsonPropertyName("companyName")]
        public string CompanyName { get; set; } = string.Empty;

        [JsonPropertyName("placementCategoryLevel")]
        public int PlacementCategoryLevel { get; set; }

        [JsonPropertyName("placementCategoryName")]
        public string? PlacementCategoryName { get; set; }

        [JsonPropertyName("content")]
        public string Content { get; set; } = string.Empty;

        [JsonPropertyName("createdAt")]
        public long? CreatedAt { get; set; }

        [JsonPropertyName("jobProfileApplicationDeadline")]
        public long? JobProfileApplicationDeadline { get; set; }
    }

    // ================================================================
    // SuperSet Job Detail DTO (full detail)
    // ================================================================
    public class SuperSetJobDetailDto
    {
        [JsonPropertyName("eligibilityCheckResult")]
        public EligibilityCheckResult? EligibilityCheckResult { get; set; }

        [JsonPropertyName("jobProfile")]
        public JobProfileDetails? JobProfile { get; set; }

        [JsonPropertyName("jobProfileLocation")]
        public string? JobProfileLocation { get; set; }

        [JsonPropertyName("positionType")]
        public string? PositionType { get; set; }
    }

    public class EligibilityCheckResult
    {
        [JsonPropertyName("academicResults")]
        public List<AcademicResult> AcademicResults { get; set; } = new();

        [JsonPropertyName("courseCheckResult")]
        public CourseCheckResult? CourseCheckResult { get; set; }
    }

    public class AcademicResult
    {
        [JsonPropertyName("level")]
        public string Level { get; set; } = string.Empty;

        [JsonPropertyName("required")]
        public float Required { get; set; }
    }

    public class CourseCheckResult
    {
        [JsonPropertyName("openedForCourses")]
        public List<OpenedCourse> OpenedForCourses { get; set; } = new();
    }

    public class OpenedCourse
    {
        [JsonPropertyName("program")]
        public CourseProgram? Program { get; set; }

        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;
    }

    public class CourseProgram
    {
        [JsonPropertyName("shortName")]
        public string ShortName { get; set; } = string.Empty;
    }

    public class JobProfileDetails
    {
        [JsonPropertyName("allowGenderFemale")]
        public bool AllowGenderFemale { get; set; }

        [JsonPropertyName("allowGenderMale")]
        public bool AllowGenderMale { get; set; }

        [JsonPropertyName("allowGenderOther")]
        public bool AllowGenderOther { get; set; }

        [JsonPropertyName("jobDescription")]
        public string? JobDescription { get; set; }

        [JsonPropertyName("invitationCustomText")]
        public string? InvitationCustomText { get; set; }

        [JsonPropertyName("location")]
        public string? Location { get; set; }

        [JsonPropertyName("package")]
        public float? Package { get; set; }

        [JsonPropertyName("ctcMin")]
        public float? CtcMin { get; set; }

        [JsonPropertyName("ctcMax")]
        public float? CtcMax { get; set; }

        [JsonPropertyName("ctcAdditionalInfo")]
        public string? CtcAdditionalInfo { get; set; }

        [JsonPropertyName("ctcInterval")]
        public string? CtcInterval { get; set; }

        [JsonPropertyName("requiredSkills")]
        public List<string> RequiredSkills { get; set; } = new();

        [JsonPropertyName("stages")]
        public List<HiringStage>? Stages { get; set; }

        [JsonPropertyName("documents")]
        public List<SuperSetDocumentDto> Documents { get; set; } = new();
    }

    public class HiringStage
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("sequence")]
        public int Sequence { get; set; }
    }

    public class SuperSetDocumentDto
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("identifier")]
        public string Identifier { get; set; } = string.Empty;
    }

    // ================================================================
    // Structured Job (internal processing model)
    // ================================================================
    public class StructuredJob
    {
        public string Id { get; set; } = string.Empty;
        public string JobProfile { get; set; } = string.Empty;
        public string Company { get; set; } = string.Empty;
        public int PlacementCategoryCode { get; set; }
        public string PlacementCategory { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
        public long? CreatedAt { get; set; }
        public long? Deadline { get; set; }
        public List<EligibilityMark> EligibilityMarks { get; set; } = new();
        public List<string> EligibilityCourses { get; set; } = new();
        public List<string> AllowedGenders { get; set; } = new();
        public string JobDescription { get; set; } = string.Empty;
        public string Location { get; set; } = "Unknown";
        public float Package { get; set; }
        public string? AnnumMonths { get; set; }
        public string PackageInfo { get; set; } = string.Empty;
        public List<string> RequiredSkills { get; set; } = new();
        public List<string> HiringFlow { get; set; } = new();
        public string? PlacementType { get; set; }
        public List<StructuredDocument> Documents { get; set; } = new();
    }

    public class EligibilityMark
    {
        public string Level { get; set; } = string.Empty;
        public float Criteria { get; set; }
    }

    public class StructuredDocument
    {
        public string Name { get; set; } = string.Empty;
        public string Identifier { get; set; } = string.Empty;
        public string? Url { get; set; }
        public string? LocalPath { get; set; }
        public string? ContentType { get; set; }
        public long FileSize { get; set; }
    }

    // ================================================================
    // Sync Result
    // ================================================================
    public class SyncResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public int Fetched { get; set; }
        public int Inserted { get; set; }
        public int Updated { get; set; }
        public int Skipped { get; set; }
        public int Failed { get; set; }
        public int DocumentsFound { get; set; }
        public int DocumentsDownloaded { get; set; }
        public int DocumentsSkipped { get; set; }
        public int DocumentsFailed { get; set; }
    }
}
