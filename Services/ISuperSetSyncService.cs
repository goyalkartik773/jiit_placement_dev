using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface ISuperSetSyncService
    {
        Task<SyncResult> SyncNoticesAsync();
        Task<SyncResult> SyncJobsAsync();
    }
}
