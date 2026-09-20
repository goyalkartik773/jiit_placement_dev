using System.Text;
using System.Text.Json;
using JIITPlacement.Models;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public interface IEmailExtractionService
    {
        /// <summary>
        /// Classify and extract structured information from email content using Gemini LLM.
        /// </summary>
        Task<EmailExtractionResult> ExtractAsync(string content, string subject);
    }

    public class EmailExtractionService : IEmailExtractionService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly GeminiSettings _geminiSettings;
        private readonly ILogger<EmailExtractionService> _logger;

        // Valid categories
        private static readonly HashSet<string> ValidCategories = new(StringComparer.OrdinalIgnoreCase)
        {
            "placement_offer", "shortlisting", "job_posting", "webinar", "hackathon",
            "internship_noc", "policy_update", "announcement", "reminder", "update", "irrelevant"
        };

        public EmailExtractionService(
            IHttpClientFactory httpClientFactory,
            IOptions<GeminiSettings> geminiOptions,
            ILogger<EmailExtractionService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _geminiSettings = geminiOptions.Value;
            _logger = logger;
        }

        /// <summary>
        /// Call Gemini LLM to classify and extract structured information from email content.
        /// </summary>
        public async Task<EmailExtractionResult> ExtractAsync(string content, string subject)
        {
            var result = new EmailExtractionResult();

            if (string.IsNullOrWhiteSpace(_geminiSettings.ApiKey))
            {
                _logger.LogWarning("Gemini API key not configured, returning default extraction");
                result.Category = "irrelevant";
                result.IsRelevant = false;
                result.RejectionReason = "Gemini API key not configured";
                return result;
            }

            try
            {
                var prompt = BuildExtractionPrompt(content, subject);
                var response = await CallGeminiAsync(prompt);

                if (response != null)
                {
                    result = MapLlmResponseToResult(response);
                }
                else
                {
                    result.Category = "irrelevant";
                    result.IsRelevant = false;
                    result.RejectionReason = "LLM returned null response";
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "LLM extraction failed");
                result.Category = "irrelevant";
                result.IsRelevant = false;
                result.RejectionReason = $"LLM extraction failed: {ex.Message}";
            }

            return result;
        }

        /// <summary>
        /// Build the extraction prompt for Gemini.
        /// </summary>
        private string BuildExtractionPrompt(string content, string subject)
        {
            // Truncate content to avoid token limits (keep first 8000 chars)
            var truncatedContent = content.Length > 8000 ? content.Substring(0, 8000) + "\n...[truncated]" : content;

            return $@"You are extracting structured information from a JIIT placement-related email.

Use ONLY information explicitly present in the supplied email and attachments.

Never invent:
- company
- role
- package
- date
- student
- enrollment number
- link
- event
- eligibility
- hiring stage

If information is missing, return null.

For arrays with no information, return [].

A placement_offer requires:
1. final/confirmed selection/placement/offer
2. quantifiable compensation.

Shortlisting/interview/assessment selection is NOT placement_offer.

Extract only student names and enrollment numbers.
Never output student email addresses or phone numbers.

Return valid JSON only.
Do not return markdown.
Do not return explanations.

Email Subject: {subject}

Email Content:
{truncatedContent}

Respond with a JSON object matching this exact schema:
{{
  ""category"": ""placement_offer|shortlisting|job_posting|webinar|hackathon|internship_noc|policy_update|announcement|reminder|update|irrelevant"",
  ""is_relevant"": true/false,
  ""rejection_reason"": null or string,
  ""title"": null or string,
  ""content"": null or string,
  ""company"": null or string,
  ""role"": null or string,
  ""package_lpa"": null or number,
  ""package_details"": null or string,
  ""job_type"": null or string,
  ""location"": null or string,
  ""joining_date"": null or string,
  ""deadline"": null or string,
  ""interview_date"": null or string,
  ""round"": null or string,
  ""venue"": null or string,
  ""event_name"": null or string,
  ""topic"": null or string,
  ""speaker"": null or string,
  ""start_date"": null or string,
  ""end_date"": null or string,
  ""registration_deadline"": null or string,
  ""registration_link"": null or string,
  ""prize_pool"": null or string,
  ""team_size"": null or string,
  ""organizer"": null or string,
  ""eligibility_criteria"": [],
  ""hiring_flow"": [],
  ""students"": [],
  ""total_students"": 0,
  ""links"": [],
  ""additional_info"": null or string
}}";
        }

        /// <summary>
        /// Call Gemini API with the extraction prompt.
        /// </summary>
        private async Task<LlmExtractionResponse?> CallGeminiAsync(string prompt)
        {
            var client = _httpClientFactory.CreateClient("Gemini");

            var requestBody = new
            {
                contents = new[]
                {
                    new
                    {
                        parts = new[]
                        {
                            new { text = prompt }
                        }
                    }
                },
                generationConfig = new
                {
                    temperature = 0.1,
                    maxOutputTokens = 4096,
                    responseMimeType = "application/json"
                }
            };

            var url = $"/v1beta/models/{_geminiSettings.Model}:generateContent?key={_geminiSettings.ApiKey}";
            var json = JsonSerializer.Serialize(requestBody);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await client.PostAsync(url, content);
            var responseString = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError("Gemini API returned {StatusCode}: {Response}",
                    response.StatusCode, responseString);
                return null;
            }

            // Parse Gemini response
            var geminiResponse = JsonSerializer.Deserialize<JsonElement>(responseString);

            if (geminiResponse.TryGetProperty("candidates", out var candidates) &&
                candidates.GetArrayLength() > 0)
            {
                var candidate = candidates[0];
                if (candidate.TryGetProperty("content", out var contentProp) &&
                    contentProp.TryGetProperty("parts", out var parts) &&
                    parts.GetArrayLength() > 0)
                {
                    var textContent = parts[0].GetProperty("text").GetString();
                    if (!string.IsNullOrEmpty(textContent))
                    {
                        // Clean the response (remove markdown code blocks if present)
                        textContent = CleanJsonResponse(textContent);

                        return JsonSerializer.Deserialize<LlmExtractionResponse>(textContent);
                    }
                }
            }

            _logger.LogWarning("Could not parse Gemini response");
            return null;
        }

        /// <summary>
        /// Clean JSON response from LLM (remove markdown formatting).
        /// </summary>
        private string CleanJsonResponse(string response)
        {
            // Remove markdown code blocks
            response = response.Trim();
            if (response.StartsWith("```json"))
                response = response.Substring(7);
            else if (response.StartsWith("```"))
                response = response.Substring(3);

            if (response.EndsWith("```"))
                response = response.Substring(0, response.Length - 3);

            return response.Trim();
        }

        /// <summary>
        /// Map LLM response to EmailExtractionResult.
        /// </summary>
        private EmailExtractionResult MapLlmResponseToResult(LlmExtractionResponse llm)
        {
            return new EmailExtractionResult
            {
                Category = llm.Category ?? "irrelevant",
                IsRelevant = llm.IsRelevant,
                RejectionReason = llm.RejectionReason,
                Title = llm.Title,
                Content = llm.Content,
                Company = llm.Company,
                Role = llm.Role,
                PackageLpa = llm.PackageLpa,
                PackageDetails = llm.PackageDetails,
                JobType = llm.JobType,
                Location = llm.Location,
                JoiningDate = llm.JoiningDate,
                Deadline = llm.Deadline,
                InterviewDate = llm.InterviewDate,
                Round = llm.Round,
                Venue = llm.Venue,
                EventName = llm.EventName,
                Topic = llm.Topic,
                Speaker = llm.Speaker,
                StartDate = llm.StartDate,
                EndDate = llm.EndDate,
                RegistrationDeadline = llm.RegistrationDeadline,
                RegistrationLink = llm.RegistrationLink,
                PrizePool = llm.PrizePool,
                TeamSize = llm.TeamSize,
                Organizer = llm.Organizer,
                EligibilityCriteria = llm.EligibilityCriteria != null
                    ? JsonSerializer.Serialize(llm.EligibilityCriteria)
                    : "[]",
                HiringFlow = llm.HiringFlow != null
                    ? JsonSerializer.Serialize(llm.HiringFlow)
                    : "[]",
                Students = llm.Students != null
                    ? JsonSerializer.Serialize(llm.Students)
                    : "[]",
                TotalStudents = llm.TotalStudents,
                Links = llm.Links != null
                    ? JsonSerializer.Serialize(llm.Links)
                    : "[]",
                AdditionalInfo = llm.AdditionalInfo
            };
        }
    }
}
