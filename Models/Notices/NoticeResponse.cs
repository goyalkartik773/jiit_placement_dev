namespace JIITPlacement.Models.Notices;

public class NoticeResponse
{
    public string Id { get; set; } = string.Empty;
    public string SuperSetIdentifier { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public string Author { get; set; } = string.Empty;
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public string Status { get; set; } = string.Empty;
    public DateTime posteddatetime { get; set; }
    public DateTime? updateddatetime { get; set; }
}
