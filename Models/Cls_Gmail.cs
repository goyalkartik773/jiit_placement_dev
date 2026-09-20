using System.Text.Json.Serialization;

namespace JIITPlacement.Models
{
    // ================================================================
    // Google Gmail Settings (config from appsettings.json)
    // ================================================================
    public class GoogleGmailSettings
    {
        public const string SectionName = "GoogleGmail";
        public string ApplicationName { get; set; } = "JIIT Placement";
        public string ClientId { get; set; } = string.Empty;
        public string ClientSecret { get; set; } = string.Empty;
        public List<string> Scopes { get; set; } = new() { "https://www.googleapis.com/auth/gmail.readonly" };
        public List<SourceGroup> SourceGroups { get; set; } = new();
        public string CredentialsFilePath { get; set; } = string.Empty;
        public string TokenFilePath { get; set; } = string.Empty;
    }

    public class SourceGroup
    {
        public string Name { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
    }

    // ================================================================
    // Gemini Settings (config from appsettings.json)
    // ================================================================
    public class GeminiSettings
    {
        public const string SectionName = "Gemini";
        public string ApiKey { get; set; } = string.Empty;
        public string Model { get; set; } = "gemini-2.0-flash";
        public string BaseUrl { get; set; } = "https://generativelanguage.googleapis.com";
    }

    // ================================================================
    // Admin Gmail Sync Request
    // ================================================================
    public class GmailSyncRequest
    {
        /// <summary>
        /// Gmail search query (e.g., "after:2026/09/01"). Combined with group filters.
        /// </summary>
        public string? Query { get; set; }

        /// <summary>
        /// Maximum results per group. Default 100.
        /// </summary>
        public int MaxResults { get; set; } = 100;

        /// <summary>
        /// Optional: process only specific group emails. If empty, processes all configured groups.
        /// </summary>
        public List<string>? Groups { get; set; }
    }

    // ================================================================
    // Gmail Message (raw record model)
    // ================================================================
    public class GmailMessageRecord
    {
        public string Id { get; set; } = string.Empty;
        public string GmailMessageId { get; set; } = string.Empty;
        public string GmailThreadId { get; set; } = string.Empty;
        public string? SourceGroup { get; set; }
        public string? SourceGroupEmail { get; set; }
        public string? Sender { get; set; }
        public string? Recipient { get; set; }
        public string? Cc { get; set; }
        public string? Bcc { get; set; }
        public string? ReplyTo { get; set; }
        public string? Subject { get; set; }
        public string? ReceivedAt { get; set; }
        public string? BodyText { get; set; }
        public string? BodyHtml { get; set; }
        public string? Snippet { get; set; }
        public bool HasAttachments { get; set; }
        public string? LabelIds { get; set; }
        public string? RawPayload { get; set; }
        public string ProcessingStatus { get; set; } = "RECEIVED";
        public string? CreatedAt { get; set; }
        public string? UpdatedAt { get; set; }
    }

    // ================================================================
    // Gmail Attachment record
    // ================================================================
    public class GmailAttachmentRecord
    {
        public string Id { get; set; } = string.Empty;
        public string SysGmailMessageUuid { get; set; } = string.Empty;
        public string GmailAttachmentId { get; set; } = string.Empty;
        public string Filename { get; set; } = string.Empty;
        public string MimeType { get; set; } = string.Empty;
        public long FileSize { get; set; }
        public string? FilePath { get; set; }
        public string? ExtractedText { get; set; }
        public string Status { get; set; } = "Active";
        public string? CreatedAt { get; set; }
        public string? UpdatedAt { get; set; }
    }

