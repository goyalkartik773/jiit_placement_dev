using JIITPlacement.Models.App_Code;
using JIITPlacement.Models.SuperSet;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Controllers;

[ApiController]
[Route("api/superset")]
public class AuthController : ControllerBase
{
    private readonly ISuperSetService _superSetService;
    private readonly SuperSetOptions _options;
    private readonly ILogger<AuthController> _logger;

    public AuthController(
        ISuperSetService superSetService,
        IOptions<SuperSetOptions> options,
        ILogger<AuthController> logger)
    {
        _superSetService = superSetService;
        _options = options.Value;
        _logger = logger;
    }

    /// <summary>
    /// Test SuperSet authentication
    /// </summary>
    /// <remarks>
    /// Tests authentication with SuperSet using configured credentials.
    /// Does not return sensitive authentication information.
    /// </remarks>
    /// <returns>Authentication result</returns>
    /// <response code="200">Authentication successful</response>
    /// <response code="400">Invalid credentials or configuration</response>
    /// <response code="500">SuperSet service unavailable</response>
    [HttpPost("authenticate")]
    [ProducesResponseType(typeof(ApiResponse<object>), 200)]
    [ProducesResponseType(typeof(ApiResponse<object>), 400)]
    [ProducesResponseType(typeof(ApiResponse<object>), 500)]
    public async Task<ActionResult<ApiResponse<object>>> Authenticate()
    {
        try
        {
            if (string.IsNullOrEmpty(_options.Username) || string.IsNullOrEmpty(_options.Password))
            {
                return BadRequest(ApiResponse<object>.Fail("SuperSet credentials not configured"));
            }
            
            var response = await _superSetService.LoginAsync(_options.Username, _options.Password);
            
            // Return only safe diagnostic information
            var result = new
            {
                Name = response.Name,
                Username = response.Username,
                Uuid = response.Uuid,
                EmailVerified = response.EmailVerified
            };
            
            return Ok(ApiResponse<object>.Ok(result, "SuperSet authentication successful"));
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "SuperSet authentication failed");
            return BadRequest(ApiResponse<object>.Fail($"SuperSet authentication failed: {ex.Message}"));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error during SuperSet authentication");
            return StatusCode(500, ApiResponse<object>.Fail($"Authentication error: {ex.Message}"));
        }
    }
}
