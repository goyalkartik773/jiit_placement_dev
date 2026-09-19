using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services;

public interface ISuperSetSyncService
{
    Task<SyncResult> SyncNoticesAsync();
    Task<SyncResult> SyncJobsAsync();
}
