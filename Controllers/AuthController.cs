using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Controllers
{
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

        [HttpPost("authenticate")]
        public async Task<ActionResult> Authenticate()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                if (string.IsNullOrEmpty(_options.Username) || string.IsNullOrEmpty(_options.Password))
                {
                    response.status = false;
                    response.Message = "SuperSet credentials not configured";
                    return BadRequest(response);
                }

                var result = await _superSetService.LoginAsync(_options.Username, _options.Password);

                response.status = true;
                response.Message = "SuperSet authentication successful";
                response.Data = new
                {
                    result.Name,
                    result.Username,
                    result.Uuid,
                    result.EmailVerified
                };
                return Ok(response);
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "SuperSet authentication failed");
                response.status = false;
                response.Message = "SuperSet auth failed: " + ex.Message;
                return BadRequest(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error during SuperSet authentication");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }
    }
}
