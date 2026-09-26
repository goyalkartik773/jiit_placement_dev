namespace JIITPlacement.Models
{
    // ================================================================
    // JWT options (config from appsettings.json / env Jwt__Secret …)
    // ================================================================
    public class JwtOptions
    {
        public const string SectionName = "Jwt";

        /// <summary>Symmetric HMAC-SHA256 signing key; at least 32 bytes.</summary>
        public string Secret { get; set; } = string.Empty;

        public string Issuer { get; set; } = "JIITPlacement";

        public string Audience { get; set; } = "JIITPlacement";
    }
}
