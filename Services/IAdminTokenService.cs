namespace JIITPlacement.Services
{
    /// <summary>
    /// Issues the admin login token: a signed JWT whose jti claim identifies
    /// the session for logout revocation.
    /// </summary>
    public interface IAdminTokenService
    {
        /// <summary>Create a token for the admin; returns it plus its expiry.</summary>
        (string token, DateTimeOffset expiresAt) Issue(string username);
    }
}
