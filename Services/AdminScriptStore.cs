using System.Data;
using System.Text.Json;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Live state of the admin console scripts (gmail sync, offer sync, deletes).
    /// The current run is kept in memory while it executes; after a restart the
    /// last persisted run is hydrated from admin_script_runs, so the console can
    /// always replay a real run instead of showing an empty screen.
    /// </summary>
    public interface IAdminScriptStore
    {
        /// <summary>Open a run in memory (runId comes from the persisted row).</summary>
        AdminScriptStatus Begin(string script, string runId, string username, string message);

        /// <summary>Append a console line produced by the server.</summary>
        void Line(string script, string tone, string text);

        /// <summary>Merge fresh counters into the running script.</summary>
        void SetCounters(string script, object counters);

        void SetProgress(string script, int? progress);

        /// <summary>Close the in-memory run with its final counters/error.</summary>
        void Finish(string script, string status, string message, object? counters, string? error, long durationMs);

        /// <summary>Snapshot of the given script ("idle" when it never ran).</summary>
        AdminScriptStatus Get(string script);
    }

    public class AdminScriptStore : IAdminScriptStore
    {
        private const int MaxLines = 500;

        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<AdminScriptStore> _logger;
        private readonly object _gate = new();
        private readonly Dictionary<string, AdminScriptStatus> _runs = new();
        private readonly HashSet<string> _hydrated = new();

        public AdminScriptStore(IServiceScopeFactory scopeFactory, ILogger<AdminScriptStore> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        public AdminScriptStatus Begin(string script, string runId, string username, string message)
        {
            var state = new AdminScriptStatus
            {
                Script = script,
                RunId = runId,
                Status = "running",
                Username = username,
                Message = message,
                StartedAt = DateTimeOffset.Now,
                Progress = null
            };
            state.Output.Add(Line("cmd", "$ " + message));

            lock (_gate)
            {
                _runs[script] = state;
                _hydrated.Add(script);
            }
            return Clone(state);
        }

        public void Line(string script, string tone, string text)
        {
            lock (_gate)
            {
                if (!_runs.TryGetValue(script, out var state)) return;
                state.Output.Add(new ScriptOutputLine
                {
                    Time = DateTime.Now.ToString("HH:mm:ss"),
                    Tone = tone,
                    Text = text
                });
                if (state.Output.Count > MaxLines)
                    state.Output.RemoveRange(0, state.Output.Count - MaxLines);
            }
        }

        public void SetCounters(string script, object counters)
        {
            lock (_gate)
            {
                if (_runs.TryGetValue(script, out var state)) state.Counters = counters;
            }
        }

        public void SetProgress(string script, int? progress)
        {
            lock (_gate)
            {
                if (_runs.TryGetValue(script, out var state)) state.Progress = progress;
            }
        }

        public void Finish(string script, string status, string message, object? counters, string? error, long durationMs)
        {
            lock (_gate)
            {
                if (!_runs.TryGetValue(script, out var state)) return;

                state.Status = status;
                state.Message = message;
                state.Error = error;
                state.DurationMs = durationMs;
                state.FinishedAt = DateTimeOffset.Now;
                state.Progress = status == "completed" ? 100 : state.Progress;
                if (counters is not null) state.Counters = counters;

                var tone = status == "completed" ? "success" : "error";
                var prefix = status == "completed" ? "✓ " : "✗ ";
                state.Output.Add(new ScriptOutputLine
                {
                    Time = DateTime.Now.ToString("HH:mm:ss"),
                    Tone = tone,
                    Text = prefix + message + " · " + durationMs + " ms"
                });
                if (state.Output.Count > MaxLines)
                    state.Output.RemoveRange(0, state.Output.Count - MaxLines);
            }
        }

        public AdminScriptStatus Get(string script)
        {
            lock (_gate)
            {
                if (_runs.TryGetValue(script, out var live)) return Clone(live);
                if (_hydrated.Contains(script)) return Idle(script);
                _hydrated.Add(script); // hydrate once, outside the lock below
            }

            return Hydrate(script) ?? Idle(script);
        }

        /// <summary>Load the latest persisted run of this script after a restart.</summary>
        private AdminScriptStatus? Hydrate(string script)
        {
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                DataTable dt = dataEntity.ExecuteDataTableFNParam(
                    "fn_api_select_script_runs_v1", ("page", 1), ("pagesize", 1), ("script", script));

                if (dt.Rows.Count == 0) return null;

                var root = Common.ParseJson(dt.Rows[0][0].ToString());
                if (root.ValueKind != JsonValueKind.Object ||
                    !root.TryGetProperty("Items", out var items) ||
                    items.ValueKind != JsonValueKind.Array || items.GetArrayLength() == 0)
                    return null;

                var row = items[0];
                var status = new AdminScriptStatus
                {
                    Script = script,
                    RunId = GetString(row, "id"),
                    Status = GetString(row, "status") ?? "idle",
                    Username = GetString(row, "username"),
                    Message = GetString(row, "message") ?? "",
                    Error = GetString(row, "error"),
                    StartedAt = GetDate(row, "startedat"),
                    FinishedAt = GetDate(row, "finishedat"),
                    DurationMs = row.TryGetProperty("durationms", out var dms) && dms.ValueKind == JsonValueKind.Number
                        ? dms.GetInt64() : null,
                    Counters = row.TryGetProperty("counters", out var counters) && counters.ValueKind != JsonValueKind.Null
                        ? counters : null
                };

                if (row.TryGetProperty("output", out var output) && output.ValueKind == JsonValueKind.Array)
                {
                    foreach (var line in output.EnumerateArray())
                    {
                        status.Output.Add(new ScriptOutputLine
                        {
                            Time = GetString(line, "time") ?? "",
                            Tone = GetString(line, "tone") ?? "info",
                            Text = GetString(line, "text") ?? ""
                        });
                    }
                }

                // A row still marked "running" can only mean the API was restarted
                // mid-run — say so instead of pretending it is still going.
                if (status.Status == "running")
                {
                    status.Status = "failed";
                    status.Error ??= "Run interrupted — the API restarted while the script was running";
                    status.Message = string.IsNullOrEmpty(status.Message) ? "Run interrupted" : status.Message;
                }

                lock (_gate)
                {
                    _runs[script] = status;
                }
                return status;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not hydrate the last {Script} run from the database", script);
                return null;
            }
        }

        private static AdminScriptStatus Idle(string script) => new()
        {
            Script = script,
            Status = "idle",
            Message = "Not run yet"
        };

        private static AdminScriptStatus Clone(AdminScriptStatus state) => new()
        {
            Script = state.Script,
            RunId = state.RunId,
            Status = state.Status,
            Message = state.Message,
            Username = state.Username,
            StartedAt = state.StartedAt,
            FinishedAt = state.FinishedAt,
            DurationMs = state.DurationMs,
            Progress = state.Progress,
            Counters = state.Counters,
            Error = state.Error,
            Output = new List<ScriptOutputLine>(state.Output)
        };

        private static string? GetString(JsonElement element, string name)
            => element.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
                ? value.GetString() : null;

        private static DateTimeOffset? GetDate(JsonElement element, string name)
            => element.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String &&
               DateTimeOffset.TryParse(value.GetString(), out var parsed) ? parsed : null;

        private static ScriptOutputLine Line(string tone, string text) => new()
        {
            Time = DateTime.Now.ToString("HH:mm:ss"),
            Tone = tone,
            Text = text
        };
    }
}
