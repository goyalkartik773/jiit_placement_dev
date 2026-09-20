using JIITPlacement.Models.App_Code;
using JIITPlacement.Models.Notices;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JIITPlacement.Controllers;

[ApiController]
[Route("api")]
public class NoticeController : ControllerBase
{
    private readonly AppDbContext _dbContext;
    private readonly ILogger<NoticeController> _logger;

    public NoticeController(AppDbContext dbContext, ILogger<NoticeController> logger)
    {
        _dbContext = dbContext;
        _logger = logger;
    }

    /// <summary>
    /// Get notices from local PostgreSQL database
    /// </summary>
    [HttpGet("notices")]
    [ProducesResponseType(typeof(ApiResponse<PaginatedResponse<NoticeResponse>>), 200)]
    public async Task<ActionResult<ApiResponse<PaginatedResponse<NoticeResponse>>>> GetNotices(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? search = null)
    {
        pageSize = Math.Min(pageSize, 100);

        var query = _dbContext.Notices.AsQueryable();

        if (!string.IsNullOrEmpty(search))
        {
            query = query.Where(n =>
                n.Title.Contains(search) ||
                n.Content.Contains(search));
        }

        var totalCount = await query.CountAsync();

        var notices = await query
            .OrderByDescending(n => n.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(n => new NoticeResponse
            {
                Id = n.Id,
                SuperSetIdentifier = n.SuperSetIdentifier,
                Title = n.Title,
                Content = n.Content,
                Author = n.Author,
                CreatedAt = n.CreatedAt,
                UpdatedAt = n.UpdatedAt,
                Status = n.Status,
                posteddatetime = n.posteddatetime,
                updateddatetime = n.updateddatetime
            })
            .ToListAsync();

        var response = new PaginatedResponse<NoticeResponse>
        {
            Items = notices,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };

        return Ok(ApiResponse<PaginatedResponse<NoticeResponse>>.Ok(response));
    }
}
