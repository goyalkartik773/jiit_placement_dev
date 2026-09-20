namespace JIITPlacement.Models.SuperSet;

public class SyncScheduleOptions
{
    public const string SectionName = "SyncSchedule";
    
    /// <summary>
    /// How often to sync notices (in minutes). Default: 30 minutes.
    /// </summary>
    public int NoticeSyncIntervalMinutes { get; set; } = 30;
    
    /// <summary>
    /// How often to sync jobs (in minutes). Default: 60 minutes.
    /// </summary>
    public int JobSyncIntervalMinutes { get; set; } = 60;
    
    /// <summary>
    /// Whether to sync on application startup. Default: true.
    /// </summary>
    public bool SyncOnStartup { get; set; } = true;
    
    /// <summary>
    /// Whether auto-sync is enabled. Default: true.
    /// </summary>
    public bool Enabled { get; set; } = true;
}
