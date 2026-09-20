using System.Data;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    public class GmailController : ControllerBase
    {
        private readonly IGmailService _gmailService;
        private readonly DataEntity _dataEntity;
        private readonly ILogger<GmailController> _logger;

        public GmailController(
            IGmailService gmailService,
            DataEntity dataEntity,
            ILogger<GmailController> logger)
        {
            _gmailService = gmailService;
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
    }
}