    // ================================================================
    // Parsed email (intermediate model after MIME parsing)
    // ================================================================
    public class ParsedEmail
    {
        public string GmailMessageId { get; set; } = string.Empty;
        public string? Sender { get; set; }
        public string? Recipient { get; set; }
        public string? Cc { get; set; }
        public string? Bcc { get; set; }
        public string? ReplyTo { get; set; }
        public string? Subject { get; set; }
        public string? ReceivedAt { get; set; }
        public string BodyText { get; set; } = string.Empty;
        public string BodyHtml { get; set; } = string.Empty;
        public string CleanedContent { get; set; } = string.Empty;
        public List<ParsedLink> Links { get; set; } = new();
        public List<ParsedAttachment> Attachments { get; set; } = new();
        public string? SourceGroup { get; set; }
        public string? SourceGroupEmail { get; set; }
        public string? Snippet { get; set; }
        public bool HasAttachments { get; set; }
        public string? LabelIds { get; set; }
        public string? RawPayload { get; set; }
    }

    public class ParsedLink
    {
        public string Url { get; set; } = string.Empty;
        public string? Label { get; set; }
        public string LinkType { get; set; } = "unknown";
    }

    public class ParsedAttachment
    {
        public string AttachmentId { get; set; } = string.Empty;
        public string Filename { get; set; } = string.Empty;
        public string MimeType { get; set; } = string.Empty;
        public long FileSize { get; set; }
        public byte[]? Data { get; set; }
        public string? ExtractedText { get; set; }
    }

    // ================================================================
    // Extraction result (structured output from LLM + validation)
    // ================================================================
    public class EmailExtractionResult
    {
        public string Id { get; set; } = string.Empty;
        public string SysGmailMessageUuid { get; set; } = string.Empty;
        public string Category { get; set; } = string.Empty;
        public bool IsRelevant { get; set; }
        public string? RejectionReason { get; set; }
        public string? Title { get; set; }
        public string? Content { get; set; }
        public string? Source { get; set; }
        public string? Company { get; set; }
        public string? Role { get; set; }
        public decimal? PackageLpa { get; set; }
        public string? PackageDetails { get; set; }
        public string? JobType { get; set; }
        public string? Location { get; set; }
        public string? JoiningDate { get; set; }
        public string? Deadline { get; set; }
        public string? InterviewDate { get; set; }
        public string? Round { get; set; }
        public string? Venue { get; set; }
        public string? EventName { get; set; }
        public string? Topic { get; set; }
        public string? Speaker { get; set; }
        public string? StartDate { get; set; }
        public string? EndDate { get; set; }
        public string? RegistrationDeadline { get; set; }
        public string? RegistrationLink { get; set; }
        public string? PrizePool { get; set; }
        public string? TeamSize { get; set; }
        public string? Organizer { get; set; }
        public string? EligibilityCriteria { get; set; }
        public string? HiringFlow { get; set; }
        public string? Students { get; set; }
        public int TotalStudents { get; set; }
        public string? Links { get; set; }
        public string? AdditionalInfo { get; set; }
        public string ProcessingStatus { get; set; } = "RECEIVED";
        public string? ValidationMessage { get; set; }
        public string? CreatedAt { get; set; }
        public string? UpdatedAt { get; set; }
    }

    // ================================================================
    // LLM Extraction Response (raw from Gemini)
    // ================================================================
    public class LlmExtractionResponse
    {
        [JsonPropertyName("category")]
        public string? Category { get; set; }

        [JsonPropertyName("is_relevant")]
        public bool IsRelevant { get; set; }

        [JsonPropertyName("rejection_reason")]
        public string? RejectionReason { get; set; }

        [JsonPropertyName("title")]
        public string? Title { get; set; }

        [JsonPropertyName("content")]
        public string? Content { get; set; }

        [JsonPropertyName("source")]
        public string? Source { get; set; }

        [JsonPropertyName("company")]
        public string? Company { get; set; }

        [JsonPropertyName("role")]
        public string? Role { get; set; }

        [JsonPropertyName("package_lpa")]
        public decimal? PackageLpa { get; set; }

        [JsonPropertyName("package_details")]
        public string? PackageDetails { get; set; }

