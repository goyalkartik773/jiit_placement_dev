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
        /// <paramref name="username"/> is only used for the history entry.
        /// </summary>
        Task<(bool started, AdminSyncStatus status, string? busyOperation)> TryStartAsync(string? username = null);

        /// <summary>Current snapshot (status "idle" when never run).</summary>
        AdminSyncStatus GetStatus();

        /// <summary>
        /// Live job count straight from the jobs table (single source of truth).
        /// Returns null when the count could not be determined; throws on DB errors.
        /// </summary>
        Task<int?> GetTotalJobsAsync();

        /// <summary>
        /// Claim the single-operation slot for any admin script (job deletion,
        /// gmail sync, offer sync, mailbox delete, ...). Returns whether it was
        /// claimed plus the operation holding it when not.
        /// </summary>
        (bool allowed, string? busyOperation) TryBeginScript(string script);

        /// <summary>Release a slot claimed by <see cref="TryBeginScript"/>.</summary>
        void EndScript();

        /// <summary>Operation currently holding the slot, or null when idle.</summary>
        string? BusyOperation { get; }

        /// <summary>
        /// Claim the slot for a job deletion (thin wrapper over
        /// <see cref="TryBeginScript"/> with the legacy "delete" label).
        /// </summary>
        (bool allowed, string? busyOperation) TryBeginDelete();

        /// <summary>Release the slot claimed by <see cref="TryBeginDelete"/>.</summary>
        void EndDelete();
    }
}
