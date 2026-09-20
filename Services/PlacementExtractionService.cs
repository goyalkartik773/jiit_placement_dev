using System.Text.Json;
using System.Text;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Extracts student placement information from congratulation emails using Gemini LLM.
    /// </summary>
    public interface IPlacementExtractionService
    {
        Task<List<PlacementInfo>> ExtractPlacementsAsync(string emailContent, string subject);
    }

    public class PlacementExtractionService : IPlacementExtractionService
    {
        private readonly IConfiguration _config;
        private readonly ILogger<PlacementExtractionService> _logger;
        private readonly HttpClient _httpClient;

        public PlacementExtractionService(IConfiguration config, ILogger<PlacementExtractionService> logger, HttpClient httpClient)
        {
            _config = config;
            _logger = logger;
            _httpClient = httpClient;
        }

        public async Task<List<PlacementInfo>> ExtractPlacementsAsync(string emailContent, string subject)
        {
            var apiKey = _config["Gemini:ApiKey"];
            if (string.IsNullOrEmpty(apiKey))
            {
                _logger.LogWarning("Gemini API key not configured, returning empty placements");
                return new List<PlacementInfo>();
            }

            try
            {
                var model = _config["Gemini:Model"] ?? "gemini-2.0-flash";
                var baseUrl = _config["Gemini:BaseUrl"] ?? "https://generativelanguage.googleapis.com";

                var prompt = BuildExtractionPrompt(emailContent, subject);
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
                        responseMimeType = "application/json",
                        responseSchema = new
                        {
                            type = "OBJECT",
                            properties = new
                            {
                                placements = new
                                {
                                    type = "ARRAY",
                                    items = new
                                    {
                                        type = "OBJECT",
                                        properties = new
                                        {
                                            student_name = new { type = "STRING" },
                                            student_email = new { type = "STRING" },
                                            company_name = new { type = "STRING" },
                                            job_profile = new { type = "STRING" },
                                            package = new { type = "STRING" },
                                            location = new { type = "STRING" },
                                            batch = new { type = "STRING" },
                                            placement_type = new { type = "STRING" },
                                            is_placement = new { type = "BOOLEAN" },
                                            confidence = new { type = "NUMBER" }
                                        },
                                        required = new[] { "student_name", "company_name", "is_placement", "confidence" }
                                    }
                                }
                            },
                            required = new[] { "placements" }
                        }
                    }
                };

                var url = $"{baseUrl}/v1beta/models/{model}:generateContent?key={apiKey}";
                var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
                var response = await _httpClient.PostAsync(url, content);
                var responseJson = await response.Content.ReadAsStringAsync();

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning("Gemini API error: {Status} {Response}", response.StatusCode, responseJson);
                    return new List<PlacementInfo>();
                }

                var result = JsonSerializer.Deserialize<JsonElement>(responseJson);
                var text = result.GetProperty("candidates")[0]
                    .GetProperty("content").GetProperty("parts")[0]
                    .GetProperty("text").GetString() ?? "";

                return ParsePlacementResponse(text);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to extract placements from email");
                return new List<PlacementInfo>();
            }
        }

        private string BuildExtractionPrompt(string content, string subject)
        {
            return $@"You are a placement data extraction system. Analyze this congratulation/offering email from a college placement group and extract ALL student placement information.

SUBJECT: {subject}

EMAIL CONTENT:
{content}

EXTRACT:
1. Each student mentioned as placed/offered/intern
2. Company name (normalize: 'SmartShift Technologies' not 'smartShift')
3. Job profile/role
4. Package/CTC if mentioned (extract numeric value in INR, e.g., '8 LPA' = '800000')
5. Location if mentioned
6. Batch year (e.g., '2027', 'Batch 2027')
7. Placement type: 'FULL_TIME', 'INTERN', 'INTERN_TO_PPO', 'PPO', 'TRAINING'
8. Is this actually a placement/offering? (not just an interview reminder or shortlisting)

RULES:
- If the email lists multiple students (like a shortlist or congratulations list), extract ALL of them
- If the email is just an interview reminder or shortlisting (not final offer), set is_placement=false
- If the email says 'congratulations' or 'offer' or 'selected' or 'placed', it IS a placement
- If the email is about internship conversion to full-time, it IS a placement
- Normalize company names to proper case
- Extract student names exactly as written

Return JSON with a 'placements' array. If no placements found, return empty array.";
        }

        private List<PlacementInfo> ParsePlacementResponse(string json)
        {
            try
            {
                var result = JsonSerializer.Deserialize<JsonElement>(json);
                var placements = new List<PlacementInfo>();

                if (result.TryGetProperty("placements", out var placementsArray))
                {
                    foreach (var item in placementsArray.EnumerateArray())
                    {
                        var isPlacement = item.TryGetProperty("is_placement", out var ip) && ip.GetBoolean();
                        var confidence = item.TryGetProperty("confidence", out var conf) ? conf.GetDouble() : 0;

                        if (!isPlacement || confidence < 0.5) continue;

                        placements.Add(new PlacementInfo
                        {
                            StudentName = GetProp(item, "student_name"),
                            StudentEmail = GetProp(item, "student_email"),
                            CompanyName = NormalizeCompany(GetProp(item, "company_name")),
                            JobProfile = GetProp(item, "job_profile"),
                            Package = GetProp(item, "package"),
                            Location = GetProp(item, "location"),
                            Batch = GetProp(item, "batch"),
                            PlacementType = GetProp(item, "placement_type"),
                            Confidence = confidence
                        });
                    }
                }

                return placements;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to parse placement response");
                return new List<PlacementInfo>();
            }
        }

        private string GetProp(JsonElement item, string name)
        {
            return item.TryGetProperty(name, out var val) ? val.GetString() ?? "" : "";
        }

        private string NormalizeCompany(string name)
        {
            if (string.IsNullOrWhiteSpace(name)) return name;
            // Common normalizations
            return name.Trim() switch
            {
                var n when n.Contains("SmartShift", StringComparison.OrdinalIgnoreCase) => "SmartShift Technologies",
                var n when n.Contains("Amazon", StringComparison.OrdinalIgnoreCase) => "Amazon",
                var n when n.Contains("Uber", StringComparison.OrdinalIgnoreCase) => "Uber",
                var n when n.Contains("Cadence", StringComparison.OrdinalIgnoreCase) => "Cadence",
                var n when n.Contains("Infosys", StringComparison.OrdinalIgnoreCase) => "Infosys",
                var n when n.Contains("STMicro", StringComparison.OrdinalIgnoreCase) => "STMicroelectronics",
                _ => name.Trim()
            };
        }
    }

    public class PlacementInfo
    {
        public string StudentName { get; set; } = "";
        public string StudentEmail { get; set; } = "";
        public string CompanyName { get; set; } = "";
        public string JobProfile { get; set; } = "";
        public string Package { get; set; } = "";
        public string Location { get; set; } = "";
        public string Batch { get; set; } = "";
        public string PlacementType { get; set; } = "";
        public double Confidence { get; set; }
    }
}
