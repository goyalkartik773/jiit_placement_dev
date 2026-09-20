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
