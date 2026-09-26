using System.Text.Json;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Single authority for running job synchronization: at most one sync at a
    /// time, executed in the background, with real counters reported by the
    /// existing sync loop. All state is in-memory and mirrored only through
    /// snapshots, so HTTP requests never block on the sync itself.
    /// </summary>
    public class AdminSyncCoordinator : IAdminSyncCoordinator
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<AdminSyncCoordinator> _logger;

        private readonly object _gate = new();
        private AdminSyncStatus _status = new();
        private int _busyFlag; // 0 = idle, 1 = sync or delete in progress
        private volatile string? _busyOperation; // "sync" | "delete" while busy

        public AdminSyncCoordinator(
            IServiceScopeFactory scopeFactory,
            ILogger<AdminSyncCoordinator> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        public AdminSyncStatus GetStatus()
        {
            lock (_gate)
            {
                return _status.Clone();
            }
        }

        public async Task<(bool started, AdminSyncStatus status, string? busyOperation)> TryStartAsync()
        {
            // Atomic guard: only the first caller may claim the operation slot.
            if (Interlocked.CompareExchange(ref _busyFlag, 1, 0) != 0)
            {
                _logger.LogWarning("Sync start rejected — another admin operation is already running");
                return (false, GetStatus(), _busyOperation);
            }
            _busyOperation = "sync";

            var syncId = Guid.NewGuid().ToString("N");
            int? totalBefore = await TryCountJobsAsync();

            var status = new AdminSyncStatus
            {
                Status = "running",
                SyncId = syncId,
                Message = "Job synchronization started",
                TotalJobsBeforeSync = totalBefore,
                JobsTotal = null, // unknown until the source list is fetched
                JobsProcessed = 0,
                NewJobs = 0,
                DocumentsDownloaded = 0,
                DocumentsFailed = 0,
                FailedJobs = 0,
                Progress = null, // no fabricated percentage before the total is known
                StartedAt = DateTimeOffset.UtcNow
            };

            lock (_gate)
            {
                _status = status;
            }

            _logger.LogInformation("Sync {SyncId} started — {Count} jobs before sync",
                syncId, totalBefore?.ToString() ?? "unknown");

            var snapshot = status.Clone();
            _ = Task.Run(() => RunSyncAsync(syncId, totalBefore));
            return (true, snapshot, null);
        }

        private async Task RunSyncAsync(string syncId, int? totalBefore)
        {
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var syncService = scope.ServiceProvider.GetRequiredService<ISuperSetSyncService>();
                var progress = new InlineProgress<SyncProgress>(p => ApplyProgress(syncId, p));

                var result = await syncService.SyncAllAsync(syncJobs: true, syncNotices: true, progress);

                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                int? totalAfter = await CountJobsAsync(dataEntity);

                if (!result.Success)
                {
                    Fail(syncId, result.Message);
                    return;
                }

                AdminSyncStatus final;
                lock (_gate)
                {
                    if (_status.SyncId != syncId) return;
                    _status.Status = "completed";
                    _status.Message = result.Message; // "Sync completed in Xs"
                    _status.TotalJobsAfterSync = totalAfter;
                    _status.Progress = ComputeProgress(_status.JobsProcessed, _status.JobsTotal);
                    _status.FinishedAt = DateTimeOffset.UtcNow;
                    final = _status.Clone();
                }

                _logger.LogInformation(
                    "Sync {SyncId} completed — jobs {Before} -> {After}, {New} new, {Processed}/{Total} processed, {Docs} documents downloaded, {DocFailed} document failures, {Failed} failed jobs",
                    syncId, totalBefore, totalAfter, final.NewJobs, final.JobsProcessed,
                    final.JobsTotal, final.DocumentsDownloaded, final.DocumentsFailed, final.FailedJobs);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Sync {SyncId} failed", syncId);
                Fail(syncId, ex.Message);
            }
            finally
            {
                _busyOperation = null;
                Interlocked.Exchange(ref _busyFlag, 0);
            }
        }

        public (bool allowed, string? busyOperation) TryBeginDelete()
        {
            if (Interlocked.CompareExchange(ref _busyFlag, 1, 0) != 0)
            {
                _logger.LogWarning("Deletion rejected — another admin operation is already running");
                return (false, _busyOperation);
            }

            _busyOperation = "delete";
            return (true, null);
        }

        public void EndDelete()
        {
            _busyOperation = null;
            Interlocked.Exchange(ref _busyFlag, 0);
        }

        /// <summary>Merge one real progress report from the sync loop.</summary>
        private void ApplyProgress(string syncId, SyncProgress p)
        {
            lock (_gate)
            {
                if (_status.SyncId != syncId || _status.Status != "running") return;

                _status.JobsTotal = p.JobsTotal;
                _status.JobsProcessed = p.JobsProcessed;
                _status.NewJobs = p.NewJobs;
                _status.FailedJobs = p.JobsFailed;
                _status.DocumentsDownloaded = p.DocumentsDownloaded;
                _status.DocumentsFailed = p.DocumentsFailed;
                _status.Progress = ComputeProgress(p.JobsProcessed, p.JobsTotal);
            }
        }

        private void Fail(string syncId, string error)
        {
            lock (_gate)
            {
                if (_status.SyncId != syncId) return;
                _status.Status = "failed";
                _status.Message = "Job synchronization failed";
                _status.Error = error;
                _status.FinishedAt = DateTimeOffset.UtcNow;
            }

            _logger.LogError("Sync {SyncId} failed: {Error}", syncId, error);
        }

        public async Task<int?> GetTotalJobsAsync()
        {
            using var scope = _scopeFactory.CreateScope();
            var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
            return await CountJobsAsync(dataEntity);
        }

        private async Task<int?> TryCountJobsAsync()
        {
            try
            {
                return await GetTotalJobsAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to count jobs before sync");
                return null;
            }
        }

        private static async Task<int?> CountJobsAsync(DataEntity dataEntity)
        {
            var dt = await dataEntity.ExecuteDataTableFNAsync("fn_api_count_jobs_v001");
            if (dt.Rows.Count == 0) return null;

            var json = dt.Rows[0][0]?.ToString();
            if (string.IsNullOrEmpty(json)) return null;

            var element = Common.ParseJson(json);
            if (element.ValueKind != JsonValueKind.Object ||
                !element.TryGetProperty("totalJobs", out var total))
                return null;

            return total.GetInt32();
        }

        /// <summary>Real percentage only when the source total is known; otherwise null.</summary>
        private static int? ComputeProgress(int? processed, int? total)
        {
            if (processed is null || total is null || total <= 0) return null;
            return (int)Math.Round(100.0 * processed.Value / total.Value, MidpointRounding.AwayFromZero);
        }

        /// <summary>IProgress that invokes its handler synchronously (no posted callbacks).</summary>
        private sealed class InlineProgress<T> : IProgress<T>
        {
            private readonly Action<T> _handler;
            public InlineProgress(Action<T> handler) => _handler = handler;
            public void Report(T value) => _handler(value);
        }
    }
}
