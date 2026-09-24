namespace JIITPlacement.Models
{
    /// <summary>
    /// Snapshot of the (single) background job synchronization. Counters stay
    /// null until they are actually known — no value is ever fabricated.
    /// </summary>
    public class AdminSyncStatus
    {
        /// <summary>idle | running | completed | failed</summary>
        public string Status { get; set; } = "idle";

        public string? SyncId { get; set; }
        public string? Message { get; set; }

        public int? TotalJobsBeforeSync { get; set; }
        public int? TotalJobsAfterSync { get; set; }

        /// <summary>Source total — null until the job list has been fetched.</summary>
        public int? JobsTotal { get; set; }
        public int? JobsProcessed { get; set; }
        public int? NewJobs { get; set; }
        public int? DocumentsDownloaded { get; set; }
        public int? DocumentsFailed { get; set; }
        public int? FailedJobs { get; set; }

        /// <summary>0–100 only while the source total is known; otherwise null.</summary>
        public int? Progress { get; set; }

        public DateTimeOffset? StartedAt { get; set; }
        public DateTimeOffset? FinishedAt { get; set; }
        public string? Error { get; set; }

        public AdminSyncStatus Clone() => (AdminSyncStatus)MemberwiseClone();
    }
}
