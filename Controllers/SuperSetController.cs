using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    public class SuperSetController : ControllerBase
    {
        private readonly ISuperSetSyncService _syncService;
        private readonly ISuperSetService _superSetService;

        public SuperSetController(
            ISuperSetSyncService syncService,
            ISuperSetService superSetService)
        {
            _syncService = syncService;
            _superSetService = superSetService;
        }

        /// <summary>
        /// Admin endpoint: Manually trigger SuperSet synchronization for jobs and/or notices.
        /// This is the primary sync endpoint. Does NOT run automatically.
        /// </summary>
        /// <param name="request">Specify which types to sync: syncJobs, syncNotices</param>
        /// <returns>Combined sync result with insert/update/fail counts</returns>
        [HttpPost("superset/admin/sync")]
        [ProducesResponseType(typeof(Common.ReturnResponse), 200)]
        [ProducesResponseType(typeof(Common.ReturnResponse), 400)]
        public async Task<ActionResult> AdminSync([FromBody] SuperSetSyncRequest request)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                if (!request.SyncJobs && !request.SyncNotices)
                {
                    response.status = false;
                    response.Message = "At least one of syncJobs or syncNotices must be true";
                    return BadRequest(response);
                }

                var result = await _syncService.SyncAllAsync(request.SyncJobs, request.SyncNotices);
                response.status = result.Success;
                response.Message = result.Message;
                response.Data = result;
                return Ok(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Sync failed: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        [HttpPost("superset/notices/sync")]
        public async Task<ActionResult> SyncNotices()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                var result = await _syncService.SyncNoticesAsync();
                response.status = result.Success;
                response.Message = result.Message;
                response.Data = result;
                return Ok(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Sync failed: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        [HttpPost("superset/jobs/sync")]
        public async Task<ActionResult> SyncJobs()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                var result = await _syncService.SyncJobsAsync();
                response.status = result.Success;
                response.Message = result.Message;
                response.Data = result;
                return Ok(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Sync failed: " + ex.Message;
                return StatusCode(500, response);
            }
        }
    }
}
