using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Runs at most one admin data operation at a time in the background and
    /// exposes its live status for the admin UI. Sync and delete share the
    /// single slot so they can never corrupt each other.
    /// </summary>
    public interface IAdminSyncCoordinator
    {
        /// <summary>
        /// Start a sync unless another admin operation is already running.
        /// Returns whether it started, the status snapshot, and the operation
        /// holding the slot ("sync" or "delete") when it did not start.
        /// </summary>
        Task<(bool started, AdminSyncStatus status, string? busyOperation)> TryStartAsync();

        /// <summary>Current snapshot (status "idle" when never run).</summary>
        AdminSyncStatus GetStatus();

        /// <summary>
        /// Live job count straight from the jobs table (single source of truth).
        /// Returns null when the count could not be determined; throws on DB errors.
        /// </summary>
        Task<int?> GetTotalJobsAsync();

        /// <summary>
        /// Claim the single-operation slot for a job deletion.
        /// Returns whether it was claimed plus the operation holding it when not.
        /// </summary>
        (bool allowed, string? busyOperation) TryBeginDelete();

        /// <summary>Release the slot claimed by <see cref="TryBeginDelete"/>.</summary>
        void EndDelete();
    }
}
