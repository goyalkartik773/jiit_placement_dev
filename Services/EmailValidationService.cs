using System.Text.Json;
using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface IEmailValidationService
    {
        /// <summary>
        /// Validate an extraction result deterministically.
        /// </summary>
        ValidationResult Validate(EmailExtractionResult extraction);
    }

    public class EmailValidationService : IEmailValidationService
    {
        private readonly ILogger<EmailValidationService> _logger;

        // Valid categories
        private static readonly HashSet<string> ValidCategories = new(StringComparer.OrdinalIgnoreCase)
        {
            "placement_offer", "shortlisting", "job_posting", "webinar", "hackathon",
            "internship_noc", "policy_update", "announcement", "reminder", "update", "irrelevant"
        };

        public EmailValidationService(ILogger<EmailValidationService> logger)
        {
            _logger = logger;
        }

        /// <summary>
        /// Perform deterministic validation on extraction results.
        /// </summary>
        public ValidationResult Validate(EmailExtractionResult extraction)
        {
            var errors = new List<string>();

            // Rule 1: Category must be valid
            if (!ValidCategories.Contains(extraction.Category))
            {
                errors.Add($"Invalid category: {extraction.Category}");
            }

            // Rule 2: Irrelevant → is_relevant must be false
            if (extraction.Category == "irrelevant" && extraction.IsRelevant)
            {
                errors.Add("Category is irrelevant but is_relevant is true");
            }

            // Rule 3: Relevant category → is_relevant must be true
            if (extraction.Category != "irrelevant" && !extraction.IsRelevant)
            {
                errors.Add($"Category is {extraction.Category} but is_relevant is false");
            }

            // Rule 4: placement_offer requires final selection evidence
            if (extraction.Category == "placement_offer")
            {
                if (!extraction.IsRelevant)
                {
                    errors.Add("placement_offer must have is_relevant = true");
                }
            }

            // Rule 5: placement_offer requires quantifiable compensation
            if (extraction.Category == "placement_offer")
            {
                if (!extraction.PackageLpa.HasValue || extraction.PackageLpa.Value <= 0)
                {
                    errors.Add("placement_offer requires quantifiable compensation (package_lpa)");
                }
            }

            // Rule 6: Students count validation
            if (!string.IsNullOrEmpty(extraction.Students) && extraction.Students != "[]")
            {
                try
                {
                    var students = JsonSerializer.Deserialize<List<StudentInfo>>(extraction.Students);
                    if (students != null && students.Count != extraction.TotalStudents)
                    {
                        errors.Add($"Student count mismatch: students.length={students.Count} but total_students={extraction.TotalStudents}");
                    }
                }
                catch
                {
                    errors.Add("Failed to parse students JSON");
                }
            }

            // Rule 7: package_lpa must be numeric when present
            if (extraction.PackageLpa.HasValue && extraction.PackageLpa.Value < 0)
            {
                errors.Add("package_lpa must be non-negative");
            }

            // Rule 8: Dates should be valid if present
            ValidateDate(extraction.JoiningDate, "joining_date", errors);
            ValidateDate(extraction.Deadline, "deadline", errors);
            ValidateDate(extraction.InterviewDate, "interview_date", errors);
            ValidateDate(extraction.StartDate, "start_date", errors);
            ValidateDate(extraction.EndDate, "end_date", errors);
            ValidateDate(extraction.RegistrationDeadline, "registration_deadline", errors);

            // Rule 9: URLs should be valid if present
            ValidateUrl(extraction.RegistrationLink, "registration_link", errors);

            // Rule 10: Links validation
            if (!string.IsNullOrEmpty(extraction.Links) && extraction.Links != "[]")
            {
                try
                {
                    var links = JsonSerializer.Deserialize<List<ExtractionLink>>(extraction.Links);
                    if (links != null)
                    {
                        foreach (var link in links)
                        {
                            if (!string.IsNullOrEmpty(link.Url))
                            {
                                ValidateUrl(link.Url, "link", errors);
                            }
                        }
                    }
                }
                catch
                {
                    errors.Add("Failed to parse links JSON");
                }
            }

            // Rule 11: Category-specific validation
            ValidateCategorySpecific(extraction, errors);

            var isValid = errors.Count == 0;

            if (!isValid)
            {
                _logger.LogWarning("Extraction validation failed with {ErrorCount} errors: {Errors}",
                    errors.Count, string.Join("; ", errors));
            }

            return new ValidationResult
            {
                IsValid = isValid,
                Errors = errors
            };
        }

        private void ValidateDate(string? dateStr, string fieldName, List<string> errors)
        {
            if (string.IsNullOrWhiteSpace(dateStr)) return;

            // Try to parse as DateTime using invariant culture
            if (DateTime.TryParse(dateStr, System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out _))
                return;

            // Common date patterns in placement emails
            var patterns = new[] { "dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd", "dd-MM-yyyy", "dd MMM yyyy" };
            if (DateTime.TryParseExact(dateStr, patterns,
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out _))
                return;

            errors.Add($"Invalid date format in {fieldName}: {dateStr}");
        }

        private void ValidateUrl(string? url, string fieldName, List<string> errors)
        {
            if (string.IsNullOrWhiteSpace(url)) return;

            if (Uri.TryCreate(url, UriKind.Absolute, out var uri))
            {
                if (uri.Scheme != "http" && uri.Scheme != "https")
                {
                    errors.Add($"Invalid URL scheme in {fieldName}: {url}");
                }
            }
            else
            {
                errors.Add($"Invalid URL in {fieldName}: {url}");
            }
        }

        private void ValidateCategorySpecific(EmailExtractionResult extraction, List<string> errors)
        {
            switch (extraction.Category?.ToLowerInvariant())
            {
                case "placement_offer":
                    if (string.IsNullOrWhiteSpace(extraction.Company))
                        errors.Add("placement_offer should have company");
                    if (string.IsNullOrWhiteSpace(extraction.Role))
                        errors.Add("placement_offer should have role");
                    break;

                case "shortlisting":
                    if (string.IsNullOrWhiteSpace(extraction.Company))
                        errors.Add("shortlisting should have company");
                    break;

                case "job_posting":
                    if (string.IsNullOrWhiteSpace(extraction.Company))
                        errors.Add("job_posting should have company");
                    if (string.IsNullOrWhiteSpace(extraction.Role))
                        errors.Add("job_posting should have role");
                    break;

                case "webinar":
                case "hackathon":
                    if (string.IsNullOrWhiteSpace(extraction.EventName))
                        errors.Add($"{extraction.Category} should have event_name");
                    break;
            }
        }
    }

    public class ValidationResult
    {
        public bool IsValid { get; set; }
        public List<string> Errors { get; set; } = new();
    }
}
