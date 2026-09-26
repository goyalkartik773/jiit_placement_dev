namespace JIITPlacement.Services
{
    /// <summary>
    /// One measured step of a job deletion (real wall-clock timings, used by
    /// the admin console output).
    /// </summary>
    public class JobCleanupPhase
    {
        public string Phase { get; init; } = string.Empty;
        public long DurationMs { get; init; }
    }

    /// <summary>Outcome of a delete-all-jobs run.</summary>
    public class JobCleanupResult
    {
        public bool Success { get; init; }
        public string? Message { get; init; }
        public int JobsDeleted { get; init; }
        public int DocumentRowsDeleted { get; init; }
        public int FilesDeleted { get; init; }
        public int FilesMissing { get; init; }
        public int FilesFailed { get; init; }
        public long DurationMs { get; init; }
        public List<JobCleanupPhase> Phases { get; init; } = new();
    }

    /// <summary>
    /// Deletes every job and the documents it owns: records first (single
    /// database transaction), then the stored files under the storage root.
    /// Notices and Gmail data are never touched.
    /// </summary>
    public interface IJobCleanupService
    {
        Task<JobCleanupResult> DeleteAllJobsAsync();
    }
}
