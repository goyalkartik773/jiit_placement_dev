using JIITPlacement.Models.App_Code;
using JIITPlacement.Models.Jobs;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JIITPlacement.Controllers;

[ApiController]
[Route("api")]
public class JobController : ControllerBase
{
    private readonly AppDbContext _dbContext;
    private readonly ILogger<JobController> _logger;

    public JobController(AppDbContext dbContext, ILogger<JobController> logger)
    {
        _dbContext = dbContext;
        _logger = logger;
    }

    /// <summary>
    /// Get jobs from local PostgreSQL database
    /// </summary>
    [HttpGet("jobs")]
    [ProducesResponseType(typeof(ApiResponse<PaginatedResponse<JobResponse>>), 200)]
    public async Task<ActionResult<ApiResponse<PaginatedResponse<JobResponse>>>> GetJobs(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? company = null)
    {
        pageSize = Math.Min(pageSize, 100);

        var query = _dbContext.Jobs.AsQueryable();

        if (!string.IsNullOrEmpty(company))
        {
            query = query.Where(j => j.Company.Contains(company));
        }

        var totalCount = await query.CountAsync();

        var jobs = await query
            .OrderByDescending(j => j.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        // Get job IDs for batch loading child data
        var jobIds = jobs.Select(j => j.Id).ToList();

        // Load child data in batches
        var eligibilities = await _dbContext.JobEligibilities
            .Where(e => jobIds.Contains(e.SysJobUuid))
            .ToListAsync();

        var courses = await _dbContext.JobEligibilityCourses
            .Where(c => jobIds.Contains(c.SysJobUuid))
            .ToListAsync();

        var genders = await _dbContext.JobGenders
            .Where(g => jobIds.Contains(g.SysJobUuid))
            .ToListAsync();

        var skills = await _dbContext.JobSkills
            .Where(s => jobIds.Contains(s.SysJobUuid))
            .ToListAsync();

        var hiringFlows = await _dbContext.JobHiringFlows
            .Where(h => jobIds.Contains(h.SysJobUuid))
            .ToListAsync();

        var documents = await _dbContext.JobDocuments
            .Where(d => jobIds.Contains(d.SysJobUuid))
            .ToListAsync();

        var response = new PaginatedResponse<JobResponse>
        {
            Items = jobs.Select(j => new JobResponse
            {
                Id = j.Id,
                SuperSetJobIdentifier = j.SuperSetJobIdentifier,
                Company = j.Company,
                JobProfile = j.JobProfile,
                PlacementCategory = j.PlacementCategory,
                PlacementCategoryCode = j.PlacementCategoryCode,
                Content = j.Content,
                CreatedAt = j.CreatedAt,
                Deadline = j.Deadline,
                Location = j.Location,
                Package = j.Package,
                PackageInfo = j.PackageInfo,
                JobDescription = j.JobDescription,
                PlacementType = j.PlacementType,
                Status = j.Status,
                posteddatetime = j.posteddatetime,
                updateddatetime = j.updateddatetime,
                EligibilityMarks = eligibilities
                    .Where(e => e.SysJobUuid == j.Id)
                    .Select(e => new JobEligibilityResponse
                    {
                        Level = e.Level,
                        Criteria = e.Criteria
                    }).ToList(),
                Documents = documents
                    .Where(d => d.SysJobUuid == j.Id)
                    .Select(d => new JobDocumentResponse
                    {
                        DocumentIdentifier = d.DocumentIdentifier,
                        DocumentName = d.DocumentName,
                        DocumentUrl = d.DocumentUrl
                    }).ToList()
            }).ToList(),
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };

        return Ok(ApiResponse<PaginatedResponse<JobResponse>>.Ok(response));
    }

    /// <summary>
    /// Get a specific job by ID (UUID string or SuperSet identifier)
    /// </summary>
    [HttpGet("jobs/{id}")]
    [ProducesResponseType(typeof(ApiResponse<JobResponse>), 200)]
    [ProducesResponseType(typeof(ApiResponse<JobResponse>), 404)]
    public async Task<ActionResult<ApiResponse<JobResponse>>> GetJob(string id)
    {
        var job = await _dbContext.Jobs
            .FirstOrDefaultAsync(j => j.Id == id || j.SuperSetJobIdentifier == id);

        if (job == null)
            return NotFound(ApiResponse<JobResponse>.Fail("Job not found"));

        // Load all child data via SysJobUuid
        var jobId = job.Id;

        var eligibilityMarks = await _dbContext.JobEligibilities
            .Where(e => e.SysJobUuid == jobId)
            .ToListAsync();

        var eligibilityCourses = await _dbContext.JobEligibilityCourses
            .Where(c => c.SysJobUuid == jobId)
            .ToListAsync();

        var allowedGenders = await _dbContext.JobGenders
            .Where(g => g.SysJobUuid == jobId)
            .ToListAsync();

        var requiredSkills = await _dbContext.JobSkills
            .Where(s => s.SysJobUuid == jobId)
            .ToListAsync();

        var hiringFlow = await _dbContext.JobHiringFlows
            .Where(h => h.SysJobUuid == jobId)
            .ToListAsync();

        var jobDocuments = await _dbContext.JobDocuments
            .Where(d => d.SysJobUuid == jobId)
            .ToListAsync();

        var response = new JobResponse
        {
            Id = job.Id,
            SuperSetJobIdentifier = job.SuperSetJobIdentifier,
            Company = job.Company,
            JobProfile = job.JobProfile,
            PlacementCategory = job.PlacementCategory,
            PlacementCategoryCode = job.PlacementCategoryCode,
            Content = job.Content,
            CreatedAt = job.CreatedAt,
            Deadline = job.Deadline,
            Location = job.Location,
            Package = job.Package,
            PackageInfo = job.PackageInfo,
            JobDescription = job.JobDescription,
            PlacementType = job.PlacementType,
            Status = job.Status,
            posteddatetime = job.posteddatetime,
            updateddatetime = job.updateddatetime,
            EligibilityMarks = eligibilityMarks.Select(e => new JobEligibilityResponse
            {
                Level = e.Level,
                Criteria = e.Criteria
            }).ToList(),
            EligibilityCourses = eligibilityCourses.Select(e => e.CourseName).ToList(),
            AllowedGenders = allowedGenders.Select(g => g.Gender).ToList(),
            RequiredSkills = requiredSkills.Select(s => s.SkillName).ToList(),
            HiringFlow = hiringFlow.OrderBy(h => h.Sequence).Select(h => h.StageName).ToList(),
            Documents = jobDocuments.Select(d => new JobDocumentResponse
            {
                DocumentIdentifier = d.DocumentIdentifier,
                DocumentName = d.DocumentName,
                DocumentUrl = d.DocumentUrl
            }).ToList()
        };

        return Ok(ApiResponse<JobResponse>.Ok(response));
    }
}
