using System.Data;
using System.Diagnostics;
using System.Text.Json;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public class SuperSetSyncService : ISuperSetSyncService
    {
        private readonly ISuperSetService _superSetService;
        private readonly DataEntity _dataEntity;
        private readonly SuperSetOptions _options;
        private readonly ILogger<SuperSetSyncService> _logger;

        public SuperSetSyncService(
            ISuperSetService superSetService,
            DataEntity dataEntity,
            IOptions<SuperSetOptions> options,
            ILogger<SuperSetSyncService> logger)
        {
            _superSetService = superSetService;
            _dataEntity = dataEntity;
            _options = options.Value;
            _logger = logger;
        }

        /// <summary>
        /// Admin endpoint: sync both jobs and notices with a single SuperSet login.
        /// </summary>
        public async Task<SyncResult> SyncAllAsync(bool syncJobs, bool syncNotices)
        {
            if (!syncJobs && !syncNotices)
            {
                return new SyncResult
                {
                    Success = false,
                    Message = "At least one of syncJobs or syncNotices must be true"
                };
            }

            _logger.LogInformation(
                "Admin sync started - SyncJobs: {SyncJobs}, SyncNotices: {SyncNotices}",
                syncJobs, syncNotices);

            var stopwatch = Stopwatch.StartNew();

            try
            {
                // Single login for both sync operations
                _logger.LogInformation("Authenticating with SuperSet...");
                var loginResponse = await _superSetService.LoginAsync(_options.Username, _options.Password);
                _logger.LogInformation("SuperSet authentication successful");

                var combinedResult = new SyncResult();

                if (syncNotices)
                {
                    _logger.LogInformation("Starting notices synchronization...");
                    var noticeResult = await SyncNoticesInternalAsync(loginResponse);
                    combinedResult.Fetched += noticeResult.Fetched;
                    combinedResult.Inserted += noticeResult.Inserted;
                    combinedResult.Updated += noticeResult.Updated;
                    combinedResult.Failed += noticeResult.Failed;
                    _logger.LogInformation(
                        "Notices sync completed: {Fetched} fetched, {Inserted} inserted, {Updated} updated, {Failed} failed",
                        noticeResult.Fetched, noticeResult.Inserted, noticeResult.Updated, noticeResult.Failed);
                }

                if (syncJobs)
                {
                    _logger.LogInformation("Starting jobs synchronization...");
                    var jobResult = await SyncJobsInternalAsync(loginResponse);
                    combinedResult.Fetched += jobResult.Fetched;
                    combinedResult.Inserted += jobResult.Inserted;
                    combinedResult.Updated += jobResult.Updated;
                    combinedResult.Failed += jobResult.Failed;
                    _logger.LogInformation(
                        "Jobs sync completed: {Fetched} fetched, {Inserted} inserted, {Updated} updated, {Failed} failed",
                        jobResult.Fetched, jobResult.Inserted, jobResult.Updated, jobResult.Failed);
                }

                stopwatch.Stop();
                combinedResult.Success = true;
                combinedResult.Message = $"Sync completed in {stopwatch.Elapsed.TotalSeconds:F1}s";

                _logger.LogInformation(
                    "Admin sync finished - Total: {Fetched} fetched, {Inserted} inserted, {Updated} updated, {Failed} failed, Duration: {Duration:F1}s",
                    combinedResult.Fetched, combinedResult.Inserted, combinedResult.Updated, combinedResult.Failed,
                    stopwatch.Elapsed.TotalSeconds);

                return combinedResult;
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "Admin sync failed after {Duration:F1}s", stopwatch.Elapsed.TotalSeconds);
                return new SyncResult
                {
                    Success = false,
                    Message = $"Sync failed after {stopwatch.Elapsed.TotalSeconds:F1}s: {ex.Message}"
                };
            }
        }

        public async Task<SyncResult> SyncNoticesAsync()
        {
            _logger.LogInformation("Starting notices synchronization");

            try
            {
                var loginResponse = await _superSetService.LoginAsync(_options.Username, _options.Password);
                return await SyncNoticesInternalAsync(loginResponse);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Notices synchronization failed");
                return new SyncResult { Success = false, Message = $"Notices sync failed: {ex.Message}" };
            }
        }

        public async Task<SyncResult> SyncJobsAsync()
        {
            _logger.LogInformation("Starting jobs synchronization");

            try
            {
                var loginResponse = await _superSetService.LoginAsync(_options.Username, _options.Password);
                return await SyncJobsInternalAsync(loginResponse);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Jobs synchronization failed");
                return new SyncResult { Success = false, Message = $"Jobs sync failed: {ex.Message}" };
            }
        }

        private async Task<SyncResult> SyncNoticesInternalAsync(SuperSetLoginResponse loginResponse)
        {
            _logger.LogInformation("Fetching notices from SuperSet...");

            var superSetNotices = await _superSetService.GetNoticesAsync(loginResponse.Uuid, loginResponse.SessionKey);
            var result = new SyncResult { Fetched = superSetNotices.Count };

            _logger.LogInformation("Fetched {Count} notices from SuperSet", superSetNotices.Count);

            foreach (var notice in superSetNotices)
            {
                try
                {
                    _logger.LogDebug("Processing notice: {Identifier} - {Title}", notice.Identifier, notice.Title);

                    string createdAt = notice.PublishedAt.HasValue
                        ? DateTimeOffset.FromUnixTimeMilliseconds(notice.PublishedAt.Value).UtcDateTime.ToString("o")
                        : string.Empty;
                    string updatedAt = notice.LastModifiedOn.HasValue
                        ? DateTimeOffset.FromUnixTimeMilliseconds(notice.LastModifiedOn.Value).UtcDateTime.ToString("o")
                        : string.Empty;

                    DataTable dt = _dataEntity.ExecuteDataTableFN(
                        "fn_api_post_notice_v001",
                        notice.Identifier,
                        notice.Title,
                        notice.Content,
                        notice.LastModifiedByUserName,
                        createdAt,
                        updatedAt,
                        _options.Username
                    );

                    string fnResult = dt.Rows[0][0].ToString();
                    var json = Common.ParseJson(fnResult);
                    if (json.TryGetProperty("status", out var s) && s.GetString() == "SUCCESS")
                    {
                        if (fnResult.Contains("created"))
                            result.Inserted++;
                        else
                            result.Updated++;
                    }
                    else
                    {
                        result.Failed++;
                        _logger.LogWarning("Notice {Identifier} save returned non-success: {Result}", notice.Identifier, fnResult);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error processing notice {Identifier}", notice.Identifier);
                    result.Failed++;
                }
            }

            return result;
        }

        private async Task<SyncResult> SyncJobsInternalAsync(SuperSetLoginResponse loginResponse)
        {
            _logger.LogInformation("Fetching job listings from SuperSet...");

            var basicJobs = await _superSetService.GetJobListingsBasicAsync(loginResponse.Uuid, loginResponse.SessionKey);
            var result = new SyncResult { Fetched = basicJobs.Count };

            _logger.LogInformation("Fetched {Count} job listings from SuperSet", basicJobs.Count);

            int processedCount = 0;
            foreach (var basicJob in basicJobs)
            {
                processedCount++;
                try
                {
                    _logger.LogInformation(
                        "Processing job {Current}/{Total}: {JobId} - {Company} - {Title}",
                        processedCount, basicJobs.Count,
                        basicJob.JobProfileIdentifier, basicJob.CompanyName, basicJob.JobProfileTitle);

                    var jobDetail = await _superSetService.GetJobDetailsAsync(
                        loginResponse.Uuid, loginResponse.SessionKey, basicJob.JobProfileIdentifier);

                    var structuredJob = StructureJob(basicJob, jobDetail);

                    foreach (var doc in structuredJob.Documents)
                    {
                        if (!string.IsNullOrEmpty(doc.Identifier))
                        {
                            doc.Url = await _superSetService.GetDocumentUrlAsync(
                                loginResponse.Uuid, loginResponse.SessionKey,
                                structuredJob.Id, doc.Identifier);
                        }
                    }

                    var jobSaveResult = await SaveJobViaFunctionAsync(structuredJob);
                    if (jobSaveResult == "created")
                        result.Inserted++;
                    else
                        result.Updated++;
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error processing job {JobId}", basicJob.JobProfileIdentifier);
                    result.Failed++;
                }
            }

            return result;
        }

        private StructuredJob StructureJob(SuperSetJobBasicDto basicJob, SuperSetJobDetailDto? jobDetail)
        {
            var categoryMapping = new Dictionary<int, string>
            {
                { 1, "High" }, { 2, "Middle" },
                { 3, "Offer is more than 4.6 lacs" }, { 4, "Internship" }
            };

            var structured = new StructuredJob
            {
                Id = basicJob.JobProfileIdentifier,
                JobProfile = basicJob.JobProfileTitle ?? "Unknown",
                Company = basicJob.CompanyName ?? "??",
                PlacementCategoryCode = basicJob.PlacementCategoryLevel,
                PlacementCategory = basicJob.PlacementCategoryName
                    ?? categoryMapping.GetValueOrDefault(basicJob.PlacementCategoryLevel, "Unknown"),
                Content = basicJob.Content ?? string.Empty,
                CreatedAt = basicJob.CreatedAt,
                Deadline = basicJob.JobProfileApplicationDeadline,
                Location = "Unknown",
                Package = 0,
                PackageInfo = string.Empty,
                JobDescription = string.Empty
            };

            if (jobDetail != null)
            {
                if (jobDetail.EligibilityCheckResult?.AcademicResults != null)
                {
                    foreach (var r in jobDetail.EligibilityCheckResult.AcademicResults)
                        structured.EligibilityMarks.Add(new EligibilityMark { Level = r.Level, Criteria = r.Required });
                }

                if (jobDetail.EligibilityCheckResult?.CourseCheckResult?.OpenedForCourses != null)
                {
                    foreach (var course in jobDetail.EligibilityCheckResult.CourseCheckResult.OpenedForCourses)
                    {
                        if (course.Program != null && !string.IsNullOrEmpty(course.Name))
                            structured.EligibilityCourses.Add($"{course.Program.ShortName} - {course.Name}");
                        else if (!string.IsNullOrEmpty(course.Name))
                            structured.EligibilityCourses.Add($"Unknown - {course.Name}");
                    }
                }

                if (jobDetail.JobProfile != null)
                {
                    var profile = jobDetail.JobProfile;
                    if (profile.AllowGenderFemale) structured.AllowedGenders.Add("Female");
                    if (profile.AllowGenderMale) structured.AllowedGenders.Add("Male");
                    if (profile.AllowGenderOther) structured.AllowedGenders.Add("Other");

                    if (!string.IsNullOrEmpty(profile.JobDescription))
                        structured.JobDescription = profile.JobDescription + (profile.InvitationCustomText ?? "");

                    if (!string.IsNullOrEmpty(profile.Location)) structured.Location = profile.Location;

                    if (profile.Package.HasValue && profile.Package.Value > 0) structured.Package = profile.Package.Value;
                    else if (profile.CtcMin.HasValue && profile.CtcMin.Value > 0) structured.Package = profile.CtcMin.Value;
                    else if (profile.CtcMax.HasValue && profile.CtcMax.Value > 0) structured.Package = profile.CtcMax.Value;

                    if (!string.IsNullOrEmpty(profile.CtcAdditionalInfo)) structured.PackageInfo = profile.CtcAdditionalInfo;
                    structured.AnnumMonths = profile.CtcInterval;

                    if (profile.RequiredSkills != null) structured.RequiredSkills.AddRange(profile.RequiredSkills);

                    if (profile.Stages != null && profile.Stages.Any())
                    {
                        var maxSeq = profile.Stages.Max(s => s.Sequence);
                        structured.HiringFlow = new List<string>(new string[maxSeq]);
                        foreach (var stage in profile.Stages)
                            if (stage.Sequence - 1 < structured.HiringFlow.Count)
                                structured.HiringFlow[stage.Sequence - 1] = stage.Name;
                    }

                    if (profile.Documents != null)
                    {
                        foreach (var doc in profile.Documents)
                            if (!string.IsNullOrEmpty(doc.Name) && !string.IsNullOrEmpty(doc.Identifier))
                                structured.Documents.Add(new StructuredDocument { Name = doc.Name, Identifier = doc.Identifier });
                    }
                }

                if (structured.Location == "Unknown" && !string.IsNullOrEmpty(jobDetail.JobProfileLocation))
                    structured.Location = jobDetail.JobProfileLocation;

                structured.PlacementType = jobDetail.PositionType;
            }

            return structured;
        }

        private async Task<string> SaveJobViaFunctionAsync(StructuredJob job)
        {
            // 1. Save main job
            DataTable jobDt = await _dataEntity.ExecuteDataTableFNAsync(
                "fn_api_post_job_v001",
                string.Empty,
                job.Id,
                job.Company,
                job.JobProfile,
                job.PlacementCategory,
                job.PlacementCategoryCode.ToString(),
                job.Content,
                job.CreatedAt.HasValue ? DateTimeOffset.FromUnixTimeMilliseconds(job.CreatedAt.Value).UtcDateTime.ToString("o") : string.Empty,
                job.Deadline.HasValue ? DateTimeOffset.FromUnixTimeMilliseconds(job.Deadline.Value).UtcDateTime.ToString("o") : string.Empty,
                job.Location,
                (decimal)job.Package,
                job.PackageInfo,
                job.JobDescription,
                job.PlacementType ?? string.Empty
            );

            string jobResult = jobDt.Rows[0][0].ToString();
            var jobJson = Common.ParseJson(jobResult);
            if (!jobJson.TryGetProperty("id", out var idProp))
            {
                _logger.LogWarning("Failed to get job ID from function result: {Result}", jobResult);
                return "failed";
            }
            string jobUuid = idProp.GetString() ?? string.Empty;
            string action = jobResult.Contains("created") ? "created" : "updated";

            // 2. Save eligibility marks
            foreach (var mark in job.EligibilityMarks)
            {
                await _dataEntity.ExecuteDataTableFNAsync(
                    "fn_api_post_jobeligibility_v001",
                    jobUuid, mark.Level, mark.Criteria.ToString()
                );
            }

            // 3. Save eligibility courses
            foreach (var course in job.EligibilityCourses)
            {
                await _dataEntity.ExecuteDataTableFNAsync(
                    "fn_api_post_jobeligibilitycourse_v001",
                    jobUuid, course
                );
            }

            // 4. Save genders
            foreach (var gender in job.AllowedGenders)
            {
                await _dataEntity.ExecuteDataTableFNAsync(
                    "fn_api_post_jobgender_v001",
                    jobUuid, gender
                );
            }

            // 5. Save skills
            foreach (var skill in job.RequiredSkills)
            {
                await _dataEntity.ExecuteDataTableFNAsync(
                    "fn_api_post_jobskill_v001",
                    jobUuid, skill
                );
            }

            // 6. Save hiring flow
            for (int i = 0; i < job.HiringFlow.Count; i++)
            {
                if (!string.IsNullOrEmpty(job.HiringFlow[i]))
                {
                    await _dataEntity.ExecuteDataTableFNAsync(
                        "fn_api_post_jobhiringflow_v001",
                        jobUuid, (i + 1).ToString(), job.HiringFlow[i]
                    );
                }
            }

            // 7. Save documents
            foreach (var doc in job.Documents)
            {
                await _dataEntity.ExecuteDataTableFNAsync(
                    "fn_api_post_jobdocument_v001",
                    jobUuid, doc.Identifier, doc.Name, doc.Url ?? string.Empty
                );
            }

            return action;
        }
    }
}
