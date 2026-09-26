using System.Collections.Concurrent;

namespace JIITPlacement.Services
{
    public class AdminTokenRevocationStore : IAdminTokenRevocationStore
    {
        private readonly ConcurrentDictionary<string, DateTimeOffset> _revoked = new();

        public void Revoke(string tokenId, DateTimeOffset expiresAt)
        {
            PruneExpired();
            _revoked[tokenId] = expiresAt;
        }

        public bool IsRevoked(string tokenId)
        {
            if (!_revoked.TryGetValue(tokenId, out var expiresAt))
                return false;

            if (expiresAt <= DateTimeOffset.UtcNow)
            {
                // The token itself has expired — nothing left to enforce.
                _revoked.TryRemove(tokenId, out _);
                return false;
            }

            return true;
        }

        private void PruneExpired()
        {
            var now = DateTimeOffset.UtcNow;
            foreach (var pair in _revoked)
            {
                if (pair.Value <= now)
                    _revoked.TryRemove(pair.Key, out _);
            }
        }
    }
}
