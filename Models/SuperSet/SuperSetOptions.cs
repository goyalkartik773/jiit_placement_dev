namespace JIITPlacement.Models.SuperSet;

public class SuperSetOptions
{
    public const string SectionName = "SuperSet";
    
    public string BaseUrl { get; set; } = string.Empty;
    public string ApiBasePath { get; set; } = "/tnpsuite-core";
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public string TenantId { get; set; } = string.Empty;
    public string TenantType { get; set; } = "STUDENT";
    public string StudentUuid { get; set; } = string.Empty;
    
    public string ApiBaseUrl => $"{BaseUrl}{ApiBasePath}";
}
