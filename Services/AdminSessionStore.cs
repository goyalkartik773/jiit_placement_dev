using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using JIITPlacement.Models;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public class AdminSessionStore : IAdminSessionStore
    {
        private sealed class Session
        {
            public string Username { get; init; } = string.Empty;
            public DateTimeOffset ExpiresAt { get; init; }
        }

        private readonly ConcurrentDictionary<string, Session> _sessions = new();
        private readonly AdminOptions _options;
        private readonly ILogger<AdminSessionStore> _logger;

        public AdminSessionStore(IOptions<AdminOptions> options, ILogger<AdminSessionStore> logger)
        {
            _options = options.Value;
            _logger = logger;
        }

        public string CreateToken(string username)
        {
            // 256 bits of randomness, URL-safe encoding for the Authorization header.
            var bytes = RandomNumberGenerator.GetBytes(64);
            var token = Convert.ToBase64String(bytes)
                .Replace('+', '-')
                .Replace('/', '_')
                .TrimEnd('=');

            var session = new Session
            {
                Username = username,
                ExpiresAt = DateTimeOffset.UtcNow.AddHours(Math.Max(1, _options.TokenExpirationHours))
            };

            PruneExpired();
            _sessions[Digest(token)] = session;

            _logger.LogInformation("Admin session created for {Username}, expires {ExpiresAt:u}",
                username, session.ExpiresAt);
            return token;
        }

        public string? ValidateToken(string token)
        {
            if (string.IsNullOrWhiteSpace(token))
                return null;

            PruneExpired();

            if (_sessions.TryGetValue(Digest(token), out var session))
                return session.Username;

            return null;
        }

        public bool RevokeToken(string token)
        {
            if (string.IsNullOrWhiteSpace(token))
                return false;

            return _sessions.TryRemove(Digest(token), out _);
        }

        private static string Digest(string token)
        {
            var hash = SHA256.HashData(Encoding.UTF8.GetBytes(token));
            return Convert.ToBase64String(hash);
        }

        private void PruneExpired()
        {
            var now = DateTimeOffset.UtcNow;
            foreach (var pair in _sessions)
            {
                if (pair.Value.ExpiresAt <= now && _sessions.TryRemove(pair.Key, out _))
                {
                    _logger.LogInformation("Admin session expired for {Username}", pair.Value.Username);
                }
            }
        }
    }
}
