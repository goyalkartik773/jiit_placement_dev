using System.Data;
using System.Diagnostics;
using System.Text.Json;
using JIITPlacement.Controllers;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// The two destructive admin scripts: wipe the synced mailbox and wipe the
    /// job↔student mapping. Both are synchronous (like the delete-all-jobs
    /// cleanup), both take the shared single-script slot, and both record their
    /// real counts + console output in admin_script_runs.
    /// </summary>
    public interface IAdminDeleteScripts
    {
        Task<AdminScriptResult> DeleteGmailAsync(string username);
        Task<AdminScriptResult> DeleteMappingsAsync(string username);
    }

    public class AdminDeleteScripts : IAdminDeleteScripts
    {
        public const string GmailScript = "delete_gmail";
        public const string MappingsScript = "delete_mappings";

        private readonly IServiceScopeFactory _scopeFactory;
        private readonly IAdminSyncCoordinator _syncCoordinator;
        private readonly IAdminScriptStore _store;
        private readonly ILogger<AdminDeleteScripts> _logger;

        public AdminDeleteScripts(
            IServiceScopeFactory scopeFactory,
            IAdminSyncCoordinator syncCoordinator,
            IAdminScriptStore store,
            ILogger<AdminDeleteScripts> logger)
        {
            _scopeFactory = scopeFactory;
            _syncCoordinator = syncCoordinator;
            _store = store;
            _logger = logger;
        }

        /// <summary>
        /// Deletes gmailmessages / gmailattachments / emailextractions — i.e. everything
        /// the mailbox sync writes. The parsed email corpus and the placement mapping
        /// are deliberately left alone (that is a separate script).
        /// </summary>
        public async Task<AdminScriptResult> DeleteGmailAsync(string username)
        {
            await Task.Yield();
            const string cmd = "DELETE /api/admin/gmail";
            const string script = GmailScript;

            var result = Begin(script, cmd, username, out string? runId, out string? busy);
            if (result is not null) return result;

            var sw = Stopwatch.StartNew();
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                var phase = Stopwatch.StartNew();
                var before = ReadOverview(dataEntity);
                phase.Stop();
                long inspectMs = phase.ElapsedMilliseconds;

                int messages = GetInt(before, "counts", "gmailMessages");
                int attachments = GetInt(before, "counts", "gmailAttachments");
                _store.Line(script, "info", $"→ mailbox in the database — {messages} messages · {attachments} attachment rows");

                phase.Restart();
                DataTable dt = dataEntity.ExecuteDataTableFN("fn_api_delete_all_gmail_v001");
                phase.Stop();
                long deleteMs = phase.ElapsedMilliseconds;

                if (dt.Rows.Count == 0)
                    return await FailAsync(script, runId, "Mailbox delete produced no result",
                        "Mailbox delete produced no result", sw.ElapsedMilliseconds, username);

                var payload = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!PlacementController.IsSuccess(payload, out string fnMessage))
                    return await FailAsync(script, runId,
                        string.IsNullOrEmpty(fnMessage) ? "Mailbox delete failed" : fnMessage,
                        string.IsNullOrEmpty(fnMessage) ? "Mailbox delete failed" : fnMessage,
                        sw.ElapsedMilliseconds, username);

                int messagesDeleted = PlacementController.GetInt32(payload, "messagesDeleted");
                int attachmentsDeleted = PlacementController.GetInt32(payload, "attachmentsDeleted");
                int extractionsDeleted = PlacementController.GetInt32(payload, "extractionsDeleted");

                _store.Line(script, "success",
                    $"✓ deleted {messagesDeleted} messages · {attachmentsDeleted} attachment rows · {extractionsDeleted} extraction rows");
                _store.Line(script, "info",
                    "  parsed email corpus (emails, offers, offer_students) and placement mappings were NOT touched");

                var counters = new
                {
                    messagesBefore = messages,
                    attachmentsBefore = attachments,
                    messagesDeleted,
                    attachmentsDeleted,
                    extractionsDeleted,
                    sqlDurationMs = GetLong(payload, "durationMs")
                };

                sw.Stop();
                var message = $"Mailbox deleted — {messagesDeleted} messages, {attachmentsDeleted} attachments, {extractionsDeleted} extractions";
                _store.Finish(script, "completed", message, counters, null, sw.ElapsedMilliseconds);
                AdminScriptRunLog.Finish(dataEntity, runId, "completed", message, counters,
                    _store.Get(script).Output, null, sw.ElapsedMilliseconds);

                _logger.LogInformation(
                    "Mailbox deleted: {Messages} messages, {Attachments} attachments, {Extractions} extractions",
                    messagesDeleted, attachmentsDeleted, extractionsDeleted);

                return new AdminScriptResult
                {
                    Success = true,
                    Script = script,
                    RunId = runId ?? "",
                    Message = message,
                    Counters = ToDictionary(counters),
                    Output = _store.Get(script).Output,
                    Phases = new()
                    {
                        new() { Phase = "inspect", DurationMs = inspectMs },
                        new() { Phase = "delete", DurationMs = deleteMs }
                    },
                    DurationMs = sw.ElapsedMilliseconds
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Mailbox delete failed");
                return await FailAsync(script, runId, "Mailbox delete failed: " + ex.Message, ex.Message,
                    sw.ElapsedMilliseconds, username);
            }
            finally
            {
                _syncCoordinator.EndScript();
            }
        }

        /// <summary>Deletes every row in job_placed_students (mappings only).</summary>
        public async Task<AdminScriptResult> DeleteMappingsAsync(string username)
        {
            await Task.Yield();
            const string cmd = "DELETE /api/admin/jobs/placed-students";
            const string script = MappingsScript;

            var result = Begin(script, cmd, username, out string? runId, out string? busy);
            if (result is not null) return result;

            var sw = Stopwatch.StartNew();
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                var phase = Stopwatch.StartNew();
                var before = ReadOverview(dataEntity);
                phase.Stop();
                long inspectMs = phase.ElapsedMilliseconds;

                int mappings = GetInt(before, "counts", "mappings");
                int students = GetInt(before, "matching", "studentsMapped");
                int companies = GetInt(before, "matching", "companiesMatched");
                _store.Line(script, "info",
                    $"→ mapping in the database — {mappings} rows · {students} students · {companies} companies");

                phase.Restart();
                DataTable dt = dataEntity.ExecuteDataTableFN("fn_api_delete_all_placed_students_v001");
                phase.Stop();
                long deleteMs = phase.ElapsedMilliseconds;

                if (dt.Rows.Count == 0)
                    return await FailAsync(script, runId, "Mapping delete produced no result",
                        "Mapping delete produced no result", sw.ElapsedMilliseconds, username);

                var payload = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!PlacementController.IsSuccess(payload, out string fnMessage))
                    return await FailAsync(script, runId,
                        string.IsNullOrEmpty(fnMessage) ? "Mapping delete failed" : fnMessage,
                        string.IsNullOrEmpty(fnMessage) ? "Mapping delete failed" : fnMessage,
                        sw.ElapsedMilliseconds, username);

                int deleted = PlacementController.GetInt32(payload, "mappingsDeleted");
                int studentsCleared = PlacementController.GetInt32(payload, "studentsCleared");
                int companiesCleared = PlacementController.GetInt32(payload, "companiesCleared");

                _store.Line(script, "success",
                    $"✓ deleted {deleted} mappings covering {studentsCleared} students and {companiesCleared} companies");
                _store.Line(script, "info",
                    "  jobs, offers and offer_students were NOT touched — re-run the job to student sync to rebuild");

                var counters = new
                {
                    mappingsBefore = mappings,
                    studentsBefore = students,
                    companiesBefore = companies,
                    mappingsDeleted = deleted,
                    studentsCleared,
                    companiesCleared,
                    sqlDurationMs = GetLong(payload, "durationMs")
                };

                sw.Stop();
                var message = $"Placement mappings deleted — {deleted} rows cleared";
                _store.Finish(script, "completed", message, counters, null, sw.ElapsedMilliseconds);
                AdminScriptRunLog.Finish(dataEntity, runId, "completed", message, counters,
                    _store.Get(script).Output, null, sw.ElapsedMilliseconds);

                _logger.LogInformation(
                    "Placement mappings deleted: {Rows} rows, {Students} students, {Companies} companies",
                    deleted, studentsCleared, companiesCleared);

                return new AdminScriptResult
                {
                    Success = true,
                    Script = script,
                    RunId = runId ?? "",
                    Message = message,
                    Counters = ToDictionary(counters),
                    Output = _store.Get(script).Output,
                    Phases = new()
                    {
                        new() { Phase = "inspect", DurationMs = inspectMs },
                        new() { Phase = "delete", DurationMs = deleteMs }
                    },
                    DurationMs = sw.ElapsedMilliseconds
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Placement mapping delete failed");
                return await FailAsync(script, runId, "Mapping delete failed: " + ex.Message, ex.Message,
                    sw.ElapsedMilliseconds, username);
            }
            finally
            {
                _syncCoordinator.EndScript();
            }
        }

        // ------------------------------------------------------------------
        // shared plumbing
        // ------------------------------------------------------------------

        /// <summary>
        /// Claims the shared script slot and opens the run. Returns null when the
        /// script may proceed; otherwise a ready-made error result (409 / failure).
        /// </summary>
        private AdminScriptResult? Begin(string script, string cmd, string username, out string? runId, out string? busy)
        {
            runId = null;
            var (allowed, busyOperation) = _syncCoordinator.TryBeginScript(script);
            if (!allowed)
            {
                busy = busyOperation;
                return new AdminScriptResult
                {
                    Success = false,
                    Script = script,
                    Message = "Another admin script is running",
                    Error = busyOperation
                };
            }

            busy = null;
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                runId = AdminScriptRunLog.Begin(dataEntity, script, username, cmd);
                _store.Begin(script, runId ?? "", username, cmd);
                return null;
            }
            catch (Exception ex)
            {
                _syncCoordinator.EndScript();
                return new AdminScriptResult
                {
                    Success = false,
                    Script = script,
                    Message = "Could not start the script: " + ex.Message,
                    Error = ex.Message
                };
            }
        }

        private async Task<AdminScriptResult> FailAsync(
            string script, string? runId, string message, string error, long durationMs, string username)
        {
            await Task.Yield();
            _store.Line(script, "error", "✗ " + message);
            _store.Finish(script, "failed", message, null, error, durationMs);

            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();
                AdminScriptRunLog.Finish(dataEntity, runId, "failed", message, null,
                    _store.Get(script).Output, error, durationMs);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not persist the failed {Script} run", script);
            }

            return new AdminScriptResult
            {
                Success = false,
                Script = script,
                RunId = runId ?? "",
                Message = message,
                Error = error,
                Output = _store.Get(script).Output,
                DurationMs = durationMs
            };
        }

        private static JsonElement ReadOverview(DataEntity dataEntity)
        {
            DataTable dt = dataEntity.ExecuteDataTableFN("fn_api_admin_overview_v1");
            if (dt.Rows.Count == 0) return default;
            return Common.ParseJson(dt.Rows[0][0].ToString());
        }

        private static int GetInt(JsonElement element, string parent, string name)
        {
            if (element.ValueKind != JsonValueKind.Object ||
                !element.TryGetProperty(parent, out var group) ||
                group.ValueKind != JsonValueKind.Object ||
                !group.TryGetProperty(name, out var value) ||
                value.ValueKind != JsonValueKind.Number)
                return 0;
            return value.GetInt32();
        }

        private static long GetLong(JsonElement element, string name)
        {
            if (element.ValueKind != JsonValueKind.Object ||
                !element.TryGetProperty(name, out var value))
                return 0;
            return value.ValueKind switch
            {
                JsonValueKind.Number => (long)value.GetDouble(),
                JsonValueKind.String when long.TryParse(value.GetString(), out var parsed) => parsed,
                _ => 0
            };
        }

        /// <summary>Turns an anonymous counters object into a string-keyed dictionary.</summary>
        private static Dictionary<string, object?> ToDictionary(object counters)
        {
            var json = JsonSerializer.SerializeToElement(counters);
            var dict = new Dictionary<string, object?>();
            if (json.ValueKind != JsonValueKind.Object) return dict;
            foreach (var property in json.EnumerateObject())
                dict[property.Name] = property.Value.Clone();
            return dict;
        }
    }
}
