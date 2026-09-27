using System.Data;
using System.Security.Cryptography;
using System.Text;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Controllers
{
    /// <summary>
    /// Admin APIs: JWT login/logout plus the job-sync workflow
    /// (count → start → status/result) and the delete-all-jobs cleanup.
    /// Every action except login requires a valid, non-revoked admin JWT.
    /// </summary>
    [ApiController]
    [Route("api/admin")]
    public class AdminController : ControllerBase
    {
        private readonly AdminOptions _adminOptions;
        private readonly IAdminTokenService _tokenService;
        private readonly IAdminTokenRevocationStore _revocationStore;
        private readonly IAdminSyncCoordinator _syncCoordinator;
        private readonly IJobCleanupService _cleanupService;
        private readonly DataEntity _dataEntity;
        private readonly ILogger<AdminController> _logger;

        public AdminController(
            IOptions<AdminOptions> adminOptions,
            IAdminTokenService tokenService,
            IAdminTokenRevocationStore revocationStore,
            IAdminSyncCoordinator syncCoordinator,
            IJobCleanupService cleanupService,
            DataEntity dataEntity,
            ILogger<AdminController> logger)
        {
            _adminOptions = adminOptions.Value;
            _tokenService = tokenService;
            _revocationStore = revocationStore;
            _syncCoordinator = syncCoordinator;
            _cleanupService = cleanupService;
            _dataEntity = dataEntity;
            _logger = logger;
        }

        /// <summary>POST /api/admin/login — exchanges credentials for a signed JWT.</summary>
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

            var (token, _) = _tokenService.Issue(username);
            _logger.LogInformation("Admin login successful for {Username}", username);
            return Ok(new { success = true, message = "Login successful", token });
        }

        /// <summary>POST /api/admin/logout — revokes the presented token's session id.</summary>
        [HttpPost("logout")]
        [Authorize]
        public ActionResult Logout()
        {
            var jti = User.FindFirst("jti")?.Value;
            if (!string.IsNullOrEmpty(jti))
            {
                var expiresAt = DateTimeOffset.UtcNow
                    .AddHours(Math.Max(1, _adminOptions.TokenExpirationHours));
                _revocationStore.Revoke(jti, expiresAt);
            }

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
                var (started, status, busyOperation) = await _syncCoordinator.TryStartAsync();

                if (!started)
                {
                    return Conflict(new
                    {
                        success = false,
                        message = busyOperation == "delete"
                            ? "Job deletion is already running"
                            : "Job synchronization is already running",
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

        /// <summary>
        /// DELETE /api/admin/jobs — removes every job record in one transaction
        /// and then deletes the documents those records owned from disk.
        /// Rejects with 409 while a synchronization (or another deletion) runs.
        /// </summary>
        /// <summary>
        /// POST /api/admin/jobs/sync-offer-students - admin-triggered matching of the
        /// offered students (extracted from congratulation emails) onto the Jobs rows
        /// that already exist in the system.
        ///
        /// Rules: a student is mapped only when his/her company exists in the Jobs
        /// table (unknown companies are reported in companiesSkipped and ignored -
        /// never created, never guessed). The mapping is idempotent thanks to the
        /// UNIQUE (job_id, student_roll_no) constraint, so re-running the sync only
        /// ever adds genuinely new mappings.
        /// </summary>
        [HttpPost("jobs/sync-offer-students")]
        [Authorize]
        public ActionResult SyncOfferStudents()
        {
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_sync_offer_students_v1");
                if (dt.Rows.Count == 0)
                {
                    return StatusCode(500, new
                    {
                        success = false,
                        message = "Offer-student sync produced no result"
                    });
                }

                var result = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!PlacementController.IsSuccess(result, out string fnMessage))
                {
                    return StatusCode(500, new
                    {
                        success = false,
                        message = string.IsNullOrEmpty(fnMessage) ? "Offer-student sync failed" : fnMessage
                    });
                }

                _logger.LogInformation(
                    "Offer-student sync: {Inserted} mappings inserted, {Duplicates} duplicates skipped, {CompaniesSkipped} companies skipped",
                    PlacementController.GetInt32(result, "mappingsInserted"),
                    PlacementController.GetInt32(result, "duplicatesSkipped"),
                    PlacementController.GetInt32(result, "companiesSkipped"));

                return Ok(new
                {
                    success = true,
                    message = "Offer-student sync completed",
                    jobsTotal = PlacementController.GetInt32(result, "jobsTotal"),
                    jobsMatched = PlacementController.GetInt32(result, "jobsMatched"),
                    jobsWithoutPlacements = PlacementController.GetInt32(result, "jobsWithoutPlacements"),
                    studentsConsidered = PlacementController.GetInt32(result, "studentsConsidered"),
                    studentsMapped = PlacementController.GetInt32(result, "studentsMapped"),
                    mappingsInserted = PlacementController.GetInt32(result, "mappingsInserted"),
                    duplicatesSkipped = PlacementController.GetInt32(result, "duplicatesSkipped"),
                    companiesMatched = PlacementController.GetInt32(result, "companiesMatched"),
                    companiesSkipped = PlacementController.GetInt32(result, "companiesSkipped"),
                    totalMappings = PlacementController.GetInt32(result, "totalMappings"),
                    lastRunAt = PlacementController.GetProperty(result, "lastRunAt")
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Offer-student sync failed");
                return StatusCode(500, new { success = false, message = "Offer-student sync failed: " + ex.Message });
            }
        }

        /// <summary>
        /// GET /api/admin/jobs/{jobId}/placed-students - who got placed against this
        /// job (job id or Superset job identifier), with role and compensation.
        /// </summary>
        [HttpGet("jobs/{jobId}/placed-students")]
        [Authorize]
        public ActionResult GetPlacedStudents(string jobId)
        {
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFNParam(
                    "fn_api_select_placed_students_v1", ("jobid", jobId));

                if (dt.Rows.Count == 0)
                    return NotFound(new { success = false, message = "Job not found" });

                var result = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!PlacementController.IsSuccess(result, out string fnMessage))
                {
                    return NotFound(new
                    {
                        success = false,
                        message = string.IsNullOrEmpty(fnMessage) ? "Job not found" : fnMessage
                    });
                }

                return Ok(new
                {
                    success = true,
                    message = "Placed students fetched successfully",
                    job = PlacementController.GetProperty(result, "job"),
                    placedCount = PlacementController.GetInt32(result, "placedCount"),
                    students = PlacementController.GetProperty(result, "students")
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load placed students for job {JobId}", jobId);
                return StatusCode(500, new { success = false, message = "Error: " + ex.Message });
            }
        }

        [HttpDelete("jobs")]
        [Authorize]
        public async Task<ActionResult> DeleteAllJobs()
        {
            var (allowed, busyOperation) = _syncCoordinator.TryBeginDelete();
            if (!allowed)
            {
                return Conflict(new
                {
                    success = false,
                    message = busyOperation == "sync"
                        ? "Job synchronization is already running"
                        : "Job deletion is already running"
                });
            }

            try
            {
                var result = await _cleanupService.DeleteAllJobsAsync();
                if (!result.Success)
                {
                    _logger.LogError("Job deletion failed: {Message}", result.Message);
                    return StatusCode(500, new { success = false, message = result.Message });
                }

                _logger.LogInformation(
                    "Deleted {Jobs} jobs, {Rows} document rows, {Files} files ({Missing} already absent, {Failed} failed) in {Elapsed} ms",
                    result.JobsDeleted, result.DocumentRowsDeleted, result.FilesDeleted,
                    result.FilesMissing, result.FilesFailed, result.DurationMs);

                return Ok(new
                {
                    success = true,
                    message = $"Deleted {result.JobsDeleted} jobs and {result.FilesDeleted} documents",
                    jobsDeleted = result.JobsDeleted,
                    documentRowsDeleted = result.DocumentRowsDeleted,
                    filesDeleted = result.FilesDeleted,
                    filesMissing = result.FilesMissing,
                    filesFailed = result.FilesFailed,
                    durationMs = result.DurationMs,
                    phases = result.Phases.Select(p => new { phase = p.Phase, durationMs = p.DurationMs })
                });
            }
            finally
            {
                _syncCoordinator.EndDelete();
            }
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
    }
}
