using System.Security.Cryptography;
using System.Text;
using JIITPlacement.Models;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using Microsoft.Net.Http.Headers;

namespace JIITPlacement.Controllers
{
    /// <summary>
    /// Admin APIs: session login/logout plus the job-sync workflow
    /// (count → start → status/result). Every action except login requires
    /// a valid admin session token.
    /// </summary>
    [ApiController]
    [Route("api/admin")]
    public class AdminController : ControllerBase
    {
        private const string BearerPrefix = "Bearer ";

        private readonly AdminOptions _adminOptions;
        private readonly IAdminSessionStore _sessionStore;
        private readonly IAdminSyncCoordinator _syncCoordinator;
        private readonly ILogger<AdminController> _logger;

        public AdminController(
            IOptions<AdminOptions> adminOptions,
            IAdminSessionStore sessionStore,
            IAdminSyncCoordinator syncCoordinator,
            ILogger<AdminController> logger)
        {
            _adminOptions = adminOptions.Value;
            _sessionStore = sessionStore;
            _syncCoordinator = syncCoordinator;
            _logger = logger;
        }

        /// <summary>POST /api/admin/login — exchanges credentials for a bearer token.</summary>
        [HttpPost("login")]
        [AllowAnonymous]
        public ActionResult Login([FromBody] AdminLoginRequest? request)
        {
            var username = request?.Username?.Trim() ?? string.Empty;
            var password = request?.Password ?? string.Empty;

            if (!IsValidCredential(username, password))
            {
                _logger.LogWarning("Admin login rejected for user {Username}", username);
                return Unauthorized(new { success = false, message = "Invalid credentials" });
            }

            var token = _sessionStore.CreateToken(username);
            _logger.LogInformation("Admin login successful for {Username}", username);
            return Ok(new { success = true, message = "Login successful", token });
        }

        /// <summary>POST /api/admin/logout — invalidates the presented token immediately.</summary>
        [HttpPost("logout")]
        [Authorize]
        public ActionResult Logout()
        {
            var token = GetBearerToken();
            if (token != null)
                _sessionStore.RevokeToken(token);

            _logger.LogInformation("Admin logout for {Username}", User.Identity?.Name ?? "unknown");
            return Ok(new { success = true, message = "Logged out successfully" });
        }

        /// <summary>GET /api/admin/jobs/count — live count from the jobs table.</summary>
        [HttpGet("jobs/count")]
        [Authorize]
        public async Task<ActionResult> GetJobsCount()
        {
            try
            {
                var total = await _syncCoordinator.GetTotalJobsAsync();
                if (total is null)
                    return StatusCode(500, new { success = false, message = "Failed to count jobs" });

                return Ok(new { success = true, totalJobs = total.Value });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to count jobs");
                return StatusCode(500, new { success = false, message = "Failed to count jobs: " + ex.Message });
            }
        }

        /// <summary>POST /api/admin/jobs/sync — starts the background sync (single run only).</summary>
        [HttpPost("jobs/sync")]
        [Authorize]
        public async Task<ActionResult> StartSync()
        {
            try
            {
                var (started, status) = await _syncCoordinator.TryStartAsync();

                if (!started)
                {
                    return Conflict(new
                    {
                        success = false,
                        message = "Job synchronization is already running",
                        syncId = status.SyncId,
                        status = status.Status
                    });
                }

                _logger.LogInformation("Admin triggered job synchronization {SyncId}", status.SyncId);
                return Ok(new
                {
                    success = true,
                    message = "Job synchronization started",
                    syncId = status.SyncId,
                    status = "started"
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to start job synchronization");
                return StatusCode(500, new { success = false, message = "Failed to start synchronization: " + ex.Message });
            }
        }

        /// <summary>
        /// GET /api/admin/jobs/sync/status — live progress while running and the
        /// final result when completed. Counters stay omitted until they are real.
        /// </summary>
        [HttpGet("jobs/sync/status")]
        [Authorize]
        public ActionResult GetSyncStatus()
        {
            var s = _syncCoordinator.GetStatus();
            return Ok(new
            {
                success = true,
                status = s.Status,
                syncId = s.SyncId,
                message = s.Message,
                totalJobsBeforeSync = s.TotalJobsBeforeSync,
                totalJobsAfterSync = s.TotalJobsAfterSync,
                jobsTotal = s.JobsTotal,
                jobsProcessed = s.JobsProcessed,
                newJobs = s.NewJobs,
                documentsDownloaded = s.DocumentsDownloaded,
                documentsFailed = s.DocumentsFailed,
                failedJobs = s.FailedJobs,
                progress = s.Progress,
                startedAt = s.StartedAt,
                finishedAt = s.FinishedAt,
                error = s.Error
            });
        }

        private bool IsValidCredential(string username, string password)
        {
            if (string.IsNullOrEmpty(_adminOptions.Username) || string.IsNullOrEmpty(_adminOptions.Password))
            {
                _logger.LogError("Admin credentials are not configured (Admin:Username / Admin:Password)");
                return false;
            }

            // Both comparisons run — no short-circuit timing signal.
            var valid = FixedTimeEquals(username, _adminOptions.Username);
            valid &= FixedTimeEquals(password, _adminOptions.Password);
            return valid;
        }

        private static bool FixedTimeEquals(string value, string expected)
        {
            var a = Encoding.UTF8.GetBytes(value);
            var b = Encoding.UTF8.GetBytes(expected);
            return a.Length == b.Length && CryptographicOperations.FixedTimeEquals(a, b);
        }

        private string? GetBearerToken()
        {
            if (!Request.Headers.TryGetValue(HeaderNames.Authorization, out var values))
                return null;

            var header = values.ToString();
            if (!header.StartsWith(BearerPrefix, StringComparison.OrdinalIgnoreCase))
                return null;

            var token = header[BearerPrefix.Length..].Trim();
            return string.IsNullOrEmpty(token) ? null : token;
        }
    }
}
