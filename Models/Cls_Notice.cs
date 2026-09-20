namespace JIITPlacement.Models
{
    public class Cls_Notice
    {
        public class NoticeRequest
        {
            public string SysIdentifier { get; set; } = string.Empty;
            public string Title { get; set; } = string.Empty;
            public string Content { get; set; } = string.Empty;
            public string Author { get; set; } = string.Empty;
            public string CreatedAt { get; set; } = string.Empty;
            public string UpdatedAt { get; set; } = string.Empty;
            public string PostedBy { get; set; } = string.Empty;
        }

        public class NoticeListRequest
        {
            public int Page { get; set; } = 1;
            public int PageSize { get; set; } = 20;
            public string Search { get; set; } = string.Empty;
        }
    }
}
