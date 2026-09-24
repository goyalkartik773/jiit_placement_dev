using System.Security.Claims;
using System.Text;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;
using Microsoft.Net.Http.Headers;

namespace JIITPlacement.Services
{
    /// <summary>
    /// Bearer-token authentication for admin APIs. Reads "Authorization: Bearer &lt;token&gt;",
    /// validates it against the in-memory session store and answers every failed
    /// challenge with the documented JSON error body.
    /// </summary>
    public class AdminAuthHandler : AuthenticationHandler<AuthenticationSchemeOptions>
    {
        public const string SchemeName = "AdminToken";
        private const string BearerPrefix = "Bearer ";

        private readonly IAdminSessionStore _sessionStore;

        public AdminAuthHandler(
            IOptionsMonitor<AuthenticationSchemeOptions> options,
            ILoggerFactory logger,
            UrlEncoder encoder,
            IAdminSessionStore sessionStore)
            : base(options, logger, encoder)
        {
            _sessionStore = sessionStore;
        }

        protected override Task<AuthenticateResult> HandleAuthenticateAsync()
        {
            if (!Request.Headers.TryGetValue(HeaderNames.Authorization, out var headerValues))
                return Task.FromResult(AuthenticateResult.NoResult());

            var header = headerValues.ToString();
            if (string.IsNullOrWhiteSpace(header) || !header.StartsWith(BearerPrefix, StringComparison.OrdinalIgnoreCase))
                return Task.FromResult(AuthenticateResult.NoResult());

            var token = header[BearerPrefix.Length..].Trim();
            if (string.IsNullOrEmpty(token))
                return Task.FromResult(AuthenticateResult.NoResult());

            var username = _sessionStore.ValidateToken(token);
            if (username is null)
                return Task.FromResult(AuthenticateResult.Fail("Invalid or expired admin session"));

            var identity = new ClaimsIdentity(new[]
            {
                new Claim(ClaimTypes.Name, username),
                new Claim(ClaimTypes.Role, "Admin")
            }, SchemeName);

            var ticket = new AuthenticationTicket(new ClaimsPrincipal(identity), SchemeName);
            return Task.FromResult(AuthenticateResult.Success(ticket));
        }

        protected override Task HandleChallengeAsync(AuthenticationProperties properties)
        {
            return WriteErrorAsync(StatusCodes.Status401Unauthorized, "Unauthorized");
        }

        protected override Task HandleForbiddenAsync(AuthenticationProperties properties)
        {
            return WriteErrorAsync(StatusCodes.Status403Forbidden, "Forbidden");
        }

        private Task WriteErrorAsync(int statusCode, string message)
        {
            Response.StatusCode = statusCode;
            Response.ContentType = "application/json; charset=utf-8";
            return Response.WriteAsync(
                $"{{\"success\":false,\"message\":\"{message}\"}}",
                Encoding.UTF8);
        }
    }
}
