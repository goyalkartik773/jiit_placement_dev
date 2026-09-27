using System.Data;
using System.Text.Json;
using JIITPlacement.Controllers;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Persists an admin script run to admin_script_runs (begin → finish) so the
    /// console history and the activity timeline are served from the database,
    /// never from client state. JSON payloads travel as text (PostgreSQL does not
    /// implicitly cast text → json).
    /// </summary>
    public static class AdminScriptRunLog
    {
        /// <summary>Opens a run row; returns its id, or null when logging failed.</summary>
        public static string? Begin(DataEntity dataEntity, string script, string username, string message)
        {
            try
            {
                DataTable dt = dataEntity.ExecuteDataTableFNParam(
                    "fn_api_script_run_begin_v1",
                    ("script", script),
                    ("username", (object?)username ?? DBNull.Value),
                    ("message", (object?)message ?? DBNull.Value));

                if (dt.Rows.Count == 0) return null;

                var element = Common.ParseJson(dt.Rows[0][0].ToString());
                return element.TryGetProperty("id", out var id) ? id.GetString() : null;
            }
            catch
            {
                return null; // history is best-effort; never blocks the script itself
            }
        }

        /// <summary>Closes a run row with its real counters and console output.</summary>
        public static void Finish(
            DataEntity dataEntity,
            string? runId,
            string status,
            string message,
            object? counters,
            IEnumerable<ScriptOutputLine> output,
            string? error,
            long durationMs)
        {
            if (string.IsNullOrEmpty(runId)) return;

            try
            {
                dataEntity.ExecuteDataTableFNParam(
                    "fn_api_script_run_finish_v1",
                    ("id", runId),
                    ("status", status),
                    ("message", (object?)message ?? DBNull.Value),
                    ("counters", (object?)(counters is null ? null : JsonSerializer.Serialize(counters)) ?? DBNull.Value),
                    ("output", (object?)JsonSerializer.Serialize(output) ?? DBNull.Value),
                    ("error", (object?)error ?? DBNull.Value),
                    ("durationms", ToInt(durationMs)));
            }
            catch
            {
                // best effort — the run itself already finished
            }
        }

        /// <summary>Records a one-shot action (login / logout / rejected start).</summary>
        public static string? Log(
            DataEntity dataEntity,
            string script,
            string status,
            string username,
            string message,
            object? counters,
            IEnumerable<ScriptOutputLine>? output,
            long durationMs)
        {
            try
            {
                DataTable dt = dataEntity.ExecuteDataTableFNParam(
                    "fn_api_script_run_log_v1",
                    ("script", script),
                    ("status", status),
                    ("username", (object?)username ?? DBNull.Value),
                    ("message", (object?)message ?? DBNull.Value),
                    ("counters", (object?)(counters is null ? null : JsonSerializer.Serialize(counters)) ?? DBNull.Value),
                    ("output", (object?)(output is null ? null : JsonSerializer.Serialize(output)) ?? DBNull.Value),
                    ("durationms", ToInt(durationMs)));

                if (dt.Rows.Count == 0) return null;
                var element = Common.ParseJson(dt.Rows[0][0].ToString());
                return element.TryGetProperty("id", out var id) ? id.GetString() : null;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// PostgreSQL's "integer" is 32-bit: Npgsql sends a CLR long as bigint, and
        /// a bigint argument does not resolve against an integer parameter.
        /// </summary>
        private static int ToInt(long value)
            => value > int.MaxValue ? int.MaxValue : value < int.MinValue ? int.MinValue : (int)value;
    }
}
