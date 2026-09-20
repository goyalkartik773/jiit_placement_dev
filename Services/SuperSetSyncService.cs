using JIITPlacement.Models.App_Code;
using JIITPlacement.Models.SuperSet;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services;

public class SuperSetSyncService : ISuperSetSyncService
{
    private readonly ISuperSetService _superSetService;
    private readonly AppDbContext _dbContext;
    private readonly SuperSetOptions _options;
    private readonly ILogger<SuperSetSyncService> _logger;

    public SuperSetSyncService(
        ISuperSetService superSetService,
        AppDbContext dbContext,
        IOptions<SuperSetOptions> options,
        ILogger<SuperSetSyncService> logger)
    {
        _superSetService = superSetService;
        _dbContext = dbContext;
        _options = options.Value;
        _logger = logger;
    }

    public async Task<SyncResult> SyncNoticesAsync()
    {
        _logger.LogInformation("Starting notices synchronization");

        try
        {
            var loginResponse = await _superSetService.LoginAsync(_options.Username, _options.Password);
            var superSetNotices = await _superSetService.GetNoticesAsync(loginResponse.Uuid, loginResponse.SessionKey);

            var result = new SyncResult { Fetched = superSetNotices.Count };

            foreach (var notice in superSetNotices)
            {
                try
                {
                    var existing = await _dbContext.Notices
                        .FirstOrDefaultAsync(n => n.SuperSetIdentifier == notice.Identifier);

                    if (existing != null)
                    {
                        existing.Title = notice.Title;
                        existing.Content = notice.Content;
                        existing.Author = notice.LastModifiedByUserName;
                        existing.CreatedAt = notice.PublishedAt.HasValue
                            ? DateTimeOffset.FromUnixTimeMilliseconds(notice.PublishedAt.Value).UtcDateTime
                            : null;
                        existing.UpdatedAt = notice.LastModifiedOn.HasValue
                            ? DateTimeOffset.FromUnixTimeMilliseconds(notice.LastModifiedOn.Value).UtcDateTime
                            : null;
                        existing.updateddatetime = DateTime.UtcNow;

                        result.Updated++;
                    }
                    else
                    {
                        var newNotice = new NoticeRecord
                        {
                            SuperSetIdentifier = notice.Identifier,
                            Title = notice.Title,
                            Content = notice.Content,
                            Author = notice.LastModifiedByUserName,
                            CreatedAt = notice.PublishedAt.HasValue
                                ? DateTimeOffset.FromUnixTimeMilliseconds(notice.PublishedAt.Value).UtcDateTime
                                : null,
                            UpdatedAt = notice.LastModifiedOn.HasValue
                                ? DateTimeOffset.FromUnixTimeMilliseconds(notice.LastModifiedOn.Value).UtcDateTime
                                : null,
                            posteddatetime = DateTime.UtcNow
                        };

                        _dbContext.Notices.Add(newNotice);
                        result.Inserted++;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error processing notice {Identifier}", notice.Identifier);
                    result.Failed++;
                }
            }

            await _dbContext.SaveChangesAsync();

            result.Success = true;
            result.Message = $"Notices sync completed: {result.Inserted} inserted, {result.Updated} updated, {result.Failed} failed";

            _logger.LogInformation("Notices synchronization completed: {Inserted} inserted, {Updated} updated, {Failed} failed",
                result.Inserted, result.Updated, result.Failed);

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Notices synchronization failed");
            return new SyncResult
            {
                Success = false,
                Message = $"Notices sync failed: {ex.Message}",
                Fetched = 0,
                Inserted = 0,
                Updated = 0,
                Failed = 0
            };
        }
    }

    public async Task<SyncResult> SyncJobsAsync()
    {
        _logger.LogInformation("Starting jobs synchronization");

        try
        {
            var loginResponse = await _superSetService.LoginAsync(_options.Username, _options.Password);
            var basicJobs = await _superSetService.GetJobListingsBasicAsync(loginResponse.Uuid, loginResponse.SessionKey);

            var result = new SyncResult { Fetched = basicJobs.Count };

            var existingJobIds = await _dbContext.Jobs
                .Select(j => j.SuperSetJobIdentifier)
                .ToHashSetAsync();

            var newJobs = basicJobs.Where(j => !existingJobIds.Contains(j.JobProfileIdentifier)).ToList();

            _logger.LogInformation("Found {NewCount} new jobs out of {TotalCount} total", newJobs.Count, basicJobs.Count);

            foreach (var basicJob in newJobs)
            {
                try
                {
                    var jobDetail = await _superSetService.GetJobDetailsAsync(
                        loginResponse.Uuid,
                        loginResponse.SessionKey,
                        basicJob.JobProfileIdentifier);

                    var structuredJob = StructureJob(basicJob, jobDetail);

                    foreach (var doc in structuredJob.Documents)
                    {
                        if (!string.IsNullOrEmpty(doc.Identifier))
                        {
                            doc.Url = await _superSetService.GetDocumentUrlAsync(
                                loginResponse.Uuid,
                                loginResponse.SessionKey,
                                structuredJob.Id,
                                doc.Identifier);
                        }
                    }

                    await SaveJobToDatabaseAsync(structuredJob);
                    result.Inserted++;
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error processing job {JobId}", basicJob.JobProfileIdentifier);
                    result.Failed++;
                }
            }

            await _dbContext.SaveChangesAsync();

            result.Success = true;
            result.Message = $"Jobs sync completed: {result.Inserted} inserted, {result.Failed} failed";

            _logger.LogInformation("Jobs synchronization completed: {Inserted} inserted, {Failed} failed",
                result.Inserted, result.Failed);

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Jobs synchronization failed");
            return new SyncResult
            {
                Success = false,
                Message = $"Jobs sync failed: {ex.Message}",
                Fetched = 0,
                Inserted = 0,
                Updated = 0,
                Failed = 0
            };
        }
    }

    private StructuredJob StructureJob(SuperSetJobBasicDto basicJob, SuperSetJobDetailDto? jobDetail)
    {
        var categoryMapping = new Dictionary<int, string>
        {
            { 1, "High" },
            { 2, "Middle" },
            { 3, "Offer is more than 4.6 lacs" },
            { 4, "Internship" }
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
            var jobDetails = jobDetail;

            if (jobDetails.EligibilityCheckResult?.AcademicResults != null)
            {
                foreach (var r in jobDetails.EligibilityCheckResult.AcademicResults)
                {
                    structured.EligibilityMarks.Add(new EligibilityMark
                    {
                        Level = r.Level,
                        Criteria = r.Required
                    });
                }
            }

            if (jobDetails.EligibilityCheckResult?.CourseCheckResult?.OpenedForCourses != null)
            {
                foreach (var course in jobDetails.EligibilityCheckResult.CourseCheckResult.OpenedForCourses)
                {
                    if (course.Program != null && !string.IsNullOrEmpty(course.Name))
                    {
                        structured.EligibilityCourses.Add($"{course.Program.ShortName} - {course.Name}");
                    }
                    else if (!string.IsNullOrEmpty(course.Name))
                    {
                        structured.EligibilityCourses.Add($"Unknown - {course.Name}");
                    }
                }
            }

            if (jobDetails.JobProfile != null)
            {
                var profile = jobDetails.JobProfile;

                if (profile.AllowGenderFemale) structured.AllowedGenders.Add("Female");
                if (profile.AllowGenderMale) structured.AllowedGenders.Add("Male");
                if (profile.AllowGenderOther) structured.AllowedGenders.Add("Other");

                if (!string.IsNullOrEmpty(profile.JobDescription))
                {
                    structured.JobDescription = profile.JobDescription + (profile.InvitationCustomText ?? "");
                }

                if (!string.IsNullOrEmpty(profile.Location))
                    structured.Location = profile.Location;

                if (profile.Package.HasValue && profile.Package.Value > 0)
                    structured.Package = profile.Package.Value;
                else if (profile.CtcMin.HasValue && profile.CtcMin.Value > 0)
                    structured.Package = profile.CtcMin.Value;
                else if (profile.CtcMax.HasValue && profile.CtcMax.Value > 0)
                    structured.Package = profile.CtcMax.Value;

                if (!string.IsNullOrEmpty(profile.CtcAdditionalInfo))
                    structured.PackageInfo = profile.CtcAdditionalInfo;

                structured.AnnumMonths = profile.CtcInterval;

                if (profile.RequiredSkills != null)
                    structured.RequiredSkills.AddRange(profile.RequiredSkills);

                if (profile.Stages != null && profile.Stages.Any())
                {
                    var maxSeq = profile.Stages.Max(s => s.Sequence);
                    structured.HiringFlow = new List<string>(new string[maxSeq]);
                    foreach (var stage in profile.Stages)
                    {
                        if (stage.Sequence - 1 < structured.HiringFlow.Count)
                            structured.HiringFlow[stage.Sequence - 1] = stage.Name;
                    }
                }

                if (profile.Documents != null)
                {
                    foreach (var doc in profile.Documents)
                    {
                        if (!string.IsNullOrEmpty(doc.Name) && !string.IsNullOrEmpty(doc.Identifier))
                        {
                            structured.Documents.Add(new StructuredDocument
                            {
                                Name = doc.Name,
                                Identifier = doc.Identifier
                            });
                        }
                    }
                }
            }

            if (structured.Location == "Unknown" && !string.IsNullOrEmpty(jobDetails.JobProfileLocation))
            {
                structured.Location = jobDetails.JobProfileLocation;
            }

            structured.PlacementType = jobDetails.PositionType;
        }

        return structured;
    }

    private async Task SaveJobToDatabaseAsync(StructuredJob job)
    {
        // Save parent job record first
        var jobRecord = new JobRecord
        {
            SuperSetJobIdentifier = job.Id,
            Company = job.Company,
            JobProfile = job.JobProfile,
            PlacementCategory = job.PlacementCategory,
            PlacementCategoryCode = job.PlacementCategoryCode.ToString(),
            Content = job.Content,
            CreatedAt = job.CreatedAt.HasValue
                ? DateTimeOffset.FromUnixTimeMilliseconds(job.CreatedAt.Value).UtcDateTime
                : null,
            Deadline = job.Deadline.HasValue
                ? DateTimeOffset.FromUnixTimeMilliseconds(job.Deadline.Value).UtcDateTime
                : null,
            Location = job.Location,
            Package = job.Package,
            PackageInfo = job.PackageInfo,
            JobDescription = job.JobDescription,
            PlacementType = job.PlacementType ?? string.Empty,
            posteddatetime = DateTime.UtcNow
        };

        _dbContext.Jobs.Add(jobRecord);
        await _dbContext.SaveChangesAsync(); // Save to get the Id

        // Now save child records with SysJobUuid = jobRecord.Id
        var jobId = jobRecord.Id;
        var now = DateTime.UtcNow;

        // Eligibility marks
        foreach (var mark in job.EligibilityMarks)
        {
            _dbContext.JobEligibilities.Add(new JobEligibilityRecord
            {
                SysJobUuid = jobId,
                Level = mark.Level,
                Criteria = mark.Criteria.ToString(),
                posteddatetime = now
            });
        }

        // Eligibility courses
        foreach (var course in job.EligibilityCourses)
        {
            _dbContext.JobEligibilityCourses.Add(new JobEligibilityCourseRecord
            {
                SysJobUuid = jobId,
                CourseName = course,
                posteddatetime = now
            });
        }

        // Genders
        foreach (var gender in job.AllowedGenders)
        {
            _dbContext.JobGenders.Add(new JobGenderRecord
            {
                SysJobUuid = jobId,
                Gender = gender,
                posteddatetime = now
            });
        }

        // Skills
        foreach (var skill in job.RequiredSkills)
        {
            _dbContext.JobSkills.Add(new JobSkillRecord
            {
                SysJobUuid = jobId,
                SkillName = skill,
                posteddatetime = now
            });
        }

        // Hiring flow
        for (int i = 0; i < job.HiringFlow.Count; i++)
        {
            if (!string.IsNullOrEmpty(job.HiringFlow[i]))
            {
                _dbContext.JobHiringFlows.Add(new JobHiringFlowRecord
                {
                    SysJobUuid = jobId,
                    Sequence = (i + 1).ToString(),
                    StageName = job.HiringFlow[i],
                    posteddatetime = now
                });
            }
        }

        // Documents
        foreach (var doc in job.Documents)
        {
            _dbContext.JobDocuments.Add(new JobDocumentRecord
            {
                SysJobUuid = jobId,
                DocumentIdentifier = doc.Identifier,
                DocumentName = doc.Name,
                DocumentUrl = doc.Url ?? string.Empty,
                posteddatetime = now
            });
        }

        await _dbContext.SaveChangesAsync(); // Save all child records
    }
}
