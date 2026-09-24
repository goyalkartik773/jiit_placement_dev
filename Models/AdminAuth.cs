namespace JIITPlacement.Models
{
    // ================================================================
    // Admin Options (config from appsettings.json / env Admin__Username…)
    // ================================================================
    public class AdminOptions
    {
        public const string SectionName = "Admin";
        public string Username { get; set; } = string.Empty;
        public string Password { get; set; } = string.Empty;
        /// <summary>Lifetime of an admin session token, in hours.</summary>
        public int TokenExpirationHours { get; set; } = 8;
    }

    // ================================================================
    // Admin login request
    // ================================================================
    public class AdminLoginRequest
    {
        public string Username { get; set; } = string.Empty;
        public string Password { get; set; } = string.Empty;
    }
}
