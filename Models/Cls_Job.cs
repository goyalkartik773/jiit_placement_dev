namespace JIITPlacement.Models
{
    public class Cls_Job
    {
        public class JobRequest
        {
            public string SysJobUuid { get; set; } = string.Empty;
            public string SuperSetJobIdentifier { get; set; } = string.Empty;
            public string Company { get; set; } = string.Empty;
            public string JobProfile { get; set; } = string.Empty;
            public string PlacementCategory { get; set; } = string.Empty;
            public string PlacementCategoryCode { get; set; } = string.Empty;
            public string Content { get; set; } = string.Empty;
            public string CreatedAt { get; set; } = string.Empty;
            public string Deadline { get; set; } = string.Empty;
            public string Location { get; set; } = string.Empty;
            public decimal Package { get; set; }
            public string PackageInfo { get; set; } = string.Empty;
            public string JobDescription { get; set; } = string.Empty;
            public string PlacementType { get; set; } = string.Empty;

            // Nested child data
            public List<EligibilityRequest> EligibilityMarks { get; set; } = new();
            public List<string> EligibilityCourses { get; set; } = new();
            public List<string> AllowedGenders { get; set; } = new();
            public List<string> RequiredSkills { get; set; } = new();
            public List<HiringFlowRequest> HiringFlow { get; set; } = new();
            public List<DocumentRequest> Documents { get; set; } = new();
        }

        public class JobListRequest
        {
            public int Page { get; set; } = 1;
            public int PageSize { get; set; } = 20;
            public string Company { get; set; } = string.Empty;
            public string Search { get; set; } = string.Empty;
        }

        public class EligibilityRequest
        {
            public string Level { get; set; } = string.Empty;
            public decimal Criteria { get; set; }
        }

        public class HiringFlowRequest
        {
            public int Sequence { get; set; }
            public string StageName { get; set; } = string.Empty;
        }

        public class DocumentRequest
        {
            public string DocumentIdentifier { get; set; } = string.Empty;
            public string DocumentName { get; set; } = string.Empty;
            public string DocumentPath { get; set; } = string.Empty;
            public string ContentType { get; set; } = "application/octet-stream";
            public long FileSize { get; set; }
        }
    }
}
