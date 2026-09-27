using System.Data;
using System.Diagnostics;
using System.Text.Json;
using JIITPlacement.Controllers;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Runs the admin "console scripts" (mailbox sync, job↔student sync) in the
    /// background while streaming server-generated output lines into
    /// <see cref="IAdminScriptStore"/>. Every counter written to the console or
    /// to the response is read from the database — nothing is estimated.
    /// </summary>
    public interface IAdminScriptRunner
    {
        /// <summary>Start the mailbox sync; returns busyScript when another script holds the slot.</summary>
        Task<(bool started, string? busyScript)> StartGmailSyncAsync(GmailSyncRequest request, string username);

        /// <summary>Start the job↔student sync; returns busyScript when another script holds the slot.</summary>
        Task<(bool started, string? busyScript)> StartOfferSyncAsync(string username);

        /// <summary>Live status of one script (hydrates the last persisted run on demand).</summary>
        AdminScriptStatus GetStatus(string script);
    }

    public class AdminScriptRunner : IAdminScriptRunner
    {
        public const string GmailScript = "gmail_sync";
        public const string OfferScript = "offer_sync";

        private readonly IServiceScopeFactory _scopeFactory;
        private readonly IAdminSyncCoordinator _syncCoordinator;
        private readonly IAdminScriptStore _store;
        private readonly ILogger<AdminScriptRunner> _logger;

        public AdminScriptRunner(
            IServiceScopeFactory scopeFactory,
            IAdminSyncCoordinator syncCoordinator,
            IAdminScriptStore store,
            ILogger<AdminScriptRunner> logger)
        {
            _scopeFactory = scopeFactory;
            _syncCoordinator = syncCoordinator;
            _store = store;
            _logger = logger;
        }

        public AdminScriptStatus GetStatus(string script) => _store.Get(script);

        // ------------------------------------------------------------------
        // Mailbox (Gmail) sync
        // ------------------------------------------------------------------
        public async Task<(bool started, string? busyScript)> StartGmailSyncAsync(GmailSyncRequest request, string username)
        {
            await Task.Yield();
            const string cmd = "POST /api/admin/gmail/sync";
            var (allowed, busy) = _syncCoordinator.TryBeginScript(GmailScript);
            if (!allowed) return (false, busy);

            string? runId;
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                runId = AdminScriptRunLog.Begin(dataEntity, GmailScript, username, cmd);
                _store.Begin(GmailScript, runId ?? "", username, cmd);

                var before = ReadOverview(dataEntity);
                int messages = GetInt(before, "counts", "gmailMessages");
                int attachments = GetInt(before, "counts", "gmailAttachments");

                _store.Line(GmailScript, "info", $"→ mailbox before sync — {messages} messages · {attachments} attachment rows");
                _store.Line(GmailScript, "info",
                    $"→ Gmail API · max {request.MaxResults} ids per source group" +
                    (string.IsNullOrWhiteSpace(request.Query) ? "" : $" · query \"{request.Query}\""));
                _store.SetCounters(GmailScript, new
                {
                    messagesBefore = messages,
                    attachmentsBefore = attachments
                });
            }
            catch (Exception ex)
            {
                _store.Finish(GmailScript, "failed", "Mailbox sync could not start", null, ex.Message, 0);
                _syncCoordinator.EndScript();
                _logger.LogError(ex, "Could not start the mailbox sync script");
                throw;
            }

            _ = Task.Run(() => RunGmailSyncAsync(runId, request));
            return (true, null);
        }

        private async Task RunGmailSyncAsync(string? runId, GmailSyncRequest request)
        {
            var sw = Stopwatch.StartNew();
            var totals = new SyncTally();
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var gmail = scope.ServiceProvider.GetRequiredService<IGmailService>();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                // Snapshot the mailbox BEFORE any write, so the delta is real.
                var before = ReadOverview(dataEntity);
                int messagesBefore = GetInt(before, "counts", "gmailMessages");
                int attachmentsBefore = GetInt(before, "counts", "gmailAttachments");

                var progress = new InlineProgress<GmailSyncProgress>(p => OnGmailProgress(p, totals));
                var result = await gmail.SyncAllAsync(request, progress);

                var after = ReadOverview(dataEntity);
                int messagesAfter = GetInt(after, "counts", "gmailMessages");
                int attachmentsAfter = GetInt(after, "counts", "gmailAttachments");

                var counters = new
                {
                    messagesBefore,
                    messagesAfter,
                    messagesAdded = Math.Max(messagesAfter - messagesBefore, 0),
                    attachmentsBefore,
                    attachmentsAfter,
                    attachmentsAdded = Math.Max(attachmentsAfter - attachmentsBefore, 0),
                    fetched = result.TotalFetched,
                    newMessages = result.Groups.Sum(g => g.NewMessages),
                    existingMessages = result.Groups.Sum(g => g.ExistingMessages),
                    processed = result.TotalProcessed,
                    reviewRequired = result.TotalReviewRequired,
                    failed = result.TotalFailed,
                    groups = result.Groups.Select(g => new
                    {
                        name = g.GroupName,
                        email = g.GroupEmail,
                        fetched = g.Fetched,
                        newMessages = g.NewMessages,
                        existingMessages = g.ExistingMessages,
                        processed = g.Processed,
                        reviewRequired = g.ReviewRequired,
                        failed = g.Failed
                    }).ToArray()
                };

                sw.Stop();
                if (!result.Success)
                {
                    _store.Line(GmailScript, "error", "✗ " + result.Message);
                    _store.Finish(GmailScript, "failed", "Mailbox sync failed", counters, result.Message, sw.ElapsedMilliseconds);
                    using var failScope = _scopeFactory.CreateScope();
                    AdminScriptRunLog.Finish(failScope.ServiceProvider.GetRequiredService<DataEntity>(),
                        runId, "failed", "Mailbox sync failed",
                        counters, _store.Get(GmailScript).Output, result.Message, sw.ElapsedMilliseconds);
                    return;
                }

                int added = counters.messagesAdded;
                var message = added > 0
                    ? $"Mailbox synced — {added} new messages stored ({messagesAfter} total)"
                    : $"Mailbox up to date — no new messages ({messagesAfter} total)";

                _store.Line(GmailScript, "success",
                    $"✓ {result.TotalFetched} ids fetched · {counters.newMessages} new · {counters.existingMessages} already stored · {result.TotalProcessed} processed · {result.TotalReviewRequired} review · {result.TotalFailed} failed");
                _store.Line(GmailScript, "info",
                    $"→ mailbox after sync — {messagesAfter} messages (+{counters.messagesAdded}) · {attachmentsAfter} attachment rows (+{counters.attachmentsAdded})");
                _store.Finish(GmailScript, "completed", message, counters, null, sw.ElapsedMilliseconds);
                AdminScriptRunLog.Finish(dataEntity, runId, "completed", message,
                    counters, _store.Get(GmailScript).Output, null, sw.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                sw.Stop();
                _logger.LogError(ex, "Mailbox sync script failed");
                _store.Finish(GmailScript, "failed", "Mailbox sync failed", null, ex.Message, sw.ElapsedMilliseconds);
                using var failScope = _scopeFactory.CreateScope();
                AdminScriptRunLog.Finish(failScope.ServiceProvider.GetRequiredService<DataEntity>(),
                    runId, "failed", "Mailbox sync failed",
                    null, _store.Get(GmailScript).Output, ex.Message, sw.ElapsedMilliseconds);
            }
            finally
            {
                _syncCoordinator.EndScript();
            }
        }

        private void OnGmailProgress(GmailSyncProgress p, SyncTally tally)
        {
            switch (p.Phase)
            {
                case "listing":
                    tally.AddGroup(p.Total);
                    _store.Line(GmailScript, "info",
                        $"→ [{p.GroupName}] {p.Total} message ids listed");
                    break;

                case "group_done":
                    _store.Line(GmailScript, p.Failed > 0 ? "warn" : "info",
                        $"✓ [{p.GroupName}] {p.Fetched} fetched · {p.NewMessages} new · {p.Existing} already stored · {p.Processed} processed · {p.ReviewRequired} review · {p.Failed} failed");
                    break;

                case "message":
                    tally.Step();
                    int step = Math.Max(1, (int)Math.Ceiling(p.Total / 20.0));
                    bool milestone = p.Done == p.Total || p.Done % step == 0;
                    if (milestone)
                    {
                        _store.Line(GmailScript, "info",
                            $"  [{p.Done}/{p.Total}] {DescribeOutcome(p.Result)} · {DescribeId(p.MessageId)}");
                    }
                    else if (p.Result is "NewFailed" or "Exception")
                    {
                        _store.Line(GmailScript, "error", $"  [{p.Done}/{p.Total}] failed · {DescribeId(p.MessageId)}");
                    }

                    var percent = tally.Percent;
                    if (percent is not null) _store.SetProgress(GmailScript, percent);
                    break;
            }
        }

        // ------------------------------------------------------------------
        // Job ↔ student (offer) sync
        // ------------------------------------------------------------------
        public async Task<(bool started, string? busyScript)> StartOfferSyncAsync(string username)
        {
            await Task.Yield();
            const string cmd = "POST /api/admin/jobs/sync-offer-students";
            var (allowed, busy) = _syncCoordinator.TryBeginScript(OfferScript);
            if (!allowed) return (false, busy);

            string? runId;
            DateTimeOffset startedAt;
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                runId = AdminScriptRunLog.Begin(dataEntity, OfferScript, username, cmd);
                startedAt = DateTimeOffset.Now;
                _store.Begin(OfferScript, runId ?? "", username, cmd);

                var before = ReadOverview(dataEntity);
                _store.Line(OfferScript, "info",
                    $"→ source tables — {GetInt(before, "counts", "offerStudents")} offer students · " +
                    $"{GetInt(before, "counts", "offers")} offers · {GetInt(before, "counts", "emails")} emails · " +
                    $"{GetInt(before, "counts", "jobs")} job listings");
                _store.Line(OfferScript, "info",
                    "→ matching by company only (trim + collapse spaces + lowercase + drop one trailing \"(...)\";");
                _store.Line(OfferScript, "info",
                    "  companies that are not in the Jobs table are skipped, never created)");
                _store.SetCounters(OfferScript, new
                {
                    mappingsBefore = GetInt(before, "counts", "mappings"),
                    studentsBefore = GetInt(before, "counts", "offerStudents"),
                    jobsBefore = GetInt(before, "counts", "jobs")
                });
            }
            catch (Exception ex)
            {
                _store.Finish(OfferScript, "failed", "Job to student sync could not start", null, ex.Message, 0);
                _syncCoordinator.EndScript();
                _logger.LogError(ex, "Could not start the offer sync script");
                throw;
            }

            _ = Task.Run(() => RunOfferSyncAsync(runId, startedAt));
            return (true, null);
        }

        private async Task RunOfferSyncAsync(string? runId, DateTimeOffset startedAt)
        {
            await Task.Yield();
            var sw = Stopwatch.StartNew();
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var dataEntity = scope.ServiceProvider.GetRequiredService<DataEntity>();

                // Snapshot the source tables BEFORE the sync writes, so the
                // reported "… before" numbers are real before-counts (same
                // discipline as the mailbox sync above).
                var sourceBefore = ReadOverview(dataEntity);
                int mappingsBefore = GetInt(sourceBefore, "counts", "mappings");
                int studentsBefore = GetInt(sourceBefore, "counts", "offerStudents");
                int jobsBefore = GetInt(sourceBefore, "counts", "jobs");

                DataTable dt = dataEntity.ExecuteDataTableFN("fn_api_sync_offer_students_v1");
                if (dt.Rows.Count == 0)
                    throw new InvalidOperationException("Offer-student sync produced no result");

                var stats = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!PlacementController.IsSuccess(stats, out string fnMessage))
                    throw new InvalidOperationException(string.IsNullOrEmpty(fnMessage)
                        ? "Offer-student sync failed" : fnMessage);

                int mappingsInserted = PlacementController.GetInt32(stats, "mappingsInserted");
                int jobsMatched = PlacementController.GetInt32(stats, "jobsMatched");
                int jobsTotal = PlacementController.GetInt32(stats, "jobsTotal");
                int companiesMatched = PlacementController.GetInt32(stats, "companiesMatched");
                int companiesSkipped = PlacementController.GetInt32(stats, "companiesSkipped");
                int studentsMapped = PlacementController.GetInt32(stats, "studentsMapped");

                _store.Line(OfferScript, "success",
                    $"✓ {mappingsInserted} mappings inserted · {studentsMapped} students mapped · " +
                    $"{jobsMatched}/{jobsTotal} jobs matched · {companiesMatched} companies · {companiesSkipped} skipped");

                // What changed in THIS run — measured from placed_at, not guessed.
                // Npgsql only accepts UTC offsets for timestamptz parameters.
                DataTable deltaDt = dataEntity.ExecuteDataTableFNParam(
                    "fn_api_offer_sync_changes_v1", ("since", startedAt.ToUniversalTime()));
                var delta = deltaDt.Rows.Count > 0
                    ? Common.ParseJson(deltaDt.Rows[0][0].ToString() ?? "")
                    : default(JsonElement);
                bool deltaKnown = delta.ValueKind == JsonValueKind.Object;
                int inserted = deltaKnown ? PlacementController.GetInt32(delta, "mappingsInserted") : 0;

                if (!deltaKnown)
                {
                    _store.Line(OfferScript, "warn",
                        "  delta unavailable — the change query returned no row (run still completed)");
                }
                else if (inserted > 0)
                {
                    int companies = delta.ValueKind == JsonValueKind.Object ? PlacementController.GetInt32(delta, "companiesTouched") : 0;
                    _store.Line(OfferScript, "info", $"→ changes — {inserted} new mappings across {companies} companies");
                    if (delta.TryGetProperty("changes", out var changes) && changes.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var change in changes.EnumerateArray().Take(20))
                        {
                            string company = change.TryGetProperty("company", out var c) ? c.GetString() ?? "?" : "?";
                            int students = change.TryGetProperty("students", out var s) && s.ValueKind == JsonValueKind.Number ? s.GetInt32() : 0;
                            _store.Line(OfferScript, "info", $"    {company}  +{students}");
                        }
                    }
                }
                else
                {
                    _store.Line(OfferScript, "info",
                        "→ changes — no new mappings (every offer student was already mapped; re-run is idempotent)");
                }

                var after = ReadOverview(dataEntity);
                var integrity = new
                {
                    orphanMappings = GetInt(after, "integrity", "orphanMappings"),
                    duplicateMappings = GetInt(after, "integrity", "duplicateMappings"),
                    orphanOffers = GetInt(after, "integrity", "orphanOffers"),
                    blankRolls = GetInt(after, "integrity", "blankRolls"),
                    totalMappings = GetInt(after, "counts", "mappings")
                };
                _store.Line(OfferScript, integrity.orphanMappings == 0 && integrity.duplicateMappings == 0
                        ? "success" : "error",
                    $"✓ integrity — {integrity.totalMappings} rows · {integrity.orphanMappings} orphan · " +
                    $"{integrity.duplicateMappings} duplicate (job_id, roll) · {integrity.blankRolls} blank roll");

                sw.Stop();
                var counters = new
                {
                    source = new
                    {
                        mappingsBefore,
                        studentsBefore,
                        jobsBefore,
                        jobs = jobsTotal
                    },
                    stats = new
                    {
                        jobsTotal,
                        jobsMatched,
                        jobsWithoutPlacements = PlacementController.GetInt32(stats, "jobsWithoutPlacements"),
                        studentsConsidered = PlacementController.GetInt32(stats, "studentsConsidered"),
                        studentsMapped,
                        mappingsInserted,
                        duplicatesSkipped = PlacementController.GetInt32(stats, "duplicatesSkipped"),
                        companiesMatched,
                        companiesSkipped,
                        totalMappings = PlacementController.GetInt32(stats, "totalMappings"),
                        lastRunAt = PlacementController.GetProperty(stats, "lastRunAt")
                    },
                    delta,
                    integrity
                };

                var message = mappingsInserted > 0
                    ? $"Job to student sync completed — {mappingsInserted} new mappings"
                    : $"Job to student sync completed — no new mappings ({integrity.totalMappings} total)";

                _store.Finish(OfferScript, "completed", message, counters, null, sw.ElapsedMilliseconds);
                AdminScriptRunLog.Finish(dataEntity, runId, "completed", message,
                    counters, _store.Get(OfferScript).Output, null, sw.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                sw.Stop();
                _logger.LogError(ex, "Offer sync script failed");
                _store.Finish(OfferScript, "failed", "Job to student sync failed", null, ex.Message, sw.ElapsedMilliseconds);
                using var failScope = _scopeFactory.CreateScope();
                AdminScriptRunLog.Finish(failScope.ServiceProvider.GetRequiredService<DataEntity>(),
                    runId, "failed", "Job to student sync failed",
                    null, _store.Get(OfferScript).Output, ex.Message, sw.ElapsedMilliseconds);
            }
            finally
            {
                _syncCoordinator.EndScript();
            }
        }

        // ------------------------------------------------------------------
        // helpers
        // ------------------------------------------------------------------
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

        private static string DescribeOutcome(string? result) => result switch
        {
            "NewProcessed" => "stored · PROCESSED",
            "NewReviewRequired" => "stored · REVIEW_REQUIRED",
            "NewFailed" => "failed",
            "ExistingProcessed" => "already stored · skipped",
            "ExistingRetry" => "re-extracted",
            "Exception" => "exception",
            null => "no outcome",
            _ => result
        };

        private static string DescribeId(string? id)
            => string.IsNullOrEmpty(id) ? "(unknown id)" : "id " + (id.Length > 12 ? id[..12] : id);

        /// <summary>Running totals across groups so the console gets a real percentage.</summary>
        private sealed class SyncTally
        {
            private int _total;
            private int _done;
            public void AddGroup(int ids) => Interlocked.Add(ref _total, ids);
            public void Step() => Interlocked.Increment(ref _done);
            public int? Percent
            {
                get
                {
                    int total = Volatile.Read(ref _total);
                    if (total <= 0) return null;
                    int done = Volatile.Read(ref _done);
                    return (int)Math.Round(100.0 * done / total, MidpointRounding.AwayFromZero);
                }
            }
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
