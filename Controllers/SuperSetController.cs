using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers;

[ApiController]
[Route("api/superset")]
public class SuperSetController : ControllerBase
{
    private readonly ISuperSetSyncService _syncService;
    private readonly ILogger<SuperSetController> _logger;

    public SuperSetController(
        ISuperSetSyncService syncService,
        ILogger<SuperSetController> logger)
    {
        _syncService = syncService;
        _logger = logger;
    }

    /// <summary>
    /// Sync notices from SuperSet to PostgreSQL
    /// </summary>
    /// <remarks>
    /// Fetches all notices from SuperSet and upserts them into PostgreSQL.
    /// Existing notices are updated, new ones are inserted.
    /// </remarks>
    /// <returns>Sync statistics</returns>
    /// <response code="200">Sync completed successfully</response>
    /// <response code="500">Sync failed</response>
    [HttpPost("notices/sync")]
    [ProducesResponseType(typeof(ApiResponse<SyncResult>), 200)]
    [ProducesResponseType(typeof(ApiResponse<SyncResult>), 500)]
    public async Task<ActionResult<ApiResponse<SyncResult>>> SyncNotices()
    {
        _logger.LogInformation("Manual notices sync triggered via API");
        
        var result = await _syncService.SyncNoticesAsync();
        
        if (result.Success)
            return Ok(ApiResponse<SyncResult>.Ok(result, result.Message));
        
        return StatusCode(500, ApiResponse<SyncResult>.Fail(result.Message));
    }

    /// <summary>
    /// Sync jobs from SuperSet to PostgreSQL
    /// </summary>
    /// <remarks>
    /// Fetches basic job listings from SuperSet, identifies new jobs,
    /// fetches detailed information for new jobs only, and saves to PostgreSQL.
    /// </remarks>
    /// <returns>Sync statistics</returns>
    /// <response code="200">Sync completed successfully</response>
    /// <response code="500">Sync failed</response>
    [HttpPost("jobs/sync")]
    [ProducesResponseType(typeof(ApiResponse<SyncResult>), 200)]
    [ProducesResponseType(typeof(ApiResponse<SyncResult>), 500)]
    public async Task<ActionResult<ApiResponse<SyncResult>>> SyncJobs()
    {
        _logger.LogInformation("Manual jobs sync triggered via API");
        
        var result = await _syncService.SyncJobsAsync();
        
        if (result.Success)
            return Ok(ApiResponse<SyncResult>.Ok(result, result.Message));
        
        return StatusCode(500, ApiResponse<SyncResult>.Fail(result.Message));
    }
}
