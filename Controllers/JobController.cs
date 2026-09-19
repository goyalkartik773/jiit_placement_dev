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
    /// <remarks>
    /// Returns paginated jobs stored in PostgreSQL.
    /// </remarks>
    /// <param name="page">Page number (default: 1)</param>
    /// <param name="pageSize">Page size (default: 20, max: 100)</param>
    /// <param name="company">Filter by company name (optional)</param>
    /// <returns>Paginated job list</returns>
    /// <response code="200">Jobs retrieved successfully</response>
    [HttpGet("jobs")]
    [ProducesResponseType(typeof(ApiResponse<PaginatedResponse<JobResponse>>), 200)]
    public async Task<ActionResult<ApiResponse<PaginatedResponse<JobResponse>>>> GetJobs(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? company = null)
    {
        pageSize = Math.Min(pageSize, 100);
        
        var query = _dbContext.Jobs
            .Include(j => j.EligibilityMarks)
            .Include(j => j.Documents)
            .AsQueryable();
        
        if (!string.IsNullOrEmpty(company))
        {
            query = query.Where(j => j.Company.Contains(company));
        }
        
        var totalCount = await query.CountAsync();
        
        var jobs = await query
            .OrderByDescending(j => j.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(j => new JobResponse
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
                CreatedOn = j.CreatedOn,
                UpdatedOn = j.UpdatedOn,
                EligibilityMarks = j.EligibilityMarks.Select(e => new JobEligibilityResponse
                {
                    Level = e.Level,
                    Criteria = e.Criteria
                }).ToList(),
                Documents = j.Documents.Select(d => new JobDocumentResponse
                {
                    DocumentIdentifier = d.DocumentIdentifier,
                    DocumentName = d.DocumentName,
                    DocumentUrl = d.DocumentUrl
                }).ToList()
            })
            .ToListAsync();
        
        var response = new PaginatedResponse<JobResponse>
        {
            Items = jobs,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
        
        return Ok(ApiResponse<PaginatedResponse<JobResponse>>.Ok(response));
    }

    /// <summary>
    /// Get a specific job by ID
    /// </summary>
    /// <param name="id">Job ID</param>
    /// <returns>Job details</returns>
    /// <response code="200">Job found</response>
    /// <response code="404">Job not found</response>
    [HttpGet("jobs/{id:int}")]
    [ProducesResponseType(typeof(ApiResponse<JobResponse>), 200)]
    [ProducesResponseType(typeof(ApiResponse<JobResponse>), 404)]
    public async Task<ActionResult<ApiResponse<JobResponse>>> GetJob(int id)
    {
        var job = await _dbContext.Jobs
            .Include(j => j.EligibilityMarks)
            .Include(j => j.EligibilityCourses)
            .Include(j => j.AllowedGenders)
            .Include(j => j.RequiredSkills)
            .Include(j => j.HiringFlow)
            .Include(j => j.Documents)
            .FirstOrDefaultAsync(j => j.Id == id);
        
        if (job == null)
            return NotFound(ApiResponse<JobResponse>.Fail("Job not found"));
        
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
            CreatedOn = job.CreatedOn,
            UpdatedOn = job.UpdatedOn,
            EligibilityMarks = job.EligibilityMarks.Select(e => new JobEligibilityResponse
            {
                Level = e.Level,
                Criteria = e.Criteria
            }).ToList(),
            EligibilityCourses = job.EligibilityCourses.Select(e => e.CourseName).ToList(),
            AllowedGenders = job.AllowedGenders.Select(g => g.Gender).ToList(),
            RequiredSkills = job.RequiredSkills.Select(s => s.SkillName).ToList(),
            HiringFlow = job.HiringFlow.OrderBy(h => h.Sequence).Select(h => h.StageName).ToList(),
            Documents = job.Documents.Select(d => new JobDocumentResponse
            {
                DocumentIdentifier = d.DocumentIdentifier,
                DocumentName = d.DocumentName,
                DocumentUrl = d.DocumentUrl
            }).ToList()
        };
        
        return Ok(ApiResponse<JobResponse>.Ok(response));
    }
}
