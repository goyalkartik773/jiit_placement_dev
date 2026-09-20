using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using JIITPlacement.Models;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public interface ISuperSetService
    {
        Task<SuperSetLoginResponse> LoginAsync(string username, string password);
        Task<List<SuperSetNoticeDto>> GetNoticesAsync(string uuid, string sessionKey);
        Task<List<SuperSetJobBasicDto>> GetJobListingsBasicAsync(string uuid, string sessionKey);
        Task<SuperSetJobDetailDto?> GetJobDetailsAsync(string uuid, string sessionKey, string jobId);
        Task<string?> GetDocumentUrlAsync(string uuid, string sessionKey, string jobId, string documentId);
    }

    public class SuperSetService : ISuperSetService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly SuperSetOptions _options;
        private readonly ILogger<SuperSetService> _logger;

        public SuperSetService(
            IHttpClientFactory httpClientFactory,
            IOptions<SuperSetOptions> options,
            ILogger<SuperSetService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _options = options.Value;
            _logger = logger;
        }

        public async Task<SuperSetLoginResponse> LoginAsync(string username, string password)
        {
            _logger.LogInformation("SuperSet authentication started for user: {Username}", username);

            var client = _httpClientFactory.CreateClient("SuperSet");

            var encryptedPassword = EncryptPassword(password);
            var loginRequest = new SuperSetLoginRequest
            {
                Username = username,
                Password = encryptedPassword
            };

            var url = $"{_options.ApiBaseUrl}/login";

            var request = new HttpRequestMessage(HttpMethod.Post, url)
            {
                Content = new StringContent(
                    JsonSerializer.Serialize(loginRequest),
                    Encoding.UTF8,
                    "application/json")
            };

            request.Headers.Add("x-requester-client", "webapp");
            request.Headers.Add("x-superset-tenant-id", _options.TenantId);
            request.Headers.Add("x-superset-tenant-type", _options.TenantType);
            request.Headers.Add("Referer", $"{_options.BaseUrl}/students/login");
            request.Headers.Add("Origin", _options.BaseUrl);

            var response = await client.SendAsync(request);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("SuperSet authentication failed with status {StatusCode}", response.StatusCode);
                throw new HttpRequestException($"SuperSet authentication failed: {response.StatusCode} - {errorContent}");
            }

            var loginResponse = await response.Content.ReadFromJsonAsync<SuperSetLoginResponse>();

            if (loginResponse == null)
                throw new InvalidOperationException("Failed to deserialize SuperSet login response");

            _logger.LogInformation("SuperSet authentication successful for user: {Username}", username);

            return loginResponse;
        }

        public async Task<List<SuperSetNoticeDto>> GetNoticesAsync(string uuid, string sessionKey)
        {
            _logger.LogInformation("Fetching notices from SuperSet for UUID: {Uuid}", uuid);

            var client = _httpClientFactory.CreateClient("SuperSet");
            var url = $"{_options.ApiBaseUrl}/students/{uuid}/notices";

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("Authorization", $"Custom {sessionKey}");
            request.Headers.Add("x-requester-client", "webapp");
            request.Headers.Add("x-superset-tenant-id", _options.TenantId);
            request.Headers.Add("x-superset-tenant-type", _options.TenantType);
            request.Headers.Add("Referer", $"{_options.BaseUrl}/students");

            var response = await client.SendAsync(request);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Failed to fetch notices: {StatusCode}", response.StatusCode);
                throw new HttpRequestException($"Failed to fetch notices: {response.StatusCode} - {errorContent}");
            }

            var notices = await response.Content.ReadFromJsonAsync<List<SuperSetNoticeDto>>();

            _logger.LogInformation("Fetched {Count} notices from SuperSet", notices?.Count ?? 0);

            return notices ?? new List<SuperSetNoticeDto>();
        }

        public async Task<List<SuperSetJobBasicDto>> GetJobListingsBasicAsync(string uuid, string sessionKey)
        {
            _logger.LogInformation("Fetching basic job listings from SuperSet for UUID: {Uuid}", uuid);

            var client = _httpClientFactory.CreateClient("SuperSet");
            var url = $"{_options.ApiBaseUrl}/students/{uuid}/job_profiles";

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("Authorization", $"Custom {sessionKey}");
            request.Headers.Add("x-requester-client", "webapp");
            request.Headers.Add("x-superset-tenant-id", _options.TenantId);
            request.Headers.Add("x-superset-tenant-type", _options.TenantType);
            request.Headers.Add("Referer", $"{_options.BaseUrl}/students/jobprofiles");

            var response = await client.SendAsync(request);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Failed to fetch job listings: {StatusCode}", response.StatusCode);
                throw new HttpRequestException($"Failed to fetch job listings: {response.StatusCode} - {errorContent}");
            }

            var jobs = await response.Content.ReadFromJsonAsync<List<SuperSetJobBasicDto>>();

            _logger.LogInformation("Fetched {Count} basic job listings from SuperSet", jobs?.Count ?? 0);

            return jobs ?? new List<SuperSetJobBasicDto>();
        }

        public async Task<SuperSetJobDetailDto?> GetJobDetailsAsync(string uuid, string sessionKey, string jobId)
        {
            _logger.LogInformation("Fetching job details for job ID: {JobId}", jobId);

            var client = _httpClientFactory.CreateClient("SuperSet");
            var url = $"{_options.ApiBaseUrl}/students/{uuid}/job_profiles/{jobId}";

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("Authorization", $"Custom {sessionKey}");
            request.Headers.Add("x-requester-client", "webapp");
            request.Headers.Add("x-superset-tenant-id", _options.TenantId);
            request.Headers.Add("x-superset-tenant-type", _options.TenantType);
            request.Headers.Add("Referer", $"{_options.BaseUrl}/students/jobprofiles");

            var response = await client.SendAsync(request);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Failed to fetch job details for {JobId}: {StatusCode}", jobId, response.StatusCode);
                throw new HttpRequestException($"Failed to fetch job details: {response.StatusCode} - {errorContent}");
            }

            var jobDetail = await response.Content.ReadFromJsonAsync<SuperSetJobDetailDto>();

            _logger.LogInformation("Fetched job details for job ID: {JobId}", jobId);

            return jobDetail;
        }

        public async Task<string?> GetDocumentUrlAsync(string uuid, string sessionKey, string jobId, string documentId)
        {
            _logger.LogInformation("Fetching document URL for job {JobId}, document {DocumentId}", jobId, documentId);

            var client = _httpClientFactory.CreateClient("SuperSet");
            var url = $"{_options.ApiBaseUrl}/students/{uuid}/job_profiles/{jobId}/documents/{documentId}/url";

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("Authorization", $"Custom {sessionKey}");
            request.Headers.Add("x-requester-client", "webapp");
            request.Headers.Add("x-superset-tenant-id", _options.TenantId);
            request.Headers.Add("x-superset-tenant-type", _options.TenantType);

            try
            {
                var response = await client.SendAsync(request);

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning("Failed to fetch document URL for {DocumentId}: {StatusCode}", documentId, response.StatusCode);
                    return null;
                }

                var result = await response.Content.ReadFromJsonAsync<JsonElement>();
                return result.TryGetProperty("url", out var urlProp) ? urlProp.GetString() : null;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error fetching document URL for {DocumentId}", documentId);
                return null;
            }
        }

                private static string EncryptPassword(string password)
        {
            var keyPath = Path.Combine(AppContext.BaseDirectory, "rsa_public_key.txt");
            var fullKey = File.ReadAllText(keyPath).Trim();

            using var rsa = RSA.Create();
            var keyBytes = Convert.FromBase64String(fullKey);
            rsa.ImportSubjectPublicKeyInfo(keyBytes, out _);
            var passwordBytes = Encoding.UTF8.GetBytes(password);
            var encryptedBytes = rsa.Encrypt(passwordBytes, RSAEncryptionPadding.Pkcs1);

            return Convert.ToBase64String(encryptedBytes);
        }
    }
}
