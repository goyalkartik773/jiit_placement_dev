using Microsoft.EntityFrameworkCore;
using JIITPlacement.Models.SuperSet;

namespace JIITPlacement.Models.App_Code;

/// <summary>
/// Domain entities for PostgreSQL database
/// </summary>

public class SupersetAccount
{
    public int Id { get; set; }
    public string Email { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Uuid { get; set; } = string.Empty;
    public string CollegeCode { get; set; } = string.Empty;
    public string Batch { get; set; } = string.Empty;
    public bool IsActive { get; set; } = true;
    public DateTime CreatedOn { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedOn { get; set; } = DateTime.UtcNow;
}

public class NoticeRecord
{
    public int Id { get; set; }
    public string SuperSetIdentifier { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public string Author { get; set; } = string.Empty;
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public DateTime CreatedOn { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedOn { get; set; } = DateTime.UtcNow;
}

public class JobRecord
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
    public string Location { get; set; } = "Unknown";
    public float Package { get; set; }
    public string PackageInfo { get; set; } = string.Empty;
    public string JobDescription { get; set; } = string.Empty;
    public string? PlacementType { get; set; }
    public DateTime CreatedOn { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedOn { get; set; } = DateTime.UtcNow;
    
    // Navigation properties
    public List<JobEligibilityRecord> EligibilityMarks { get; set; } = new();
    public List<JobEligibilityCourseRecord> EligibilityCourses { get; set; } = new();
    public List<JobGenderRecord> AllowedGenders { get; set; } = new();
    public List<JobSkillRecord> RequiredSkills { get; set; } = new();
    public List<JobHiringFlowRecord> HiringFlow { get; set; } = new();
    public List<JobDocumentRecord> Documents { get; set; } = new();
}

public class JobEligibilityRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public string Level { get; set; } = string.Empty;
    public float Criteria { get; set; }
    public JobRecord JobRecord { get; set; } = null!;
}

public class JobEligibilityCourseRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public string CourseName { get; set; } = string.Empty;
    public JobRecord JobRecord { get; set; } = null!;
}

public class JobGenderRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public string Gender { get; set; } = string.Empty;
    public JobRecord JobRecord { get; set; } = null!;
}

public class JobSkillRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public string SkillName { get; set; } = string.Empty;
    public JobRecord JobRecord { get; set; } = null!;
}

public class JobHiringFlowRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public int Sequence { get; set; }
    public string StageName { get; set; } = string.Empty;
    public JobRecord JobRecord { get; set; } = null!;
}

public class JobDocumentRecord
{
    public int Id { get; set; }
    public int JobRecordId { get; set; }
    public string DocumentIdentifier { get; set; } = string.Empty;
    public string DocumentName { get; set; } = string.Empty;
    public string? DocumentUrl { get; set; }
    public JobRecord JobRecord { get; set; } = null!;
}

/// <summary>
/// Application DbContext for PostgreSQL
/// </summary>
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }
    
    public DbSet<SupersetAccount> SupersetAccounts => Set<SupersetAccount>();
    public DbSet<NoticeRecord> Notices => Set<NoticeRecord>();
    public DbSet<JobRecord> Jobs => Set<JobRecord>();
    public DbSet<JobEligibilityRecord> JobEligibilities => Set<JobEligibilityRecord>();
    public DbSet<JobEligibilityCourseRecord> JobEligibilityCourses => Set<JobEligibilityCourseRecord>();
    public DbSet<JobGenderRecord> JobGenders => Set<JobGenderRecord>();
    public DbSet<JobSkillRecord> JobSkills => Set<JobSkillRecord>();
    public DbSet<JobHiringFlowRecord> JobHiringFlows => Set<JobHiringFlowRecord>();
    public DbSet<JobDocumentRecord> JobDocuments => Set<JobDocumentRecord>();
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        
        // SupersetAccount
        modelBuilder.Entity<SupersetAccount>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.Email).IsUnique();
            entity.HasIndex(e => e.Uuid).IsUnique();
            entity.Property(e => e.Email).HasMaxLength(256).IsRequired();
            entity.Property(e => e.Name).HasMaxLength(256).IsRequired();
            entity.Property(e => e.Uuid).HasMaxLength(128).IsRequired();
            entity.Property(e => e.CollegeCode).HasMaxLength(64).IsRequired();
            entity.Property(e => e.Batch).HasMaxLength(128).IsRequired();
        });
        
        // NoticeRecord
        modelBuilder.Entity<NoticeRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SuperSetIdentifier).IsUnique();
            entity.Property(e => e.SuperSetIdentifier).HasMaxLength(128).IsRequired();
            entity.Property(e => e.Title).HasMaxLength(512).IsRequired();
            entity.Property(e => e.Author).HasMaxLength(256).IsRequired();
        });
        
        // JobRecord
        modelBuilder.Entity<JobRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SuperSetJobIdentifier).IsUnique();
            entity.Property(e => e.SuperSetJobIdentifier).HasMaxLength(128).IsRequired();
            entity.Property(e => e.Company).HasMaxLength(256).IsRequired();
            entity.Property(e => e.JobProfile).HasMaxLength(512).IsRequired();
            entity.Property(e => e.PlacementCategory).HasMaxLength(128).IsRequired();
            entity.Property(e => e.Content).HasColumnType("text").IsRequired();
            entity.Property(e => e.Location).HasMaxLength(256).IsRequired();
            entity.Property(e => e.PackageInfo).HasColumnType("text");
            entity.Property(e => e.JobDescription).HasColumnType("text").IsRequired();
            entity.Property(e => e.PlacementType).HasMaxLength(128);
        });
        
        // JobEligibilityRecord
        modelBuilder.Entity<JobEligibilityRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.EligibilityMarks)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.Property(e => e.Level).HasMaxLength(32).IsRequired();
        });
        
        // JobEligibilityCourseRecord
        modelBuilder.Entity<JobEligibilityCourseRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.EligibilityCourses)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.Property(e => e.CourseName).HasMaxLength(256).IsRequired();
        });
        
        // JobGenderRecord
        modelBuilder.Entity<JobGenderRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.AllowedGenders)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.Property(e => e.Gender).HasMaxLength(32).IsRequired();
        });
        
        // JobSkillRecord
        modelBuilder.Entity<JobSkillRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.RequiredSkills)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.Property(e => e.SkillName).HasMaxLength(256).IsRequired();
        });
        
        // JobHiringFlowRecord
        modelBuilder.Entity<JobHiringFlowRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.HiringFlow)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.Property(e => e.StageName).HasMaxLength(256).IsRequired();
        });
        
        // JobDocumentRecord
        modelBuilder.Entity<JobDocumentRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.JobRecord)
                  .WithMany(j => j.Documents)
                  .HasForeignKey(e => e.JobRecordId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.HasIndex(e => e.DocumentIdentifier).IsUnique();
            entity.Property(e => e.DocumentIdentifier).HasMaxLength(128).IsRequired();
            entity.Property(e => e.DocumentName).HasMaxLength(256).IsRequired();
            entity.Property(e => e.DocumentUrl).HasMaxLength(1024);
        });
    }
}
