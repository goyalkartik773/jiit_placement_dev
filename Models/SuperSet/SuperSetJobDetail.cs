using System.Text.Json.Serialization;

namespace JIITPlacement.Models.SuperSet;

/// <summary>
/// Detailed job response from SuperSet API
/// The response IS the jobDetails object (not wrapped)
/// </summary>
public class SuperSetJobDetailDto
{
    [JsonPropertyName("eligibilityCheckResult")]
    public EligibilityCheckResult? EligibilityCheckResult { get; set; }
    
    [JsonPropertyName("jobProfile")]
    public JobProfileDetails? JobProfile { get; set; }
    
    [JsonPropertyName("jobProfileLocation")]
    public string? JobProfileLocation { get; set; }
    
    [JsonPropertyName("positionType")]
    public string? PositionType { get; set; }
}

public class EligibilityCheckResult
{
    [JsonPropertyName("academicResults")]
    public List<AcademicResult> AcademicResults { get; set; } = new();
    
    [JsonPropertyName("courseCheckResult")]
    public CourseCheckResult? CourseCheckResult { get; set; }
}

public class AcademicResult
{
    [JsonPropertyName("level")]
    public string Level { get; set; } = string.Empty;
    
    [JsonPropertyName("required")]
    public float Required { get; set; }
}

public class CourseCheckResult
{
    [JsonPropertyName("openedForCourses")]
    public List<OpenedCourse> OpenedForCourses { get; set; } = new();
}

public class OpenedCourse
{
    [JsonPropertyName("program")]
    public CourseProgram? Program { get; set; }
    
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
}

public class CourseProgram
{
    [JsonPropertyName("shortName")]
    public string ShortName { get; set; } = string.Empty;
}

public class JobProfileDetails
{
    [JsonPropertyName("allowGenderFemale")]
    public bool AllowGenderFemale { get; set; }
    
    [JsonPropertyName("allowGenderMale")]
    public bool AllowGenderMale { get; set; }
    
    [JsonPropertyName("allowGenderOther")]
    public bool AllowGenderOther { get; set; }
    
    [JsonPropertyName("jobDescription")]
    public string? JobDescription { get; set; }
    
    [JsonPropertyName("invitationCustomText")]
    public string? InvitationCustomText { get; set; }
    
    [JsonPropertyName("location")]
    public string? Location { get; set; }
    
    [JsonPropertyName("package")]
    public float? Package { get; set; }
    
    [JsonPropertyName("ctcMin")]
    public float? CtcMin { get; set; }
    
    [JsonPropertyName("ctcMax")]
    public float? CtcMax { get; set; }
    
    [JsonPropertyName("ctcAdditionalInfo")]
    public string? CtcAdditionalInfo { get; set; }
    
    [JsonPropertyName("ctcInterval")]
    public string? CtcInterval { get; set; }
    
    [JsonPropertyName("requiredSkills")]
    public List<string> RequiredSkills { get; set; } = new();
    
    [JsonPropertyName("stages")]
    public List<HiringStage>? Stages { get; set; }
    
    [JsonPropertyName("documents")]
    public List<SuperSetDocumentDto> Documents { get; set; } = new();
}

public class HiringStage
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("sequence")]
    public int Sequence { get; set; }
}

public class SuperSetDocumentDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("identifier")]
    public string Identifier { get; set; } = string.Empty;
}
