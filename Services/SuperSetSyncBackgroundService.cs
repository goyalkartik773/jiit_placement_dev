using JIITPlacement.Models.SuperSet;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services;

/// <summary>
/// Background service that automatically syncs notices and jobs from SuperSet on a schedule.
/// </summary>
public class SuperSetSyncBackgroundService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly SyncScheduleOptions _scheduleOptions;
    private readonly SuperSetOptions _superSetOptions;
    private readonly ILogger<SuperSetSyncBackgroundService> _logger;

    public SuperSetSyncBackgroundService(
        IServiceProvider serviceProvider,
        IOptions<SyncScheduleOptions> scheduleOptions,
        IOptions<SuperSetOptions> superSetOptions,
        ILogger<SuperSetSyncBackgroundService> logger)
    {
        _serviceProvider = serviceProvider;
        _scheduleOptions = scheduleOptions.Value;
        _superSetOptions = superSetOptions.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_scheduleOptions.Enabled)
        {
            _logger.LogInformation("Auto-sync is disabled via configuration");
            return;
        }

        _logger.LogInformation(
            "SuperSet background sync started. Notices every {NoticeInterval}min, Jobs every {JobInterval}min",
            _scheduleOptions.NoticeSyncIntervalMinutes,
            _scheduleOptions.JobSyncIntervalMinutes);

        // Sync on startup if configured
        if (_scheduleOptions.SyncOnStartup)
        {
            _logger.LogInformation("Running initial sync on startup...");
            await RunSyncAsync(stoppingToken);
        }

        // Create timers for each sync type
        var noticeTimer = new PeriodicTimer(
            TimeSpan.FromMinutes(_scheduleOptions.NoticeSyncIntervalMinutes));
        var jobTimer = new PeriodicTimer(
            TimeSpan.FromMinutes(_scheduleOptions.JobSyncIntervalMinutes));

        // Run both timers concurrently
        var noticeTask = RunNoticeSyncLoopAsync(noticeTimer, stoppingToken);
        var jobTask = RunJobSyncLoopAsync(jobTimer, stoppingToken);

        await Task.WhenAll(noticeTask, jobTask);
    }

    private async Task RunNoticeSyncLoopAsync(PeriodicTimer timer, CancellationToken ct)
    {
        try
        {
            while (await timer.WaitForNextTickAsync(ct))
            {
                await SyncNoticesAsync(ct);
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            // Normal shutdown
        }
    }

    private async Task RunJobSyncLoopAsync(PeriodicTimer timer, CancellationToken ct)
    {
        try
        {
            while (await timer.WaitForNextTickAsync(ct))
            {
                await SyncJobsAsync(ct);
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            // Normal shutdown
        }
    }

    private async Task RunSyncAsync(CancellationToken ct)
    {
        await SyncNoticesAsync(ct);
        await SyncJobsAsync(ct);
    }

    private async Task SyncNoticesAsync(CancellationToken ct)
    {
        try
        {
            _logger.LogInformation("[Background] Starting notices sync...");

            using var scope = _serviceProvider.CreateScope();
            var syncService = scope.ServiceProvider.GetRequiredService<ISuperSetSyncService>();

            var result = await syncService.SyncNoticesAsync();

            _logger.LogInformation(
                "[Background] Notices sync completed: {Inserted} inserted, {Updated} updated, {Failed} failed",
                result.Inserted, result.Updated, result.Failed);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[Background] Notices sync failed");
        }
    }

    private async Task SyncJobsAsync(CancellationToken ct)
    {
        try
        {
            _logger.LogInformation("[Background] Starting jobs sync...");

            using var scope = _serviceProvider.CreateScope();
            var syncService = scope.ServiceProvider.GetRequiredService<ISuperSetSyncService>();

            var result = await syncService.SyncJobsAsync();

            _logger.LogInformation(
                "[Background] Jobs sync completed: {Inserted} inserted, {Failed} failed",
                result.Inserted, result.Failed);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[Background] Jobs sync failed");
        }
    }
}
