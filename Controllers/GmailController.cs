using System.Data;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    [Authorize] // every Gmail admin/placement API requires an admin session;
                // only the two OAuth endpoints below are anonymous
    public class GmailController : ControllerBase
    {
        private readonly IGmailService _gmailService;
        private readonly IPlacementExtractionService _placementExtractor;
        private readonly DataEntity _dataEntity;
        private readonly ILogger<GmailController> _logger;

        public GmailController(
            IGmailService gmailService,
            IPlacementExtractionService placementExtractor,
            DataEntity dataEntity,
            ILogger<GmailController> logger)
        {
            _gmailService = gmailService;
            _placementExtractor = placementExtractor;
            _dataEntity = dataEntity;
            _logger = logger;
        }

        /// <summary>
        /// Primary Admin endpoint: Synchronize Gmail messages from both configured Google Groups.
        /// ONE API call handles: fetch → store → parse → preprocess → classify → extract → validate → persist.
        /// No background service required.
        /// </summary>
        [HttpPost("gmail/admin/sync")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        [ProducesResponseType(typeof(Common.ReturnResponse), 400)]
        public async Task<ActionResult> AdminSync([FromBody] GmailSyncRequest request)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                _logger.LogInformation("Admin Gmail sync requested");

                var result = await _gmailService.SyncAllAsync(request);

                if (!result.Success)
                {
                    response.status = false;
                    response.Message = result.Message;
                    return BadRequest(response);
                }

                response.status = true;
                response.Message = result.Message;
                response.Data = new
                {
                    result.Groups,
                    result.TotalFetched,
                    result.TotalProcessed,
                    result.TotalReviewRequired,
                    result.TotalFailed
                };

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Gmail admin sync failed");
                response.status = false;
                response.Message = "Gmail sync failed: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get Gmail messages with pagination and filtering.
        /// </summary>
        [HttpGet("gmail/admin/messages")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetMessages(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20,
            [FromQuery] string sourceGroup = "",
            [FromQuery] string status = "",
            [FromQuery] string search = "")
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                pageSize = Math.Min(pageSize, 100);

                DataTable dt = _gmailService.GetMessagesAsync(page, pageSize, sourceGroup, status, search)
                    .GetAwaiter().GetResult();

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Gmail messages fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No Gmail messages found";
                    response.Data = null;
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch Gmail messages");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get a single Gmail message with attachments and extraction details.
        /// </summary>
        [HttpGet("gmail/admin/messages/{messageId}")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public async Task<ActionResult> GetMessageDetail(string messageId)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                var result = await _gmailService.GetMessageDetailAsync(messageId);

                if (result != null)
                {
                    response.status = true;
                    response.Message = "Gmail message fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = false;
                    response.Message = "Gmail message not found";
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch Gmail message detail");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get messages in a Gmail thread.
        /// </summary>
        [HttpGet("gmail/admin/threads/{threadId}")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public async Task<ActionResult> GetThreadMessages(string threadId)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                var messages = await _gmailService.GetThreadMessagesAsync(threadId);

                response.status = true;
                response.Message = "Thread messages fetched successfully";
                response.Data = messages;

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch thread messages");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Manually reprocess a single Gmail message. Only for retry/recovery/debugging.
        /// NOT required after normal sync.
        /// </summary>
        [HttpPost("gmail/admin/process/{messageId}")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public async Task<ActionResult> ReprocessMessage(string messageId)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                _logger.LogInformation("Manual reprocessing requested for message {MessageId}", messageId);

                var success = await _gmailService.ReprocessMessageAsync(messageId);

                if (success)
                {
                    response.status = true;
                    response.Message = "Message reprocessed successfully";
                }
                else
                {
                    response.status = false;
                    response.Message = "Failed to reprocess message";
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to reprocess message {MessageId}", messageId);
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Manually process multiple messages by IDs.
        /// </summary>
        [HttpPost("gmail/admin/process")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public async Task<ActionResult> ReprocessMessages([FromBody] List<string> messageIds)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                if (messageIds == null || messageIds.Count == 0)
                {
                    response.status = false;
                    response.Message = "No message IDs provided";
                    return BadRequest(response);
                }

                int processed = 0;
                int failed = 0;

                foreach (var messageId in messageIds)
                {
                    try
                    {
                        var success = await _gmailService.ReprocessMessageAsync(messageId);
                        if (success) processed++;
                        else failed++;
                    }
                    catch
                    {
                        failed++;
                    }
                }

                response.status = true;
                response.Message = $"Reprocessed: {processed} successful, {failed} failed";
                response.Data = new { processed, failed };

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to reprocess messages");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get extraction details for a specific Gmail message.
        /// </summary>
        [HttpGet("gmail/admin/extractions/{messageId}")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetExtraction(string messageId)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataEntity dataEntity = _dataEntity;
                DataTable dt = dataEntity.ExecuteDataTableFN(
                    "fn_api_select_emailextraction_v1",
                    messageId
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Extraction fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = false;
                    response.Message = "No extraction found for this message";
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch extraction for message {MessageId}", messageId);
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get messages requiring manual review (REVIEW_REQUIRED status).
        /// </summary>
        [HttpGet("gmail/admin/review-queue")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetReviewQueue(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                pageSize = Math.Min(pageSize, 100);

                DataEntity dataEntity = _dataEntity;
                DataTable dt = dataEntity.ExecuteDataTableFN(
                    "fn_api_select_reviewqueue_v1",
                    page, pageSize
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Review queue fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No items in review queue";
                    response.Data = null;
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch review queue");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Start Gmail OAuth authorization. Opens Google consent screen in browser.
        /// After granting access, Google redirects to /api/gmail/auth/callback.
        /// </summary>
        [HttpGet("gmail/auth")]
        [AllowAnonymous] // Google redirects the browser here without an admin token
        public ActionResult StartAuth()
        {
            try
            {
                var authUrl = _gmailService.GetAuthorizationUrl();
                return Redirect(authUrl);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to generate auth URL");
                return BadRequest(new { error = ex.Message });
            }
        }

        /// <summary>
        /// OAuth callback endpoint. Google redirects here after user grants access.
        /// Exchanges the code for tokens and saves them.
        /// </summary>
        [HttpGet("gmail/auth/callback")]
        [AllowAnonymous] // Google redirects the browser here without an admin token
        public async Task<ActionResult> AuthCallback(
            [FromQuery] string? code,
            [FromQuery] string? error)
        {
            if (!string.IsNullOrEmpty(error))
            {
                return Content($@"
                    <html><body style='font-family:Arial,sans-serif;text-align:center;padding:50px'>
                    <h2 style='color:red'>Authorization Failed</h2>
                    <p>Error: {error}</p>
                    <p><a href='/api/gmail/auth'>Try Again</a></p>
                    </body></html>", "text/html");
            }

            if (string.IsNullOrEmpty(code))
            {
                return Content(@"
                    <html><body style='font-family:Arial,sans-serif;text-align:center;padding:50px'>
                    <h2 style='color:red'>Missing Authorization Code</h2>
                    <p><a href='/api/gmail/auth'>Try Again</a></p>
                    </body></html>", "text/html");
            }

            try
            {
                await _gmailService.ExchangeCodeAsync(code);

                return Content(@"
                    <html><body style='font-family:Arial,sans-serif;text-align:center;padding:50px'>
                    <h2 style='color:green'>&#10004; Gmail Authorized Successfully!</h2>
                    <p>You can now use the Gmail sync API.</p>
                    <p><a href='/swagger'>Go to Swagger</a></p>
                    </body></html>", "text/html");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to exchange OAuth code");
                return Content($@"
                    <html><body style='font-family:Arial,sans-serif;text-align:center;padding:50px'>
                    <h2 style='color:red'>Token Exchange Failed</h2>
                    <p>{ex.Message}</p>
                    <p><a href='/api/gmail/auth'>Try Again</a></p>
                    </body></html>", "text/html");
            }
        }

        /// <summary>
        /// Full sync: Fetch ALL unfetched messages from both groups, process them, and extract placements.
        /// This is the comprehensive sync that covers ALL messages in the groups.
        /// </summary>
        [HttpPost("gmail/admin/full-sync")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public async Task<ActionResult> FullSync(
            [FromQuery] int maxPerGroup = 500,
            [FromQuery] bool extractPlacements = true)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                _logger.LogInformation("Full Gmail sync requested - MaxPerGroup: {Max}, ExtractPlacements: {Extract}",
                    maxPerGroup, extractPlacements);

                // Step 1: Fetch ALL messages from both groups (no date filter)
                var syncRequest = new GmailSyncRequest
                {
                    MaxResults = maxPerGroup,
                    Query = "" // No filter - get everything
                };
                var syncResult = await _gmailService.SyncAllAsync(syncRequest);

                var placementResults = new List<PlacementSyncResult>();

                // Step 2: Extract placements from processed messages
                if (extractPlacements)
                {
                    // Get all processed messages that haven't been placement-extracted yet
                    DataTable unprocessedDt = _dataEntity.ExecuteDataTableFN(
                        "fn_api_select_gmailmessages_v1", 1, 10000, "", "PROCESSED", "");

                    if (unprocessedDt.Rows.Count > 0)
                    {
                        string unprocessedJson = unprocessedDt.Rows[0][0].ToString() ?? "{}";
                        var unprocessedResult = Common.ParseJson(unprocessedJson);

                        if (unprocessedResult.TryGetProperty("items", out var itemsArray))
                        {
                            foreach (var msgElement in itemsArray.EnumerateArray())
                            {
                                try
                                {
                                    var messageUuid = msgElement.TryGetProperty("id", out var idEl) ? idEl.GetString() ?? "" : "";
                                    var gmailMessageId = msgElement.TryGetProperty("gmailmessageid", out var midEl) ? midEl.GetString() ?? "" : "";
                                    var subject = msgElement.TryGetProperty("subject", out var subjEl) ? subjEl.GetString() ?? "" : "";
                                    var bodyText = msgElement.TryGetProperty("bodytext", out var bodyEl) ? bodyEl.GetString() ?? "" : "";
                                    var sourceGroup = msgElement.TryGetProperty("sourcegroup", out var sgEl) ? sgEl.GetString() ?? "" : "";
                                    var sourceGroupEmail = msgElement.TryGetProperty("sourcegroupemail", out var sgeEl) ? sgeEl.GetString() ?? "" : "";

                                    // Check if placements already extracted for this message
                                    bool alreadyExtracted = false;
                                    DataTable existingPlacements = _dataEntity.ExecuteDataTableFN(
                                        "fn_api_select_studentplacements_v001", 1, 100, gmailMessageId, "", "", "", "");
                                    if (existingPlacements.Rows.Count > 0)
                                    {
                                        string epJson = existingPlacements.Rows[0][0].ToString() ?? "{}";
                                        var epResult = Common.ParseJson(epJson);
                                        if (epResult.TryGetProperty("total", out var totalEl) && totalEl.GetInt32() > 0)
                                            alreadyExtracted = true;
                                    }

                                    if (alreadyExtracted) continue;

                                    // Extract placements from this message
                                    var placements = await _placementExtractor.ExtractPlacementsAsync(
                                        bodyText, subject);

                                    foreach (var placement in placements)
                                    {
                                        // Try to match company to existing job
                                        string matchedJobUuid = await FindMatchingJobAsync(
                                            placement.CompanyName, placement.JobProfile);

                                        // If no match found, create a new job
                                        if (string.IsNullOrEmpty(matchedJobUuid) && !string.IsNullOrEmpty(placement.CompanyName))
                                        {
                                            matchedJobUuid = await CreateJobFromPlacementAsync(placement);
                                        }

                                        // Save the student placement
                                        DataTable saveDt = _dataEntity.ExecuteDataTableFNParam(
                                            "fn_api_insert_studentplacement_v001",
                                            ("_gmailmessageid", (object)gmailMessageId),
                                            ("_gmailmessageuuid", (object)messageUuid),
                                            ("_sourcegroup", (object)sourceGroup),
                                            ("_sourcegroupemail", (object)sourceGroupEmail),
                                            ("_studentname", (object)placement.StudentName),
                                            ("_studentemail", (object)placement.StudentEmail),
                                            ("_companyname", (object)placement.CompanyName),
                                            ("_jobprofile", (object)placement.JobProfile),
                                            ("_package", (object)placement.Package),
                                            ("_location", (object)placement.Location),
                                            ("_batch", (object)placement.Batch),
                                            ("_placementtype", (object)placement.PlacementType),
                                            ("_jobuuid", (object)matchedJobUuid),
                                            ("_notes", (object)$"Confidence: {placement.Confidence:F2}")
                                        );

                                        if (saveDt.Rows.Count > 0)
                                        {
                                            string saveJson = saveDt.Rows[0][0].ToString() ?? "";
                                            var saveResult = Common.ParseJson(saveJson);
                                            var saveStatus = saveResult.TryGetProperty("status", out var stEl) ? stEl.GetString() : "";
                                            if (saveStatus == "SUCCESS")
                                            {
                                                placementResults.Add(new PlacementSyncResult
                                                {
                                                    StudentName = placement.StudentName,
                                                    CompanyName = placement.CompanyName,
                                                    JobProfile = placement.JobProfile,
                                                    MatchedJobUuid = matchedJobUuid,
                                                    Confidence = placement.Confidence
                                                });
                                            }
                                        }
                                    }
                                }
                                catch (Exception ex)
                                {
                                    _logger.LogError(ex, "Failed to extract placements from message");
                                }
                            }
                        }
                    }
                }

                response.status = true;
                response.Message = "Full sync and placement extraction completed.";
                response.Data = new
                {
                    SyncResult = syncResult,
                    PlacementsExtracted = placementResults.Count,
                    Placements = placementResults
                };

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Full sync failed");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get all student placements with optional filters.
        /// </summary>
        [HttpGet("gmail/placements")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetPlacements(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 50,
            [FromQuery] string company = "",
            [FromQuery] string student = "",
            [FromQuery] string sourceGroup = "",
            [FromQuery] string batch = "",
            [FromQuery] string status = "")
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                pageSize = Math.Min(pageSize, 200);
                DataEntity dataEntity = _dataEntity;
                DataTable dt = dataEntity.ExecuteDataTableFN(
                    "fn_api_select_studentplacements_v001",
                    page, pageSize, company, student, sourceGroup, batch, status
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Placements fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No placements found";
                    response.Data = null;
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch placements");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get placement summary by company.
        /// </summary>
        [HttpGet("gmail/placements/summary")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetPlacementSummary()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataEntity dataEntity = _dataEntity;
                DataTable dt = dataEntity.ExecuteDataTableFN(
                    "fn_api_select_placementsummary_v001"
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Placement summary fetched";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No summary available";
                    response.Data = null;
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch placement summary");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Get overall placement statistics.
        /// </summary>
        [HttpGet("gmail/placements/stats")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        public ActionResult GetPlacementStats()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataEntity dataEntity = _dataEntity;
                DataTable dt = dataEntity.ExecuteDataTableFN(
                    "fn_api_select_placementstats_v001"
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Placement stats fetched";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No stats available";
                    response.Data = null;
                }

                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to fetch placement stats");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        // ---- Helper methods ----

        private async Task<string> FindMatchingJobAsync(string companyName, string jobProfile)
        {
            if (string.IsNullOrWhiteSpace(companyName)) return "";

            try
            {
                // Try exact company match first
                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_jobs_v1", 1, 100, companyName, "");

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString() ?? "{}";
                    var result = Common.ParseJson(json);
                    if (result.TryGetProperty("items", out var items))
                    {
                        foreach (var item in items.EnumerateArray())
                        {
                            if (item.TryGetProperty("id", out var idEl))
                            {
                                return idEl.GetString() ?? "";
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to find matching job for {Company}", companyName);
            }

            return "";
        }

        private async Task<string> CreateJobFromPlacementAsync(PlacementInfo placement)
        {
            try
            {
                // Create a job entry for a company found in congratulations but not in SuperSet
                var jobId = Guid.NewGuid().ToString();
                var now = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_post_job_v001",
                    jobId,
                    $"CONGRATULATIONS-{Guid.NewGuid().ToString()[..8]}",
                    placement.CompanyName,
                    placement.JobProfile ?? "Placed",
                    "PLACEMENT",
                    "PLACEMENT",
                    $"Auto-created from congratulations email. Student: {placement.StudentName}",
                    now,
                    now,
                    placement.Location ?? "",
                    decimal.TryParse(placement.Package, out var pkg) ? pkg : 0,
                    placement.Package ?? "",
                    $"Placed via {placement.CompanyName}",
                    placement.PlacementType ?? "FULL_TIME"
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString() ?? "";
                    var result = Common.ParseJson(json);
                    if (result.TryGetProperty("status", out var stEl) && stEl.GetString() == "SUCCESS")
                    {
                        _logger.LogInformation("Created new job for {Company}: {Profile}", placement.CompanyName, placement.JobProfile);
                        return result.TryGetProperty("id", out var idEl) ? idEl.GetString() ?? "" : "";
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to create job for {Company}", placement.CompanyName);
            }

            return "";
        }
    }

    public class PlacementSyncResult
    {
        public string StudentName { get; set; } = "";
        public string CompanyName { get; set; } = "";
        public string JobProfile { get; set; } = "";
        public string MatchedJobUuid { get; set; } = "";
        public double Confidence { get; set; }
    }
}
