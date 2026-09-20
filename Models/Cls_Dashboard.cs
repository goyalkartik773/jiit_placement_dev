namespace JIITPlacement.Models
{
    public class Cls_Dashboard
    {
        public class DashboardStats
        {
            public int TotalJobs { get; set; }
            public int TotalNotices { get; set; }
            public int HighCategoryJobs { get; set; }
            public int MiddleCategoryJobs { get; set; }
            public int InternshipJobs { get; set; }
            public List<RecentNotice> RecentNotices { get; set; } = new();
        }

        public class RecentNotice
        {
            public string Id { get; set; } = string.Empty;
            public string Title { get; set; } = string.Empty;
            public string Author { get; set; } = string.Empty;
            public DateTime? CreatedAt { get; set; }
        }
    }
}
