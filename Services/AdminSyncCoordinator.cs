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
        private string? _runRowId; // admin_script_runs.id of the current run
        private int _nextLogAt; // next jobsProcessed value to print in the console

        public AdminSyncCoordinator(
            IServiceScopeFactory scopeFactory,
            ILogger<AdminSyncCoordinator> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        private bool _hydrated; // last persisted jobs_sync run already loaded

        public AdminSyncStatus GetStatus()
        {
            lock (_gate)
            {
                if (_hydrated) return _status.Clone();
                _hydrated = true; // claim the one-off load before doing IO
            }

            HydrateLastRun();

            lock (_gate)
            {
                return _status.Clone();
            }
        }

        /// <summary>
        /// Load the last persisted jobs_sync run after a restart, so the status
        /// endpoint reports what actually happened instead of a fresh <c>idle</c>.
        /// A run started in this process always wins over the loaded row.
        /// </summary>
        private void HydrateLastRun()
        {
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                var dt = dataEntity.ExecuteDataTableFNParam(
                    "fn_api_select_script_runs_v1", ("page", 1), ("pagesize", 1), ("script", "jobs_sync"));
                if (dt.Rows.Count == 0) return;

                var root = Common.ParseJson(dt.Rows[0][0].ToString() ?? "");
                if (root.ValueKind != JsonValueKind.Object ||
                    !root.TryGetProperty("Items", out var items) ||
                    items.ValueKind != JsonValueKind.Array || items.GetArrayLength() == 0)
                    return;

                var row = items[0];
                var status = new AdminSyncStatus
                {
                    SyncId = Str(row, "id"),
                    Status = Str(row, "status") ?? "idle",
                    Message = Str(row, "message"),
                    Error = Str(row, "error"),
                    StartedAt = Date(row, "startedat"),
                    FinishedAt = Date(row, "finishedat"),
                    DurationMs = Num(row, "durationms"),
                    TotalJobsBeforeSync = Int(row, "counters", "totalJobsBeforeSync"),
                    TotalJobsAfterSync = Int(row, "counters", "totalJobsAfterSync"),
                    JobsTotal = Int(row, "counters", "jobsTotal"),
                    JobsProcessed = Int(row, "counters", "jobsProcessed"),
                    NewJobs = Int(row, "counters", "newJobs"),
                    DocumentsDownloaded = Int(row, "counters", "documentsDownloaded"),
                    DocumentsFailed = Int(row, "counters", "documentsFailed"),
                    FailedJobs = Int(row, "counters", "failedJobs"),
                    Output = ReadOutput(row)
                };
                status.Progress = ComputeProgress(status.JobsProcessed, status.JobsTotal);

                // A row still marked "running" means the API restarted mid-run.
                if (status.Status == "running")
                {
                    status.Status = "failed";
                    status.Error ??= "Run interrupted — the API restarted while the script was running";
                    status.Message ??= "Run interrupted";
                }

                lock (_gate)
                {
                    if (_status.Status != "idle" || _runRowId is not null) return; // a live run owns the status
                    _status = status;
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not hydrate the last jobs_sync run from the database");
            }
        }

        private static List<ScriptOutputLine> ReadOutput(JsonElement row)
        {
            var lines = new List<ScriptOutputLine>();
            if (!row.TryGetProperty("output", out var output) || output.ValueKind != JsonValueKind.Array)
                return lines;

            foreach (var line in output.EnumerateArray())
            {
                lines.Add(new ScriptOutputLine
                {
                    Time = Str(line, "time") ?? "",
                    Tone = Str(line, "tone") ?? "info",
                    Text = Str(line, "text") ?? ""
                });
            }
            return lines;
        }

        private static string? Str(JsonElement row, string name) =>
            row.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;

        private static DateTimeOffset? Date(JsonElement row, string name)
        {
            var text = Str(row, name);
            return text is not null && DateTimeOffset.TryParse(text, out var parsed) ? parsed : null;
        }

        private static long? Num(JsonElement row, string name) =>
            row.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.Number
                ? value.GetInt64()
                : null;

        private static int? Int(JsonElement row, string group, string name)
        {
            if (!row.TryGetProperty(group, out var value) || value.ValueKind != JsonValueKind.Object)
                return null;
            return value.TryGetProperty(name, out var nested) && nested.ValueKind == JsonValueKind.Number
                ? nested.GetInt32()
                : null;
        }

        public async Task<(bool started, AdminSyncStatus status, string? busyOperation)> TryStartAsync(string? username = null)
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
                StartedAt = DateTimeOffset.UtcNow,
                Output = new List<ScriptOutputLine>()
            };
            AppendLine(status, "cmd", "$ POST /api/admin/jobs/sync");
            AppendLine(status, "info", totalBefore is null
                ? "→ job count unavailable before sync"
                : $"→ {totalBefore} jobs in the database before sync");
            AppendLine(status, "info", "→ source: Superset job feed (jobs + notices + documents)");

            // History is best-effort: a logging failure must never block the sync.
            _runRowId = null;
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                _runRowId = AdminScriptRunLog.Begin(dataEntity, "jobs_sync", username ?? "unknown",
                    "POST /api/admin/jobs/sync");
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not open the jobs_sync history row");
            }

            lock (_gate)
            {
                _status = status;
                _nextLogAt = 0;
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
                    Persist(syncId, "failed", "Job synchronization failed", result.Message);
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
                    MarkFinished(_status);
                    AppendLine(_status, "success",
                        $"✓ {_status.TotalJobsBeforeSync} → {totalAfter} jobs in the database");
                    AppendLine(_status, "info",
                        $"  {_status.JobsProcessed}/{_status.JobsTotal} source jobs processed · {_status.NewJobs} new · " +
                        $"{_status.DocumentsDownloaded} documents downloaded" +
                        (_status.FailedJobs > 0 ? $" · {_status.FailedJobs} failed" : "") +
                        (_status.DocumentsFailed > 0 ? $" · {_status.DocumentsFailed} document failures" : ""));
                    final = _status.Clone();
                }

                Persist(syncId, "completed", final.Message ?? "Job synchronization completed", null);

                _logger.LogInformation(
                    "Sync {SyncId} completed — jobs {Before} -> {After}, {New} new, {Processed}/{Total} processed, {Docs} documents downloaded, {DocFailed} document failures, {Failed} failed jobs",
                    syncId, totalBefore, totalAfter, final.NewJobs, final.JobsProcessed,
                    final.JobsTotal, final.DocumentsDownloaded, final.DocumentsFailed, final.FailedJobs);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Sync {SyncId} failed", syncId);
                Fail(syncId, ex.Message);
                Persist(syncId, "failed", "Job synchronization failed", ex.Message);
            }
            finally
            {
                _busyOperation = null;
                Interlocked.Exchange(ref _busyFlag, 0);
            }
        }

        public string? BusyOperation => _busyOperation;

        public (bool allowed, string? busyOperation) TryBeginScript(string script)
        {
            if (Interlocked.CompareExchange(ref _busyFlag, 1, 0) != 0)
            {
                _logger.LogWarning(
                    "Script {Script} rejected — {Busy} is already running", script, _busyOperation);
                return (false, _busyOperation);
            }

            _busyOperation = script;
            return (true, null);
        }

        public void EndScript()
        {
            _busyOperation = null;
            Interlocked.Exchange(ref _busyFlag, 0);
        }

        public (bool allowed, string? busyOperation) TryBeginDelete() => TryBeginScript("delete");

        public void EndDelete() => EndScript();

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

                // Print about 20 progress lines per run — enough to feel live,
                // few enough to keep the console readable and the log small.
                if (p.JobsTotal is int total && total > 0)
                {
                    int step = Math.Max(1, (int)Math.Ceiling(total / 20.0));
                    if (_nextLogAt == 0) _nextLogAt = step;
                    if (p.JobsProcessed >= _nextLogAt || p.JobsProcessed == total)
                    {
                        AppendLine(_status, "info",
                            $"  [{p.JobsProcessed}/{p.JobsTotal}] {p.NewJobs} new · {p.DocumentsDownloaded} documents" +
                            (p.JobsFailed > 0 ? $" · {p.JobsFailed} failed" : ""));
                        _nextLogAt = p.JobsProcessed + step;
                    }
                }
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
                MarkFinished(_status);
                AppendLine(_status, "error", "✗ " + error);
            }

            _logger.LogError("Sync {SyncId} failed: {Error}", syncId, error);
        }

        /// <summary>Write the run to admin_script_runs so history survives restarts.</summary>
        private void Persist(string syncId, string status, string message, string? error)
        {
            AdminSyncStatus snapshot;
            string? runId;
            lock (_gate)
            {
                if (_status.SyncId != syncId) return;
                snapshot = _status.Clone();
                runId = _runRowId;
                _runRowId = null;
            }

            if (string.IsNullOrEmpty(runId)) return;

            long durationMs = snapshot.DurationMs
                ?? (snapshot.StartedAt is not null && snapshot.FinishedAt is not null
                    ? (long)Math.Max((snapshot.FinishedAt.Value - snapshot.StartedAt.Value).TotalMilliseconds, 0)
                    : 0);

            var counters = new
            {
                totalJobsBeforeSync = snapshot.TotalJobsBeforeSync,
                totalJobsAfterSync = snapshot.TotalJobsAfterSync,
                jobsTotal = snapshot.JobsTotal,
                jobsProcessed = snapshot.JobsProcessed,
                newJobs = snapshot.NewJobs,
                documentsDownloaded = snapshot.DocumentsDownloaded,
                documentsFailed = snapshot.DocumentsFailed,
                failedJobs = snapshot.FailedJobs
            };

            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                AdminScriptRunLog.Finish(dataEntity, runId, status, message, counters,
                    snapshot.Output ?? new List<ScriptOutputLine>(), error, durationMs);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not persist the jobs_sync history row");
            }
        }

        /// <summary>Clock a run off: finish time and the measured duration.</summary>
        private static void MarkFinished(AdminSyncStatus status)
        {
            status.FinishedAt = DateTimeOffset.UtcNow;
            status.DurationMs = status.StartedAt is null
                ? null
                : (long)Math.Max((status.FinishedAt.Value - status.StartedAt.Value).TotalMilliseconds, 0);
        }

        /// <summary>Append a console line while holding the status lock.</summary>
        private static void AppendLine(AdminSyncStatus status, string tone, string text)
        {
            status.Output ??= new List<ScriptOutputLine>();
            status.Output.Add(new ScriptOutputLine
            {
                Time = DateTime.Now.ToString("HH:mm:ss"),
                Tone = tone,
                Text = text
            });
            if (status.Output.Count > 500)
                status.Output.RemoveRange(0, status.Output.Count - 500);
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
