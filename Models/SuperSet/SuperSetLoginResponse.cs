using System.Text.Json.Serialization;

namespace JIITPlacement.Models.SuperSet;

public class SuperSetLoginResponse
{
    [JsonPropertyName("userId")]
    public long UserId { get; set; }
    
    [JsonPropertyName("username")]
    public string Username { get; set; } = string.Empty;
    
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("emailHash")]
    public string EmailHash { get; set; } = string.Empty;
    
    [JsonPropertyName("sessionKey")]
    public string SessionKey { get; set; } = string.Empty;
    
    [JsonPropertyName("uuid")]
    public string Uuid { get; set; } = string.Empty;
    
    [JsonPropertyName("refreshToken")]
    public string RefreshToken { get; set; } = string.Empty;
    
    [JsonPropertyName("userProfilePhotoId")]
    public string UserProfilePhotoId { get; set; } = string.Empty;
    
    [JsonPropertyName("userModes")]
    public List<string> UserModes { get; set; } = new();
    
    [JsonPropertyName("permissions")]
    public List<string> Permissions { get; set; } = new();
    
    [JsonPropertyName("emailVerified")]
    public bool EmailVerified { get; set; }
    
    [JsonPropertyName("message")]
    public string? Message { get; set; }
    
    [JsonPropertyName("enableMfa")]
    public bool EnableMfa { get; set; }
}
