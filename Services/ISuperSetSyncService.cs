using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface ISuperSetSyncService
    {
        /// <summary>
        /// Sync jobs and/or notices with a single SuperSet login. The optional
        /// progress callback receives real counters from the running job loop
        /// (source total is only known after the fetch — nothing is fabricated).
        /// </summary>
        Task<SyncResult> SyncAllAsync(bool syncJobs, bool syncNotices, IProgress<SyncProgress>? progress = null);
    }
}
