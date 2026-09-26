using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using JIITPlacement.Models;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace JIITPlacement.Services
{
    public class AdminTokenService : IAdminTokenService
    {
        private readonly AdminOptions _adminOptions;
        private readonly JwtOptions _jwtOptions;

        public AdminTokenService(IOptions<AdminOptions> adminOptions, IOptions<JwtOptions> jwtOptions)
        {
            _adminOptions = adminOptions.Value;
            _jwtOptions = jwtOptions.Value;
        }

        public (string token, DateTimeOffset expiresAt) Issue(string username)
        {
            if (string.IsNullOrWhiteSpace(_jwtOptions.Secret) ||
                Encoding.UTF8.GetBytes(_jwtOptions.Secret).Length < 32)
            {
                throw new InvalidOperationException(
                    "Jwt:Secret must be configured with at least 32 bytes before a token can be issued.");
            }

            var now = DateTimeOffset.UtcNow;
            var expiresAt = now.AddHours(Math.Max(1, _adminOptions.TokenExpirationHours));

            var claims = new[]
            {
                new Claim("username", username),
                new Claim("role", "Admin"),
                // Token id — the handle logout revokes.
                new Claim("jti", Guid.NewGuid().ToString("N"))
            };

            var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_jwtOptions.Secret));
            var jwt = new JwtSecurityToken(
                issuer: _jwtOptions.Issuer,
                audience: _jwtOptions.Audience,
                claims: claims,
                notBefore: now.UtcDateTime,
                expires: expiresAt.UtcDateTime,
                signingCredentials: new SigningCredentials(key, SecurityAlgorithms.HmacSha256));

            return (new JwtSecurityTokenHandler().WriteToken(jwt), expiresAt);
        }
    }
}
