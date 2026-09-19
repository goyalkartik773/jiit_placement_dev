namespace JIITPlacement.Models.Jobs;

public class JobResponse
{
    public int Id { get; set; }
    public string SuperSetJobIdentifier { get; set; } = string.Empty;
    public string Company { get; set; } = string.Empty;
    public string JobProfile { get; set; } = string.Empty;
    public string PlacementCategory { get; set; } = string.Empty;
    public int PlacementCategoryCode { get; set; }
    public string Content { get; set; } = string.Empty;
    public DateTime? CreatedAt { get; set; }
    public DateTime? Deadline { get; set; }
    public string Location { get; set; } = string.Empty;
    public float Package { get; set; }
    public string PackageInfo { get; set; } = string.Empty;
    public string JobDescription { get; set; } = string.Empty;
    public string? PlacementType { get; set; }
    public DateTime CreatedOn { get; set; }
    public DateTime UpdatedOn { get; set; }
    public List<JobEligibilityResponse> EligibilityMarks { get; set; } = new();
    public List<string> EligibilityCourses { get; set; } = new();
    public List<string> AllowedGenders { get; set; } = new();
    public List<string> RequiredSkills { get; set; } = new();
    public List<string> HiringFlow { get; set; } = new();
    public List<JobDocumentResponse> Documents { get; set; } = new();
}

public class JobEligibilityResponse
{
    public string Level { get; set; } = string.Empty;
    public float Criteria { get; set; }
}

public class JobDocumentResponse
{
    public string DocumentIdentifier { get; set; } = string.Empty;
    public string DocumentName { get; set; } = string.Empty;
    public string? DocumentUrl { get; set; }
}
