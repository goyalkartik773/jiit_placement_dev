using System.Data;
using System.Text;
using System.Text.Json;
using Google.Apis.Auth.OAuth2;
using Google.Apis.Gmail.v1;
using Google.Apis.Gmail.v1.Data;
using Google.Apis.Services;
using Google.Apis.Util.Store;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public class GmailSyncService : IGmailService
    {
        private readonly GoogleGmailSettings _gmailSettings;
        private readonly GeminiSettings _geminiSettings;
        private readonly IEmailPreprocessor _preprocessor;
        private readonly IAttachmentProcessor _attachmentProcessor;
        private readonly IEmailExtractionService _extractionService;
        private readonly IEmailValidationService _validationService;
        private readonly DataEntity _dataEntity;
        private readonly ILogger<GmailSyncService> _logger;
        private Google.Apis.Gmail.v1.GmailService? _gmailApiService;

        public GmailSyncService(
            IOptions<GoogleGmailSettings> gmailOptions,
            IOptions<GeminiSettings> geminiOptions,
            IEmailPreprocessor preprocessor,
            IAttachmentProcessor attachmentProcessor,
            IEmailExtractionService extractionService,
            IEmailValidationService validationService,
            DataEntity dataEntity,
            ILogger<GmailSyncService> logger)
        {
            _gmailSettings = gmailOptions.Value;
            _geminiSettings = geminiOptions.Value;
            _preprocessor = preprocessor;
            _attachmentProcessor = attachmentProcessor;
            _extractionService = extractionService;
            _validationService = validationService;
            _dataEntity = dataEntity;
            _logger = logger;
        }

        private string GetTokenPath()
        {
            var tokenFile = _gmailSettings.TokenFilePath ?? "token.json";
            if (Path.IsPathRooted(tokenFile))
                return tokenFile;

            var appDataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "JIITPlacement");
            Directory.CreateDirectory(appDataDir);
            return Path.Combine(appDataDir, tokenFile);
        }

        private async Task<Google.Apis.Gmail.v1.GmailService> GetGmailApiServiceAsync()
        {
            if (_gmailApiService != null)
                return _gmailApiService;

            var credPath = GetTokenPath();

            if (!File.Exists(credPath))
            {
                throw new UnauthorizedAccessException(
                    "Gmail not authorized. Please visit http://localhost:5000/api/gmail/auth to authorize Gmail access.");
            }

            var tokenData = await File.ReadAllTextAsync(credPath);
            var token = JsonSerializer.Deserialize<TokenData>(tokenData);
            if (token == null || string.IsNullOrEmpty(token.AccessToken))
            {
                throw new UnauthorizedAccessException(
                    "Invalid token file. Please re-authorize at http://localhost:5000/api/gmail/auth");
            }

            // Check if token is expired (simple check: if issued more than expiresInSeconds ago)
            var elapsed = (DateTime.UtcNow - token.IssuedUtc).TotalSeconds;
            if (token.ExpiresInSeconds.HasValue && elapsed > token.ExpiresInSeconds.Value - 300)
            {
                // Try refresh
                if (!string.IsNullOrEmpty(token.RefreshToken))
                {
                    _logger.LogInformation("Access token expired, refreshing...");
                    var refreshed = await RefreshAccessTokenAsync(token);
                    if (refreshed)
                    {
                        token = JsonSerializer.Deserialize<TokenData>(await File.ReadAllTextAsync(credPath));
                    }
                    else
                    {
                        throw new UnauthorizedAccessException(
                            "Gmail token expired and refresh failed. Please re-authorize at http://localhost:5000/api/gmail/auth");
                    }
                }
                else
                {
                    throw new UnauthorizedAccessException(
                        "Gmail token expired. Please re-authorize at http://localhost:5000/api/gmail/auth");
                }
            }

            // Create credential using GoogleCredential with bearer token
            var googleCredential = GoogleCredential.FromAccessToken(token.AccessToken);

            _gmailApiService = new Google.Apis.Gmail.v1.GmailService(new BaseClientService.Initializer()
            {
                HttpClientInitializer = googleCredential,
                ApplicationName = _gmailSettings.ApplicationName ?? "JIIT Placement",
            });

            _logger.LogInformation("Gmail API service initialized from saved token");
            return _gmailApiService;
        }

        private async Task<bool> RefreshAccessTokenAsync(TokenData token)
        {
            var secrets = LoadClientSecrets();
            var content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                { "client_id", secrets.ClientId! },
                { "client_secret", secrets.ClientSecret! },
                { "refresh_token", token.RefreshToken! },
                { "grant_type", "refresh_token" },
            });

            using var http = new HttpClient();
            var response = await http.PostAsync("https://oauth2.googleapis.com/token", content);
            var json = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("Token refresh failed: {Status} {Response}", response.StatusCode, json);
                return false;
            }

            var refreshResult = JsonSerializer.Deserialize<JsonElement>(json);
            var newAccessToken = refreshResult.GetProperty("access_token").GetString();
            var newExpiresIn = refreshResult.GetProperty("expires_in").GetInt64();

            token.AccessToken = newAccessToken;
            token.ExpiresInSeconds = newExpiresIn;
            token.IssuedUtc = DateTime.UtcNow;

            var credPath = GetTokenPath();
            await File.WriteAllTextAsync(credPath, JsonSerializer.Serialize(token, new JsonSerializerOptions { WriteIndented = true }));
            _logger.LogInformation("Token refreshed and saved");
            return true;
        }

        private (string clientId, string clientSecret) GetClientIdSecret()
        {
            var secrets = LoadClientSecrets();
            return (secrets.ClientId!, secrets.ClientSecret!);
        }

        private Google.Apis.Auth.OAuth2.ClientSecrets LoadClientSecrets()
        {
            if (!string.IsNullOrEmpty(_gmailSettings.CredentialsFilePath) && File.Exists(_gmailSettings.CredentialsFilePath))
            {
                using var stream = new FileStream(_gmailSettings.CredentialsFilePath, FileMode.Open, FileAccess.Read);
                return GoogleClientSecrets.FromStream(stream).Secrets;
            }
            return new Google.Apis.Auth.OAuth2.ClientSecrets
            {
                ClientId = _gmailSettings.ClientId,
                ClientSecret = _gmailSettings.ClientSecret,
            };
        }

        public string GetAuthorizationUrl()
        {
            var (clientId, _) = GetClientIdSecret();
            var scopes = _gmailSettings.Scopes?.FirstOrDefault() ?? "https://www.googleapis.com/auth/gmail.readonly";
            var scopeStr = string.Join(" ", _gmailSettings.Scopes ?? new List<string> { scopes });

            var parameters = new Dictionary<string, string>
            {
                { "client_id", clientId },
                { "redirect_uri", "http://localhost:5000/api/gmail/auth/callback" },
                { "response_type", "code" },
                { "scope", scopeStr },
                { "access_type", "offline" },
                { "prompt", "consent" },
            };

            var queryString = string.Join("&", parameters.Select(kvp => $"{kvp.Key}={Uri.EscapeDataString(kvp.Value)}"));
            return $"https://accounts.google.com/o/oauth2/auth?{queryString}";
        }

        public async Task ExchangeCodeAsync(string code)
        {
            var (clientId, clientSecret) = GetClientIdSecret();

            var content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                { "client_id", clientId },
                { "client_secret", clientSecret },
                { "code", code },
                { "grant_type", "authorization_code" },
                { "redirect_uri", "http://localhost:5000/api/gmail/auth/callback" },
            });

            using var http = new HttpClient();
            var response = await http.PostAsync("https://oauth2.googleapis.com/token", content);
            var json = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Token exchange failed: {json}");
            }

            var result = JsonSerializer.Deserialize<JsonElement>(json);
            var tokenData = new TokenData
            {
                AccessToken = result.GetProperty("access_token").GetString(),
                RefreshToken = result.TryGetProperty("refresh_token", out var rt) ? rt.GetString() : null,
                ExpiresInSeconds = result.GetProperty("expires_in").GetInt64(),
                IssuedUtc = DateTime.UtcNow,
            };

            var credPath = GetTokenPath();
            await File.WriteAllTextAsync(credPath, JsonSerializer.Serialize(tokenData, new JsonSerializerOptions { WriteIndented = true }));

            _logger.LogInformation("Gmail OAuth token obtained and saved successfully");
        }

        public async Task SaveTokenAsync(TokenData tokenData)
        {
            var credPath = GetTokenPath();
            var json = JsonSerializer.Serialize(tokenData, new JsonSerializerOptions { WriteIndented = true });
            await File.WriteAllTextAsync(credPath, json);
            _logger.LogInformation("Token saved to {Path}", credPath);
        }

        public List<string> BuildGroupQueries(string? additionalQuery = null)
        {
            var queries = new List<string>();
            if (_gmailSettings.SourceGroups == null || _gmailSettings.SourceGroups.Count == 0)
            {
                _logger.LogWarning("No source groups configured");
                return queries;
            }

            foreach (var group in _gmailSettings.SourceGroups)
            {
                if (string.IsNullOrEmpty(group.Email)) continue;
                // Google Groups use List-Id header, not From
                // Convert jaypeeengg2027@googlegroups.com → list:jaypeeengg2027.googlegroups.com
                var listId = group.Email.Replace("@", ".");
                var query = $"list:{listId}";
                if (!string.IsNullOrWhiteSpace(additionalQuery))
                    query += $" {additionalQuery}";
                queries.Add(query);
            }

            return queries;
        }

        public async Task<List<string>> GetMessageIdsAsync(string query, int maxResults = 100)
        {
            var service = await GetGmailApiServiceAsync();
            var messageIds = new List<string>();
            string? pageToken = null;
            int fetched = 0;

            do
            {
                var request = service.Users.Messages.List("me");
                request.Q = query;
                request.MaxResults = Math.Min(maxResults - fetched, 100);
                request.PageToken = pageToken;

                var response = await ExecuteWithRetryAsync(() => request.ExecuteAsync());
                if (response.Messages != null)
                {
                    foreach (var msg in response.Messages)
                    {
                        if (msg.Id != null) { messageIds.Add(msg.Id); fetched++; }
                    }
                }
                pageToken = response.NextPageToken;
            } while (pageToken != null && fetched < maxResults);

            _logger.LogInformation("Fetched {Count} message IDs for query: {Query}", messageIds.Count, query);
            return messageIds;
        }

        public async Task<Message?> GetMessageAsync(string messageId)
        {
            var service = await GetGmailApiServiceAsync();
            var request = service.Users.Messages.Get("me", messageId);
            request.Format = UsersResource.MessagesResource.GetRequest.FormatEnum.Full;
            return await ExecuteWithRetryAsync(() => request.ExecuteAsync());
        }

        public (string? groupName, string? groupEmail) IdentifySourceGroup(Message message)
        {
            if (_gmailSettings.SourceGroups == null || _gmailSettings.SourceGroups.Count == 0)
                return (null, null);

            var headers = message.Payload?.Headers;
            if (headers == null) return (null, null);

            var headerValues = new List<string>();
            var headerNames = new[] { "From", "Sender", "List-Id", "List-Post", "Reply-To", "To", "Cc" };

            foreach (var header in headers)
            {
                if (headerNames.Contains(header.Name, StringComparer.OrdinalIgnoreCase) && !string.IsNullOrEmpty(header.Value))
                    headerValues.Add(header.Value.ToLowerInvariant());
            }

            foreach (var group in _gmailSettings.SourceGroups)
            {
                if (string.IsNullOrEmpty(group.Email)) continue;
                var groupEmailLower = group.Email.ToLowerInvariant();
                foreach (var hv in headerValues)
                {
                    if (hv.Contains(groupEmailLower))
                    {
                        _logger.LogInformation("Identified source group: {GroupName} ({GroupEmail})", group.Name, group.Email);
                        return (group.Name, group.Email);
                    }
                }
            }

            _logger.LogWarning("Could not identify source group for message {MessageId}", message.Id);
            return (null, null);
        }

        public async Task<GmailSyncResult> SyncAllAsync(GmailSyncRequest request)
        {
            _logger.LogInformation("Gmail sync started - MaxResults: {MaxResults}, Query: {Query}", request.MaxResults, request.Query ?? "(none)");

            var result = new GmailSyncResult { Success = true };

            var groupsToProcess = _gmailSettings.SourceGroups!;
            if (request.Groups != null && request.Groups.Count > 0)
            {
                groupsToProcess = groupsToProcess.Where(g => request.Groups.Contains(g.Email, StringComparer.OrdinalIgnoreCase)).ToList();
            }

            try
            {
                foreach (var group in groupsToProcess)
                {
                    _logger.LogInformation("Processing group: {GroupName} ({GroupEmail})", group.Name, group.Email);

                    var groupResult = new GmailGroupSyncResult { GroupName = group.Name, GroupEmail = group.Email };

                    var listId = group.Email.Replace("@", ".");
                    var query = $"list:{listId}";
                    if (!string.IsNullOrWhiteSpace(request.Query))
                        query += $" {request.Query}";

                    var messageIds = await GetMessageIdsAsync(query, request.MaxResults);
                    groupResult.Fetched = messageIds.Count;

                    foreach (var messageId in messageIds)
                    {
                        try
                        {
                            var procResult = await ProcessMessageAsync(messageId, group);
                            switch (procResult)
                            {
                                case MessageProcessResult.NewProcessed: groupResult.NewMessages++; groupResult.Processed++; break;
                                case MessageProcessResult.NewReviewRequired: groupResult.NewMessages++; groupResult.ReviewRequired++; break;
                                case MessageProcessResult.NewFailed: groupResult.NewMessages++; groupResult.Failed++; break;
                                case MessageProcessResult.ExistingProcessed: groupResult.ExistingMessages++; break;
                                case MessageProcessResult.ExistingRetry:
                                    var retryResult = await ProcessMessageAsync(messageId, group);
                                    if (retryResult == MessageProcessResult.NewProcessed) groupResult.Processed++;
                                    else if (retryResult == MessageProcessResult.NewReviewRequired) groupResult.ReviewRequired++;
                                    else groupResult.Failed++;
                                    break;
                            }
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "Failed to process message {MessageId}", messageId);
                            groupResult.Failed++;
                        }
                    }

                    result.Groups.Add(groupResult);
                }

                result.TotalFetched = result.Groups.Sum(g => g.Fetched);
                result.TotalProcessed = result.Groups.Sum(g => g.Processed);
                result.TotalReviewRequired = result.Groups.Sum(g => g.ReviewRequired);
                result.TotalFailed = result.Groups.Sum(g => g.Failed);
                result.Message = "Gmail synchronization and extraction completed successfully.";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Gmail sync failed");
                result.Success = false;
                result.Message = $"Gmail sync failed: {ex.Message}";
            }

            return result;
        }

        private async Task<MessageProcessResult> ProcessMessageAsync(string messageId, SourceGroup group)
        {
            DataTable existingDt = _dataEntity.ExecuteDataTableFN("fn_api_select_gmailmessage_v1", messageId);
            if (existingDt.Rows.Count > 0)
            {
                string existingJson = existingDt.Rows[0][0].ToString() ?? "";
                var existingResult = JsonSerializer.Deserialize<Dictionary<string, object>>(existingJson);
                if (existingResult != null && existingResult.ContainsKey("status") && existingResult["status"]?.ToString() == "SUCCESS")
                {
                    var dataStr = existingResult["data"]?.ToString() ?? "{}";
                    var data = JsonSerializer.Deserialize<Dictionary<string, object>>(dataStr);
                    if (data != null && data.ContainsKey("processingstatus"))
                    {
                        var procStatus = data["processingstatus"]?.ToString();
                        if (procStatus == "PROCESSED" || procStatus == "IRRELEVANT")
                        {
                            _logger.LogDebug("Message {MessageId} already processed, skipping", messageId);
                            return MessageProcessResult.ExistingProcessed;
                        }
                        _logger.LogInformation("Message {MessageId} has status {Status}, retrying", messageId, procStatus);
                        return MessageProcessResult.ExistingRetry;
                    }
                }
            }

            var message = await GetMessageAsync(messageId);
            if (message == null) { _logger.LogWarning("Could not fetch message {MessageId}", messageId); return MessageProcessResult.NewFailed; }

            var (identifiedGroup, identifiedEmail) = IdentifySourceGroup(message);
            var parsed = _preprocessor.ParseMessage(message, identifiedGroup, identifiedEmail);

            var messageUuid = SaveGmailMessage(parsed);
            if (string.IsNullOrEmpty(messageUuid)) { _logger.LogError("Failed to save Gmail message {MessageId}", messageId); return MessageProcessResult.NewFailed; }

            if (parsed.Attachments.Count > 0)
            {
                foreach (var attachment in parsed.Attachments)
                {
                    try
                    {
                        var attachmentData = await DownloadAttachmentAsync(messageId, attachment.AttachmentId);
                        if (attachmentData != null)
                        {
                            attachment.Data = attachmentData;
                            attachment.ExtractedText = await _attachmentProcessor.ExtractTextAsync(attachment);
                        }
                        SaveAttachment(messageUuid, attachment);
                    }
                    catch (Exception ex) { _logger.LogError(ex, "Failed to process attachment {AttachmentId}", attachment.AttachmentId); }
                }
            }

            var combinedContent = _preprocessor.BuildCombinedContent(parsed);
            var extraction = await _extractionService.ExtractAsync(combinedContent, parsed.Subject ?? "");

            if (!string.IsNullOrEmpty(identifiedGroup))
                extraction.Source = identifiedGroup;

            var validation = _validationService.Validate(extraction);

            string finalStatus;
            if (!extraction.IsRelevant)
            {
                finalStatus = "IRRELEVANT";
            }
            else if (!validation.IsValid)
            {
                finalStatus = "REVIEW_REQUIRED";
                extraction.ProcessingStatus = finalStatus;
                extraction.ValidationMessage = string.Join("; ", validation.Errors);
            }
            else
            {
                finalStatus = "PROCESSED";
                extraction.ProcessingStatus = finalStatus;
            }

            SaveExtraction(messageUuid, extraction);
            UpdateMessageStatus(messageUuid, finalStatus);

            _logger.LogInformation("Processed message {MessageId} - Category: {Category}, Status: {Status}", messageId, extraction.Category, finalStatus);

            if (finalStatus == "REVIEW_REQUIRED") return MessageProcessResult.NewReviewRequired;
            return MessageProcessResult.NewProcessed;
        }

        private async Task<byte[]?> DownloadAttachmentAsync(string messageId, string attachmentId)
        {
            var service = await GetGmailApiServiceAsync();
            try
            {
                var request = service.Users.Messages.Attachments.Get("me", messageId, attachmentId);
                var attachment = await ExecuteWithRetryAsync(() => request.ExecuteAsync());
                if (attachment?.Data != null)
                    return Convert.FromBase64String(attachment.Data.Replace('-', '+').Replace('_', '/'));
            }
            catch (Exception ex) { _logger.LogError(ex, "Failed to download attachment {AttachmentId}", attachmentId); }
            return null;
        }

        private string SaveGmailMessage(ParsedEmail parsed)
        {
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFNParam("fn_api_insert_gmailmessage_v001",
                    ("_gmailmessageid", (object)(parsed.GmailMessageId ?? "")),
                    ("_gmailthreadid", (object)"" ),
                    ("_sourcegroup", (object)(parsed.SourceGroup ?? "")),
                    ("_sourcegroupemail", (object)(parsed.SourceGroupEmail ?? "")),
                    ("_sender", (object)(parsed.Sender ?? "")),
                    ("_recipient", (object)(parsed.Recipient ?? "")),
                    ("_cc", (object)(parsed.Cc ?? "")),
                    ("_bcc", (object)(parsed.Bcc ?? "")),
                    ("_replyto", (object)(parsed.ReplyTo ?? "")),
                    ("_subject", (object)(parsed.Subject ?? "")),
                    ("_receivedat", (object)(parsed.ReceivedAt ?? "")),
                    ("_bodytext", (object)(parsed.BodyText ?? "")),
                    ("_bodyhtml", (object)(parsed.BodyHtml ?? "")),
                    ("_snippet", (object)(parsed.Snippet ?? "")),
                    ("_hasattachments", (object)parsed.HasAttachments),
                    ("_labelids", (object)(parsed.LabelIds ?? "")),
                    ("_rawpayload", (object)(parsed.RawPayload?.Substring(0, Math.Min(parsed.RawPayload.Length, 50000)) ?? "")));

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0]?.ToString() ?? "";
                    var result = JsonSerializer.Deserialize<Dictionary<string, object>>(json);
                    if (result != null && result.ContainsKey("status"))
                    {
                        var status = result["status"]?.ToString();
                        if (status == "SUCCESS")
                            return result["id"]?.ToString() ?? "";
                        else
                            _logger.LogWarning("DB function returned: {Status} - {Message}", status, result["message"]);
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception in SaveGmailMessage for {MessageId}", parsed.GmailMessageId);
            }
            return "";
        }

        private void SaveAttachment(string messageUuid, ParsedAttachment attachment)
        {
            _dataEntity.ExecuteDataTableFNParam("fn_api_insert_gmailattachment_v001",
                ("_sysgmailmessageuuid", (object)messageUuid),
                ("_gmailattachmentid", (object)(attachment.AttachmentId ?? "")),
                ("_filename", (object)(attachment.Filename ?? "")),
                ("_mimetype", (object)(attachment.MimeType ?? "")),
                ("_filesize", (object)attachment.FileSize),
                ("_filepath", (object)""),
                ("_extractedtext", (object)(attachment.ExtractedText?.Substring(0, Math.Min(attachment.ExtractedText.Length, 50000)) ?? "")));
        }

        private void SaveExtraction(string messageUuid, EmailExtractionResult extraction)
        {
            try
            {
                _dataEntity.ExecuteDataTableFNParam("fn_api_save_emailextraction_v001",
                    ("_sysgmailmessageuuid", (object)messageUuid),
                    ("_category", (object)(extraction.Category ?? "")),
                    ("_isrelevant", (object)extraction.IsRelevant),
                    ("_rejectionreason", (object)(extraction.RejectionReason ?? "")),
                    ("_title", (object)(extraction.Title ?? "")),
                    ("_content", (object)(extraction.Content ?? "")),
                    ("_source", (object)(extraction.Source ?? "")),
                    ("_company", (object)(extraction.Company ?? "")),
                    ("_role", (object)(extraction.Role ?? "")),
                    ("_packagelpa", (object)(extraction.PackageLpa ?? (decimal?)null ?? (object)DBNull.Value)),
                    ("_packagedetails", (object)(extraction.PackageDetails ?? "")),
                    ("_jobtype", (object)(extraction.JobType ?? "")),
                    ("_location", (object)(extraction.Location ?? "")),
                    ("_joiningdate", (object)(extraction.JoiningDate ?? "")),
                    ("_deadline", (object)(extraction.Deadline ?? "")),
                    ("_interviewdate", (object)(extraction.InterviewDate ?? "")),
                    ("_round", (object)(extraction.Round ?? "")),
                    ("_venue", (object)(extraction.Venue ?? "")),
                    ("_eventname", (object)(extraction.EventName ?? "")),
                    ("_topic", (object)(extraction.Topic ?? "")),
                    ("_speaker", (object)(extraction.Speaker ?? "")),
                    ("_startdate", (object)(extraction.StartDate ?? "")),
                    ("_enddate", (object)(extraction.EndDate ?? "")),
                    ("_registrationdeadline", (object)(extraction.RegistrationDeadline ?? "")),
                    ("_registrationlink", (object)(extraction.RegistrationLink ?? "")),
                    ("_prizepool", (object)(extraction.PrizePool ?? "")),
                    ("_teamsize", (object)(extraction.TeamSize ?? "")),
                    ("_organizer", (object)(extraction.Organizer ?? "")),
                    ("_eligibilitycriteria", (object)(extraction.EligibilityCriteria ?? "")),
                    ("_hiringflow", (object)(extraction.HiringFlow ?? "")),
                    ("_students", (object)(extraction.Students ?? "")),
                    ("_totalstudents", (object)extraction.TotalStudents),
                    ("_links", (object)(extraction.Links ?? "")),
                    ("_additionalinfo", (object)(extraction.AdditionalInfo ?? "")),
                    ("_processingstatus", (object)(extraction.ProcessingStatus ?? "")),
                    ("_validationmessage", (object)(extraction.ValidationMessage ?? "")));
                _logger.LogInformation("Extraction saved for message UUID {MessageUuid}", messageUuid);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to save extraction for {MessageUuid}", messageUuid);
            }
        }

        private void UpdateMessageStatus(string messageUuid, string newStatus)
        {
            try
            {
                _dataEntity.ExecuteDataTableFNParam("fn_api_update_gmailmessage_status_v001",
                    ("_messageuuid", (object)messageUuid),
                    ("_status", (object)newStatus));
            }
            catch (Exception ex) { _logger.LogError(ex, "Failed to update message status for {MessageUuid}", messageUuid); }
        }

        public Task<DataTable> GetMessagesAsync(int page = 1, int pageSize = 20, string sourceGroup = "", string status = "", string search = "")
        {
            return Task.FromResult(_dataEntity.ExecuteDataTableFN("fn_api_select_gmailmessages_v1", page, pageSize, sourceGroup, status, search));
        }

        public Task<object?> GetMessageDetailAsync(string messageId)
        {
            DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_select_gmailmessage_v1", messageId);
            if (dt.Rows.Count > 0)
            {
                string json = dt.Rows[0][0].ToString() ?? "";
                return Task.FromResult<object?>(Common.ParseJson(json));
            }
            return Task.FromResult<object?>(null);
        }

        public async Task<List<object>> GetThreadMessagesAsync(string threadId)
        {
            try
            {
                var service = await GetGmailApiServiceAsync();
                var thread = await service.Users.Threads.Get("me", threadId).ExecuteAsync();
                var messages = new List<object>();
                if (thread.Messages != null)
                {
                    foreach (var msg in thread.Messages)
                        messages.Add(new { Id = msg.Id, ThreadId = msg.ThreadId, Snippet = msg.Snippet });
                }
                return messages;
            }
            catch (Exception ex) { _logger.LogError(ex, "Failed to fetch thread {ThreadId}", threadId); return new List<object>(); }
        }

        public async Task<bool> ReprocessMessageAsync(string messageId)
        {
            DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_select_gmailmessage_v1", messageId);
            if (dt.Rows.Count == 0) return false;

            string json = dt.Rows[0][0].ToString() ?? "";
            var result = JsonSerializer.Deserialize<Dictionary<string, object>>(json);
            if (result == null || result["status"]?.ToString() != "SUCCESS") return false;

            var data = JsonSerializer.Deserialize<Dictionary<string, object>>(result["data"]?.ToString() ?? "{}");
            if (data == null) return false;

            var sourceGroupEmail = data["sourcegroupemail"]?.ToString() ?? "";
            var sourceGroup = data["sourcegroup"]?.ToString() ?? "";

            var groupConfig = _gmailSettings.SourceGroups?.FirstOrDefault(g => g.Email == sourceGroupEmail)
                ?? new SourceGroup { Name = sourceGroup, Email = sourceGroupEmail };

            var procResult = await ProcessMessageAsync(messageId, groupConfig);
            return procResult != MessageProcessResult.NewFailed;
        }

        private async Task<T> ExecuteWithRetryAsync<T>(Func<Task<T>> operation, int maxRetries = 3)
        {
            for (int i = 0; i <= maxRetries; i++)
            {
                try { return await operation(); }
                catch (Exception ex) when (i < maxRetries && IsTransient(ex))
                {
                    _logger.LogWarning(ex, "Transient error, retrying ({Attempt}/{MaxRetries})", i + 1, maxRetries);
                    await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, i)));
                }
            }
            return await operation();
        }

        private bool IsTransient(Exception ex)
        {
            if (ex is HttpRequestException || ex is TaskCanceledException || ex is IOException) return true;
            // Check for HTTP error status codes in the message
            var msg = ex.Message?.ToLowerInvariant() ?? "";
            if (msg.Contains("429") || msg.Contains("500") || msg.Contains("503") ||
                msg.Contains("too many requests") || msg.Contains("server error") ||
                msg.Contains("service unavailable")) return true;
            return false;
        }

        private string ExtractIdFromJson(string json)
        {
            try
            {
                var result = JsonSerializer.Deserialize<Dictionary<string, object>>(json);
                if (result != null && result.ContainsKey("id")) return result["id"]?.ToString() ?? "";
            } catch { }
            return "";
        }
    }

    internal enum MessageProcessResult
    {
        NewProcessed, NewReviewRequired, NewFailed, ExistingProcessed, ExistingRetry
    }
}
