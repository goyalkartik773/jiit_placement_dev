using System.Text;
using System.Text.Json;
using System.Linq;
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
  ""event_name"": null or string,
  ""topic"": null or string,
  ""registration_link"": null or string,
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
                    maxOutputTokens = 8192,
                    responseMimeType = "application/json"
                }
            };

            var url = $"/v1beta/models/{_geminiSettings.Model}:generateContent?key={_geminiSettings.ApiKey}";
            var json = JsonSerializer.Serialize(requestBody);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            // Retry loop for429 rate limits
            const int maxRetries = 3;
            for (int attempt = 1; attempt <= maxRetries; attempt++)
            {
                var response = await client.PostAsync(url, content);
                var responseString = await response.Content.ReadAsStringAsync();

                if (response.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                {
                    _logger.LogWarning("Gemini429 TooManyRequests (attempt {Attempt}/{Max}), parsing retry delay", attempt, maxRetries);
                    // Parse retry delay from response
                    int retrySeconds = 60; // default
                    try
                    {
                        var errorDoc = JsonSerializer.Deserialize<JsonElement>(responseString);
                        if (errorDoc.TryGetProperty("error", out var err) &&
                            err.TryGetProperty("details", out var details) &&
                            details.GetArrayLength() > 0)
                        {
                            foreach (var detail in details.EnumerateArray())
                            {
                                if (detail.TryGetProperty("@type", out var type) &&
                                    type.GetString()?.Contains("RetryInfo") == true &&
                                    detail.TryGetProperty("retryDelay", out var delay))
                                {
                                    var delayStr = delay.GetString() ?? "60s";
                                    retrySeconds = int.Parse(delayStr.Replace("s", "").Trim());
                                    break;
                                }
                            }
                        }
                    }
                    catch { }

                    if (attempt < maxRetries)
                    {
                        _logger.LogInformation("Waiting {Seconds}s before retry...", retrySeconds);
                        await Task.Delay(retrySeconds * 1000);
                        continue;
                    }
                    else
                    {
                        _logger.LogError("Gemini API429 exhausted after {Max} retries, saving as REVIEW_REQUIRED", maxRetries);
                        return null;
                    }
                }

                // Retry on 503 ServiceUnavailable (Gemini timeout)
                if ((int)response.StatusCode == 503 && attempt < maxRetries)
                {
                    _logger.LogWarning("Gemini503 ServiceUnavailable (attempt {Attempt}/{Max}), retrying in 30s", attempt, maxRetries);
                    await Task.Delay(30000);
                    continue;
                }

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError("Gemini API returned {StatusCode}: {Response}",
                        response.StatusCode, responseString);
                    return null;
                }

                // Success - parse response

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
                        _logger.LogDebug("Gemini raw response (len={Len}): {Response}", textContent.Length, textContent.Length > 500 ? textContent.Substring(0, 500) + "..." : textContent);

                        // Try parsing with truncation repair
                        var result = ParseWithRepair(textContent);
                        if (result != null) return result;
                        return null;
                    }
                }
            }

            _logger.LogWarning("Could not parse Gemini response");
            return null;
            } // end for loop retry

            return null; // unreachable but satisfies compiler
        }

        /// <summary>
        /// Parse JSON with manual extraction and truncation repair.
        /// Uses JsonElement to avoid schema mismatch issues with complex nested types.
        /// </summary>
        private LlmExtractionResponse? ParseWithRepair(string json)
        {
            // Try direct parse first
            var result = TryParseJson(json);
            if (result != null) return result;

            // Try repairing truncated JSON
            _logger.LogWarning("JSON parse failed, attempting truncation repair");
            var repaired = RepairTruncatedJson(json);
            if (repaired != null)
            {
                result = TryParseJson(repaired);
                if (result != null) return result;
            }
            return null;
        }

        private LlmExtractionResponse? TryParseJson(string json)
        {
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                var response = new LlmExtractionResponse();

                if (root.TryGetProperty("category", out var cat))
                    response.Category = cat.GetString();
                if (root.TryGetProperty("is_relevant", out var rel))
                    response.IsRelevant = rel.GetBoolean();
                if (root.TryGetProperty("rejection_reason", out var rej))
                    response.RejectionReason = rej.GetString();
                if (root.TryGetProperty("title", out var title))
                    response.Title = title.GetString();
                if (root.TryGetProperty("content", out var content))
                    response.Content = content.GetString();
                if (root.TryGetProperty("source", out var source))
                    response.Source = source.GetString();
                if (root.TryGetProperty("company", out var company))
                    response.Company = company.GetString();
                if (root.TryGetProperty("role", out var role))
                    response.Role = role.GetString();
                if (root.TryGetProperty("package_lpa", out var pkg))
                {
                    if (pkg.ValueKind == JsonValueKind.Number)
                        response.PackageLpa = pkg.GetDecimal();
                    else if (pkg.ValueKind == JsonValueKind.String && decimal.TryParse(pkg.GetString(), out var pkgVal))
                        response.PackageLpa = pkgVal;
                }
                if (root.TryGetProperty("package_details", out var pkgDet))
                    response.PackageDetails = pkgDet.GetString();
                if (root.TryGetProperty("job_type", out var jt))
                    response.JobType = jt.GetString();
                if (root.TryGetProperty("location", out var loc))
                    response.Location = loc.GetString();
                if (root.TryGetProperty("joining_date", out var jd))
                    response.JoiningDate = jd.GetString();
                if (root.TryGetProperty("deadline", out var dl))
                    response.Deadline = dl.GetString();
                if (root.TryGetProperty("interview_date", out var id))
                    response.InterviewDate = id.GetString();
                if (root.TryGetProperty("round", out var rnd))
                    response.Round = rnd.GetString();
                if (root.TryGetProperty("venue", out var ven))
                    response.Venue = ven.GetString();
                if (root.TryGetProperty("event_name", out var ev))
                    response.EventName = ev.GetString();
                if (root.TryGetProperty("topic", out var topic))
                    response.Topic = topic.GetString();
                if (root.TryGetProperty("speaker", out var speaker))
                    response.Speaker = speaker.GetString();
                if (root.TryGetProperty("start_date", out var sd))
                    response.StartDate = sd.GetString();
                if (root.TryGetProperty("end_date", out var ed))
                    response.EndDate = ed.GetString();
                if (root.TryGetProperty("registration_deadline", out var rd))
                    response.RegistrationDeadline = rd.GetString();
                if (root.TryGetProperty("registration_link", out var rl))
                    response.RegistrationLink = rl.GetString();
                if (root.TryGetProperty("prize_pool", out var pp))
                    response.PrizePool = pp.GetString();
                if (root.TryGetProperty("team_size", out var ts))
                    response.TeamSize = ts.GetString();
                if (root.TryGetProperty("organizer", out var org))
                    response.Organizer = org.GetString();
                if (root.TryGetProperty("additional_info", out var ai))
                    response.AdditionalInfo = ai.GetString();
                if (root.TryGetProperty("total_students", out var ts2))
                    response.TotalStudents = ts2.GetInt32();

                // Parse links as simple list of strings (ignore complex objects)
                if (root.TryGetProperty("links", out var links) && links.ValueKind == JsonValueKind.Array)
                {
                    response.Links = new List<ExtractionLink>();
                    foreach (var link in links.EnumerateArray())
                    {
                        var el = new ExtractionLink();
                        if (link.ValueKind == JsonValueKind.Object)
                        {
                            if (link.TryGetProperty("url", out var url)) el.Url = url.GetString();
                            if (link.TryGetProperty("label", out var lbl)) el.Label = lbl.GetString();
                        }
                        else if (link.ValueKind == JsonValueKind.String)
                        {
                            el.Url = link.GetString();
                        }
                        response.Links.Add(el);
                    }
                }

                // Parse hiring_flow as simple list of strings (ignore objects)
                if (root.TryGetProperty("hiring_flow", out var hf) && hf.ValueKind == JsonValueKind.Array)
                {
                    response.HiringFlow = new List<string>();
                    foreach (var step in hf.EnumerateArray())
                    {
                        if (step.ValueKind == JsonValueKind.String)
                            response.HiringFlow.Add(step.GetString()!);
                        else if (step.ValueKind == JsonValueKind.Object)
                            response.HiringFlow.Add(step.ToString());
                    }
                }

                // Parse eligibility_criteria as simple list of strings
                if (root.TryGetProperty("eligibility_criteria", out var ec) && ec.ValueKind == JsonValueKind.Array)
                {
                    response.EligibilityCriteria = new List<string>();
                    foreach (var crit in ec.EnumerateArray())
                    {
                        if (crit.ValueKind == JsonValueKind.String)
                            response.EligibilityCriteria.Add(crit.GetString()!);
                        else if (crit.ValueKind == JsonValueKind.Object)
                            response.EligibilityCriteria.Add(crit.ToString());
                    }
                }

                // Parse students safely
                if (root.TryGetProperty("students", out var students) && students.ValueKind == JsonValueKind.Array)
                {
                    response.Students = new List<StudentInfo>();
                    foreach (var student in students.EnumerateArray())
                    {
                        if (student.ValueKind != JsonValueKind.Object) continue;
                        var si = new StudentInfo();
                        if (student.TryGetProperty("name", out var n)) si.Name = n.GetString();
                        if (student.TryGetProperty("enrollment_number", out var en)) si.EnrollmentNumber = en.GetString();
                        if (student.TryGetProperty("role", out var r)) si.Role = r.GetString();
                        if (student.TryGetProperty("company", out var c2)) si.Company = c2.GetString();
                        if (student.TryGetProperty("package_lpa", out var p))
                        {
                            if (p.ValueKind == JsonValueKind.Number) si.PackageLpa = p.GetDecimal();
                            else if (p.ValueKind == JsonValueKind.String && decimal.TryParse(p.GetString(), out var pv)) si.PackageLpa = pv;
                        }
                        response.Students.Add(si);
                    }
                }

                return response;
            }
            catch (JsonException jex)
            {
                _logger.LogWarning("JSON parse error: {Error}", jex.Message);
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Parse error: {Error}", ex.Message);
                return null;
            }
        }

        /// <summary>
        /// Attempt to repair truncated JSON by closing open braces.
        /// </summary>
        private string RepairTruncatedJson(string json)
        {
            try
            {
                // Count open vs close braces
                int openBraces = json.Count(c => c == '{');
                int closeBraces = json.Count(c => c == '}');
                int openBrackets = json.Count(c => c == '[');
                int closeBrackets = json.Count(c => c == ']');

                // Remove trailing incomplete value if present (after last comma or colon)
                int lastComplete = json.LastIndexOfAny(new[] { ',', ':' });
                if (lastComplete > 0 && lastComplete < json.Length - 1)
                {
                    json = json.Substring(0, lastComplete + 1).TrimEnd(',', ' ');
                }

                // Close any unclosed brackets/braces
                for (int i = 0; i < openBrackets - closeBrackets; i++) json += "]";
                for (int i = 0; i < openBraces - closeBraces; i++) json += "}";

                return json;
            }
            catch { return null; }
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
