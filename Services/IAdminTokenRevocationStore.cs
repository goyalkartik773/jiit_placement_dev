namespace JIITPlacement.Services
{
    /// <summary>
    /// Denylist of logged-out JWT ids (jti claims). Entries expire together
    /// with the token they belong to, so the store prunes itself.
    /// </summary>
    public interface IAdminTokenRevocationStore
    {
        /// <summary>Revoke a token id until <paramref name="expiresAt"/>.</summary>
        void Revoke(string tokenId, DateTimeOffset expiresAt);

        /// <summary>True when the id belongs to a token that was logged out.</summary>
        bool IsRevoked(string tokenId);
    }
}
