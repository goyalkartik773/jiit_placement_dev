using System.Text.Json.Serialization;

namespace JIITPlacement.Models.SuperSet;

public class SuperSetLoginRequest
{
    [JsonPropertyName("username")]
    public string Username { get; set; } = string.Empty;
    
    [JsonPropertyName("password")]
    public string Password { get; set; } = string.Empty;
}
