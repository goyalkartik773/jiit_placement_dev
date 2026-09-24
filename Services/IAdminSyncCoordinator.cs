using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Runs at most one job synchronization at a time in the background and
    /// exposes its live status for the admin UI.
    /// </summary>
    public interface IAdminSyncCoordinator
    {
        /// <summary>
        /// Start a sync unless one is already running.
        /// Returns whether it started plus the resulting status snapshot.
        /// </summary>
        Task<(bool started, AdminSyncStatus status)> TryStartAsync();

        /// <summary>Current snapshot (status "idle" when never run).</summary>
        AdminSyncStatus GetStatus();
    }
}
