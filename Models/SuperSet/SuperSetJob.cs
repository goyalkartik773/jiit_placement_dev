using System.Text.Json.Serialization;

namespace JIITPlacement.Models.SuperSet;

/// <summary>
/// Basic job listing from SuperSet API (without detailed info)
/// </summary>
public class SuperSetJobBasicDto
{
    [JsonPropertyName("jobProfileIdentifier")]
    public string JobProfileIdentifier { get; set; } = string.Empty;
    
    [JsonPropertyName("jobProfileTitle")]
    public string JobProfileTitle { get; set; } = string.Empty;
    
    [JsonPropertyName("companyName")]
    public string CompanyName { get; set; } = string.Empty;
    
    [JsonPropertyName("placementCategoryLevel")]
    public int PlacementCategoryLevel { get; set; }
    
    [JsonPropertyName("placementCategoryName")]
    public string? PlacementCategoryName { get; set; }
    
    [JsonPropertyName("content")]
    public string Content { get; set; } = string.Empty;
    
    [JsonPropertyName("createdAt")]
    public long? CreatedAt { get; set; }
    
    [JsonPropertyName("jobProfileApplicationDeadline")]
    public long? JobProfileApplicationDeadline { get; set; }
}
