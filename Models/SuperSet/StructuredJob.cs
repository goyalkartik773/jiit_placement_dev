namespace JIITPlacement.Models.SuperSet;

/// <summary>
/// Fully structured job after processing from SuperSet API
/// </summary>
public class StructuredJob
{
    public string Id { get; set; } = string.Empty;
    public string JobProfile { get; set; } = string.Empty;
    public string Company { get; set; } = string.Empty;
    public int PlacementCategoryCode { get; set; }
    public string PlacementCategory { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public long? CreatedAt { get; set; }
    public long? Deadline { get; set; }
    public List<EligibilityMark> EligibilityMarks { get; set; } = new();
    public List<string> EligibilityCourses { get; set; } = new();
    public List<string> AllowedGenders { get; set; } = new();
    public string JobDescription { get; set; } = string.Empty;
    public string Location { get; set; } = "Unknown";
    public float Package { get; set; }
    public string? AnnumMonths { get; set; }
    public string PackageInfo { get; set; } = string.Empty;
    public List<string> RequiredSkills { get; set; } = new();
    public List<string> HiringFlow { get; set; } = new();
    public string? PlacementType { get; set; }
    public List<StructuredDocument> Documents { get; set; } = new();
}

public class EligibilityMark
{
    public string Level { get; set; } = string.Empty;
    public float Criteria { get; set; }
}

public class StructuredDocument
{
    public string Name { get; set; } = string.Empty;
    public string Identifier { get; set; } = string.Empty;
    public string? Url { get; set; }
}
