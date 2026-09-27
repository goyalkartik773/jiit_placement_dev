using System.Text.Json.Serialization;

namespace JIITPlacement.Models
{
    /// <summary>
    /// One line of console output produced by a server-side admin script.
    /// The UI renders these verbatim, so past runs can be replayed exactly
    /// as they happened - no client-side line synthesis.
    /// </summary>
    public class ScriptOutputLine
    {
        [JsonPropertyName("time")]
        public string Time { get; set; } = "";

        /// <summary>cmd | info | success | warn | error | step</summary>
        [JsonPropertyName("tone")]
        public string Tone { get; set; } = "info";

        [JsonPropertyName("text")]
        public string Text { get; set; } = "";
    }

    /// <summary>Live status of one admin script (gmail sync, offer sync, deletes).</summary>
    public class AdminScriptStatus
    {
        [JsonPropertyName("script")]
        public string Script { get; set; } = "";

        [JsonPropertyName("runId")]
        public string? RunId { get; set; }

        /// <summary>idle | running | completed | failed</summary>
        [JsonPropertyName("status")]
        public string Status { get; set; } = "idle";

        [JsonPropertyName("message")]
        public string Message { get; set; } = "";

        [JsonPropertyName("username")]
        public string? Username { get; set; }

        [JsonPropertyName("startedAt")]
        public DateTimeOffset? StartedAt { get; set; }

        [JsonPropertyName("finishedAt")]
        public DateTimeOffset? FinishedAt { get; set; }

        [JsonPropertyName("durationMs")]
        public long? DurationMs { get; set; }

        /// <summary>0-100 while running; null when the script does not report progress.</summary>
        [JsonPropertyName("progress")]
        public int? Progress { get; set; }

        /// <summary>Real counters/delta straight from the database.</summary>
        [JsonPropertyName("counters")]
        public object? Counters { get; set; }

        [JsonPropertyName("output")]
        public List<ScriptOutputLine> Output { get; set; } = new();

        [JsonPropertyName("error")]
        public string? Error { get; set; }
    }

    /// <summary>Progress reported by the Gmail sync pipeline, one event per message.</summary>
    public class GmailSyncProgress
    {
        public string Phase { get; set; } = "listing";
        public string? GroupName { get; set; }
        public string? GroupEmail { get; set; }
        public int Total { get; set; }
        public int Done { get; set; }
        public int Fetched { get; set; }
        public int NewMessages { get; set; }
        public int Existing { get; set; }
        public int Processed { get; set; }
        public int ReviewRequired { get; set; }
        public int Failed { get; set; }
        public int Attachments { get; set; }
        public string? MessageId { get; set; }
        public string? Subject { get; set; }
        public string? Result { get; set; }
    }

    /// <summary>A single timed phase of a script, reported in milliseconds.</summary>
    public class ScriptPhase
    {
        [JsonPropertyName("phase")]
        public string Phase { get; set; } = "";

        [JsonPropertyName("durationMs")]
        public long DurationMs { get; set; }
    }

    /// <summary>Result of a synchronous admin delete script.</summary>
    public class AdminScriptResult
    {
        public bool Success { get; set; }
        public string Script { get; set; } = "";
        public string RunId { get; set; } = "";
        public string Message { get; set; } = "";
        public string? Error { get; set; }
        public Dictionary<string, object?> Counters { get; set; } = new();
        public List<ScriptOutputLine> Output { get; set; } = new();
        public List<ScriptPhase> Phases { get; set; } = new();
        public long DurationMs { get; set; }
    }
}