        [JsonPropertyName("job_type")]
        public string? JobType { get; set; }

        [JsonPropertyName("location")]
        public string? Location { get; set; }

        [JsonPropertyName("joining_date")]
        public string? JoiningDate { get; set; }

        [JsonPropertyName("deadline")]
        public string? Deadline { get; set; }

        [JsonPropertyName("interview_date")]
        public string? InterviewDate { get; set; }

        [JsonPropertyName("round")]
        public string? Round { get; set; }

        [JsonPropertyName("venue")]
        public string? Venue { get; set; }

        [JsonPropertyName("event_name")]
        public string? EventName { get; set; }

        [JsonPropertyName("topic")]
        public string? Topic { get; set; }

        [JsonPropertyName("speaker")]
        public string? Speaker { get; set; }

        [JsonPropertyName("start_date")]
        public string? StartDate { get; set; }

        [JsonPropertyName("end_date")]
        public string? EndDate { get; set; }

        [JsonPropertyName("registration_deadline")]
        public string? RegistrationDeadline { get; set; }

        [JsonPropertyName("registration_link")]
        public string? RegistrationLink { get; set; }

        [JsonPropertyName("prize_pool")]
        public string? PrizePool { get; set; }

        [JsonPropertyName("team_size")]
        public string? TeamSize { get; set; }

        [JsonPropertyName("organizer")]
        public string? Organizer { get; set; }

        [JsonPropertyName("eligibility_criteria")]
        public List<string>? EligibilityCriteria { get; set; }

        [JsonPropertyName("hiring_flow")]
        public List<string>? HiringFlow { get; set; }

        [JsonPropertyName("students")]
        public List<StudentInfo>? Students { get; set; }

        [JsonPropertyName("total_students")]
        public int TotalStudents { get; set; }

        [JsonPropertyName("links")]
        public List<ExtractionLink>? Links { get; set; }

        [JsonPropertyName("additional_info")]
        public string? AdditionalInfo { get; set; }
    }

    public class StudentInfo
    {
        [JsonPropertyName("name")]
        public string? Name { get; set; }

        [JsonPropertyName("enrollment_number")]
        public string? EnrollmentNumber { get; set; }

        [JsonPropertyName("role")]
        public string? Role { get; set; }

        [JsonPropertyName("package_lpa")]
        public decimal? PackageLpa { get; set; }

        [JsonPropertyName("company")]
        public string? Company { get; set; }
    }

    public class ExtractionLink
    {
        [JsonPropertyName("url")]
        public string? Url { get; set; }

        [JsonPropertyName("label")]
        public string? Label { get; set; }

        [JsonPropertyName("link_type")]
        public string? LinkType { get; set; }
    }

    // ================================================================
    // Token Data (persisted to token.json)
    // ================================================================
    public class TokenData
    {
        public string? AccessToken { get; set; }
        public string? RefreshToken { get; set; }
        public long? ExpiresInSeconds { get; set; }
        public DateTime IssuedUtc { get; set; }
    }

    // ================================================================
    // Gmail Sync Result (per-group statistics)
    // ================================================================
    public class GmailSyncResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public List<GmailGroupSyncResult> Groups { get; set; } = new();
        public int TotalFetched { get; set; }
        public int TotalProcessed { get; set; }
        public int TotalReviewRequired { get; set; }
        public int TotalFailed { get; set; }
    }

    public class GmailGroupSyncResult
    {
        public string GroupName { get; set; } = string.Empty;
        public string GroupEmail { get; set; } = string.Empty;
        public int Fetched { get; set; }
        public int NewMessages { get; set; }
        public int ExistingMessages { get; set; }
        public int AttachmentsFound { get; set; }
        public int AttachmentsProcessed { get; set; }
        public int Processed { get; set; }
        public int ReviewRequired { get; set; }
        public int Failed { get; set; }
    }
}
