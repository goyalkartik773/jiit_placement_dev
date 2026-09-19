using System.Text.Json.Serialization;

namespace JIITPlacement.Models.SuperSet;

/// <summary>
/// Raw notice response from SuperSet API
/// </summary>
public class SuperSetNoticeDto
{
    [JsonPropertyName("identifier")]
    public string Identifier { get; set; } = string.Empty;
    
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;
    
    [JsonPropertyName("content")]
    public string Content { get; set; } = string.Empty;
    
    [JsonPropertyName("lastModifiedByUserName")]
    public string LastModifiedByUserName { get; set; } = string.Empty;
    
    [JsonPropertyName("lastModifiedOn")]
    public long? LastModifiedOn { get; set; }
    
    [JsonPropertyName("publishedAt")]
    public long? PublishedAt { get; set; }
}
