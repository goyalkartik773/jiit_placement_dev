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
        private readonly IAdminScriptRunner _scriptRunner;
        private readonly IAdminDeleteScripts _deleteScripts;
        private readonly DataEntity _dataEntity;
        private readonly ILogger<AdminController> _logger;

        public AdminController(
            IOptions<AdminOptions> adminOptions,
            IAdminTokenService tokenService,
            IAdminTokenRevocationStore revocationStore,
            IAdminSyncCoordinator syncCoordinator,
            IJobCleanupService cleanupService,
            IAdminScriptRunner scriptRunner,
            IAdminDeleteScripts deleteScripts,
            DataEntity dataEntity,
            ILogger<AdminController> logger)
        {
            _adminOptions = adminOptions.Value;
            _tokenService = tokenService;
            _revocationStore = revocationStore;
            _syncCoordinator = syncCoordinator;
            _cleanupService = cleanupService;
            _scriptRunner = scriptRunner;
            _deleteScripts = deleteScripts;
            _dataEntity = dataEntity;
            _logger = logger;
        }

        /// <summary>User behind the presented admin JWT (for the history entries).</summary>
        private string Username => User.Identity?.Name ?? "unknown";

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
                TryLog("login", "failed", username.Length > 100 ? username[..100] : username,
                    "Login rejected — invalid credentials", null);
                return Unauthorized(new { success = false, message = "Invalid credentials" });
            }

            var (token, expiresAt) = _tokenService.Issue(username);
            _logger.LogInformation("Admin login successful for {Username}", username);
            TryLog("login", "completed", username, "Admin login successful",
                new { expiresAt, tokenHours = Math.Max(1, _adminOptions.TokenExpirationHours) });
            return Ok(new { success = true, message = "Login successful", token, username, expiresAt });
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
            TryLog("logout", "completed", User.Identity?.Name ?? "unknown", "Admin logged out", null);
            return Ok(new { success = true, message = "Logged out successfully" });
        }

        /// <summary>History write that never breaks the request it belongs to.</summary>
        private void TryLog(string script, string status, string username, string message, object? counters)
        {
            try
            {
                AdminScriptRunLog.Log(_dataEntity, script, status, username, message, counters, null, 0);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not record {Script} in the history", script);
            }
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
                var (started, status, busyOperation) = await _syncCoordinator.TryStartAsync(Username);

                if (!started)
                {
                    return Conflict(new
                    {
                        success = false,
                        message = DescribeBusy(busyOperation) + " is already running",
                        busyScript = busyOperation,
                        syncId = status.SyncId,
                        status = status.Status
                    });
                }

                _logger.LogInformation("Admin triggered job synchronization {SyncId}", status.SyncId);
                return Ok(new
                {
                    success = true,
                    message = "Job synchronization started",
                    script = "jobs_sync",
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
        /// <c>output</c> holds the console lines the run produced.
        /// </summary>
        [HttpGet("jobs/sync/status")]
        [Authorize]
        public ActionResult GetSyncStatus()
        {
            var s = _syncCoordinator.GetStatus();
            return Ok(new
            {
                success = true,
                script = "jobs_sync",
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
                error = s.Error,
                output = s.Output ?? new List<ScriptOutputLine>()
            });
        }

        /// <summary>
        /// POST /api/admin/gmail/sync — console-script style mailbox sync: fetches the
        /// messages of every configured source group from the Gmail API and stores them
        /// (plus their attachments and extractions) in the database. Runs in the
        /// background; GET .../gmail/sync/status streams the lines it prints.
        /// Rejects with 409 while any other admin script holds the single slot.
        /// </summary>
        [HttpPost("gmail/sync")]
        [Authorize]
        public async Task<ActionResult> StartGmailSync([FromBody] GmailSyncRequest? request)
        {
            try
            {
                var syncRequest = request ?? new GmailSyncRequest();
                if (syncRequest.MaxResults <= 0) syncRequest.MaxResults = 500;

                var (started, busyScript) = await _scriptRunner.StartGmailSyncAsync(syncRequest, Username);
                if (!started)
                {
                    return Conflict(new
                    {
                        success = false,
                        message = DescribeBusy(busyScript) + " is already running",
                        script = "gmail_sync",
                        busyScript
                    });
                }

                _logger.LogInformation("Admin triggered the mailbox sync");
                return Ok(new
                {
                    success = true,
                    message = "Mailbox sync started",
                    script = "gmail_sync",
                    status = "started"
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to start the mailbox sync");
                return StatusCode(500, new { success = false, message = "Failed to start the mailbox sync: " + ex.Message });
            }
        }

        /// <summary>GET /api/admin/gmail/sync/status — live console output of the mailbox sync.</summary>
        [HttpGet("gmail/sync/status")]
        [Authorize]
        public ActionResult GetGmailSyncStatus()
            => Ok(ToScriptStatus(_scriptRunner.GetStatus(AdminScriptRunner.GmailScript)));

        /// <summary>
        /// POST /api/admin/jobs/sync-offer-students — console-script style job↔student
        /// sync. The matching itself is still the same idempotent database function; this
        /// endpoint just runs it in the background with live console output and a real
        /// "what changed" delta. Rejects with 409 while another script is running.
        /// </summary>
        [HttpPost("jobs/sync-offer-students")]
        [Authorize]
        public async Task<ActionResult> SyncOfferStudents()
        {
            try
            {
                var (started, busyScript) = await _scriptRunner.StartOfferSyncAsync(Username);
                if (!started)
                {
                    return Conflict(new
                    {
                        success = false,
                        message = DescribeBusy(busyScript) + " is already running",
                        script = "offer_sync",
                        busyScript
                    });
                }

                _logger.LogInformation("Admin triggered the job to student sync");
                return Ok(new
                {
                    success = true,
                    message = "Job to student sync started",
                    script = "offer_sync",
                    status = "started"
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to start the offer sync");
                return StatusCode(500, new { success = false, message = "Failed to start the job to student sync: " + ex.Message });
            }
        }

        /// <summary>
        /// GET /api/admin/jobs/sync-offer-students/status — live console output, final
        /// stats and the delta of the run (which companies gained mappings).
        /// </summary>
        [HttpGet("jobs/sync-offer-students/status")]
        [Authorize]
        public ActionResult GetOfferSyncStatus()
            => Ok(ToScriptStatus(_scriptRunner.GetStatus(AdminScriptRunner.OfferScript)));

        /// <summary>
        /// DELETE /api/admin/gmail — console-script style wipe of the synced mailbox
        /// (gmailmessages + gmailattachments + emailextractions). The parsed email
        /// corpus and the placement mapping are untouched by design.
        /// </summary>
        [HttpDelete("gmail")]
        [Authorize]
        public async Task<ActionResult> DeleteGmail()
        {
            var result = await _deleteScripts.DeleteGmailAsync(Username);
            if (!result.Success)
            {
                if (result.Message == "Another admin script is running")
                {
                    return Conflict(new
                    {
                        success = false,
                        message = DescribeBusy(result.Error) + " is already running",
                        script = result.Script,
                        busyScript = result.Error
                    });
                }

                _logger.LogError("Mailbox delete failed: {Message}", result.Message);
                return StatusCode(500, new
                {
                    success = false,
                    script = result.Script,
                    message = result.Message,
                    error = result.Error,
                    output = result.Output
                });
            }

            return Ok(new
            {
                success = true,
                script = result.Script,
                message = result.Message,
                counters = result.Counters,
                phases = result.Phases.Select(p => new { phase = p.Phase, durationMs = p.DurationMs }),
                durationMs = result.DurationMs,
                output = result.Output
            });
        }

        /// <summary>
        /// DELETE /api/admin/jobs/placed-students — console-script style wipe of every
        /// job↔student mapping. Jobs, offers and offer_students are untouched; the
        /// job↔student sync rebuilds the mapping from scratch afterwards.
        /// </summary>
        [HttpDelete("jobs/placed-students")]
        [Authorize]
        public async Task<ActionResult> DeletePlacedStudents()
        {
            var result = await _deleteScripts.DeleteMappingsAsync(Username);
            if (!result.Success)
            {
                if (result.Message == "Another admin script is running")
                {
                    return Conflict(new
                    {
                        success = false,
                        message = DescribeBusy(result.Error) + " is already running",
                        script = result.Script,
                        busyScript = result.Error
                    });
                }

                _logger.LogError("Mapping delete failed: {Message}", result.Message);
                return StatusCode(500, new
                {
                    success = false,
                    script = result.Script,
                    message = result.Message,
                    error = result.Error,
                    output = result.Output
                });
            }

            return Ok(new
            {
                success = true,
                script = result.Script,
                message = result.Message,
                counters = result.Counters,
                phases = result.Phases.Select(p => new { phase = p.Phase, durationMs = p.DurationMs }),
                durationMs = result.DurationMs,
                output = result.Output
            });
        }

        /// <summary>
        /// GET /api/admin/activity — newest-first history of every admin action
        /// (logins, syncs, deletes) with the console output each run produced, so the
        /// timeline and the console replay come from the database.
        /// </summary>
        [HttpGet("activity")]
        [Authorize]
        public ActionResult GetActivity(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 12,
            [FromQuery] string? script = null)
        {
            try
            {
                page = page < 1 ? 1 : page;
                pageSize = pageSize < 1 ? 12 : Math.Min(pageSize, 100);

                DataTable dt = _dataEntity.ExecuteDataTableFNParam(
                    "fn_api_select_script_runs_v1",
                    ("page", page),
                    ("pagesize", pageSize),
                    ("script", string.IsNullOrWhiteSpace(script) ? "" : script.Trim()));

                if (dt.Rows.Count == 0)
                    return StatusCode(500, new { success = false, message = "History query failed" });

                return Ok(new
                {
                    success = true,
                    message = "Activity fetched successfully",
                    data = Common.ParseJson(dt.Rows[0][0].ToString() ?? "")
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load the admin activity history");
                return StatusCode(500, new { success = false, message = "Error: " + ex.Message });
            }
        }

        /// <summary>
        /// GET /api/admin/overview — live counts, accuracy ratios, integrity checks,
        /// session info (last login) and the last run of every script. Every value is
        /// counted from a table; nothing here is cached or estimated.
        /// </summary>
        [HttpGet("overview")]
        [Authorize]
        public ActionResult GetOverview()
        {
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_admin_overview_v1");
                if (dt.Rows.Count == 0)
                    return StatusCode(500, new { success = false, message = "Overview query failed" });

                return Ok(new
                {
                    success = true,
                    message = "Overview fetched successfully",
                    data = Common.ParseJson(dt.Rows[0][0].ToString() ?? "")
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load the admin overview");
                return StatusCode(500, new { success = false, message = "Error: " + ex.Message });
            }
        }

        /// <summary>Uniform status payload for every console script.</summary>
        private static object ToScriptStatus(AdminScriptStatus s) => new
        {
            success = true,
            script = s.Script,
            runId = s.RunId,
            status = s.Status,
            message = s.Message,
            username = s.Username,
            startedAt = s.StartedAt,
            finishedAt = s.FinishedAt,
            durationMs = s.DurationMs,
            progress = s.Progress,
            counters = s.Counters,
            output = s.Output,
            error = s.Error
        };

        /// <summary>Human label of the operation currently holding the script slot.</summary>
        private static string DescribeBusy(string? operation) => operation switch
        {
            "sync" => "Superset job sync",
            "jobs_sync" => "Superset job sync",
            "gmail_sync" => "Mailbox sync",
            "offer_sync" => "Job to student sync",
            "delete" => "Job deletion",
            "delete_jobs" => "Job deletion",
            "delete_gmail" => "Mailbox delete",
            "delete_mappings" => "Mapping delete",
            null => "Another admin script",
            _ => operation
        };

        /// <summary>
        /// DELETE /api/admin/jobs — removes every job record in one transaction
        /// and then deletes the documents those records owned from disk.
        /// Rejects with 409 while a synchronization (or another deletion) runs.
        /// </summary>

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

                var result = Common.ParseJson(dt.Rows[0][0].ToString() ?? "");
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
            var (allowed, busyOperation) = _syncCoordinator.TryBeginScript("delete_jobs");
            if (!allowed)
            {
                return Conflict(new
                {
                    success = false,
                    message = DescribeBusy(busyOperation) + " is already running",
                    busyScript = busyOperation
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

                TryLog("delete_jobs", "completed", Username,
                    $"Deleted {result.JobsDeleted} jobs and {result.FilesDeleted} documents",
                    new
                    {
                        jobsDeleted = result.JobsDeleted,
                        documentRowsDeleted = result.DocumentRowsDeleted,
                        filesDeleted = result.FilesDeleted,
                        filesMissing = result.FilesMissing,
                        filesFailed = result.FilesFailed
                    });

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
                _syncCoordinator.EndScript();
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
