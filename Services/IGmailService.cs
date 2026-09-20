using System.Data;
using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface IGmailService
    {
        /// <summary>
        /// Build Gmail queries for all configured source groups.
        /// </summary>
        List<string> BuildGroupQueries(string? additionalQuery = null);

        /// <summary>
        /// Fetch message IDs matching a query.
        /// </summary>
        Task<List<string>> GetMessageIdsAsync(string query, int maxResults = 100);

        /// <summary>
        /// Fetch a complete Gmail message by ID.
        /// </summary>
        Task<Google.Apis.Gmail.v1.Data.Message?> GetMessageAsync(string messageId);

        /// <summary>
        /// Identify the source group from message headers.
        /// </summary>
        (string? groupName, string? groupEmail) IdentifySourceGroup(Google.Apis.Gmail.v1.Data.Message message);

        /// <summary>
        /// Synchronize messages from all configured groups (the complete pipeline).
        /// </summary>
        Task<GmailSyncResult> SyncAllAsync(GmailSyncRequest request);

        /// <summary>
        /// Get messages with pagination and filtering.
        /// </summary>
        Task<DataTable> GetMessagesAsync(int page = 1, int pageSize = 20, string sourceGroup = "", string status = "", string search = "");

        /// <summary>
        /// Get a single message with attachments and extraction.
        /// </summary>
        Task<object?> GetMessageDetailAsync(string messageId);

        /// <summary>
        /// Get messages in a thread.
        /// </summary>
        Task<List<object>> GetThreadMessagesAsync(string threadId);

        /// <summary>
        /// Manually reprocess a single message.
        /// </summary>
        Task<bool> ReprocessMessageAsync(string messageId);

        /// <summary>
        /// Get the Google OAuth authorization URL for user consent.
        /// </summary>
        string GetAuthorizationUrl();

        /// <summary>
        /// Exchange an authorization code for access/refresh tokens.
        /// </summary>
        Task ExchangeCodeAsync(string code);
    }
}
