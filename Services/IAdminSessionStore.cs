namespace JIITPlacement.Services
{
    /// <summary>
    /// In-memory store for admin session tokens. Tokens are random and only
    /// their SHA-256 digest is kept, so logout can truly invalidate a session
    /// and a memory snapshot never exposes a usable token.
    /// </summary>
    public interface IAdminSessionStore
    {
        /// <summary>Create a new session for the admin and return the raw token.</summary>
        string CreateToken(string username);

        /// <summary>Return the session's username, or null when the token is unknown/expired.</summary>
        string? ValidateToken(string token);

        /// <summary>Invalidate a token (logout). Returns false when it was already gone.</summary>
        bool RevokeToken(string token);
    }
}
