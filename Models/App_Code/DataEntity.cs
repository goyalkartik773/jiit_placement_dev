using Microsoft.EntityFrameworkCore;
using JIITPlacement.Models.SuperSet;

namespace JIITPlacement.Models.App_Code;

/// <summary>
/// Domain entities for PostgreSQL database
/// All tables use text PKs (UUIDs), text datatypes everywhere, no FK constraints
/// </summary>

public class SupersetAccount
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Email { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Uuid { get; set; } = string.Empty;
    public string CollegeCode { get; set; } = string.Empty;
    public string Batch { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class NoticeRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SuperSetIdentifier { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public string Author { get; set; } = string.Empty;
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SuperSetJobIdentifier { get; set; } = string.Empty;
    public string Company { get; set; } = string.Empty;
    public string JobProfile { get; set; } = string.Empty;
    public string PlacementCategory { get; set; } = string.Empty;
    public string PlacementCategoryCode { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public DateTime? CreatedAt { get; set; }
    public DateTime? Deadline { get; set; }
    public string Location { get; set; } = "Unknown";
    public float Package { get; set; }
    public string PackageInfo { get; set; } = string.Empty;
    public string JobDescription { get; set; } = string.Empty;
    public string PlacementType { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobEligibilityRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string Level { get; set; } = string.Empty;
    public string Criteria { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobEligibilityCourseRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string CourseName { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobGenderRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string Gender { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobSkillRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string SkillName { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobHiringFlowRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string Sequence { get; set; } = string.Empty;
    public string StageName { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

public class JobDocumentRecord
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string SysJobUuid { get; set; } = string.Empty;
    public string DocumentIdentifier { get; set; } = string.Empty;
    public string DocumentName { get; set; } = string.Empty;
    public string DocumentUrl { get; set; } = string.Empty;
    public string Status { get; set; } = "Active";
    public DateTime posteddatetime { get; set; } = DateTime.UtcNow;
    public DateTime? updateddatetime { get; set; }
}

/// <summary>
/// Application DbContext for PostgreSQL
/// No FK relationships - child tables reference parent via SysJobUuid string
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
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.Email).HasColumnType("text");
            entity.Property(e => e.Name).HasColumnType("text");
            entity.Property(e => e.Uuid).HasColumnType("text");
            entity.Property(e => e.CollegeCode).HasColumnType("text");
            entity.Property(e => e.Batch).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // NoticeRecord
        modelBuilder.Entity<NoticeRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SuperSetIdentifier).IsUnique();
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SuperSetIdentifier).HasColumnType("text");
            entity.Property(e => e.Title).HasColumnType("text");
            entity.Property(e => e.Content).HasColumnType("text");
            entity.Property(e => e.Author).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobRecord
        modelBuilder.Entity<JobRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SuperSetJobIdentifier).IsUnique();
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SuperSetJobIdentifier).HasColumnType("text");
            entity.Property(e => e.Company).HasColumnType("text");
            entity.Property(e => e.JobProfile).HasColumnType("text");
            entity.Property(e => e.PlacementCategory).HasColumnType("text");
            entity.Property(e => e.PlacementCategoryCode).HasColumnType("text");
            entity.Property(e => e.Content).HasColumnType("text");
            entity.Property(e => e.Location).HasColumnType("text");
            entity.Property(e => e.PackageInfo).HasColumnType("text");
            entity.Property(e => e.JobDescription).HasColumnType("text");
            entity.Property(e => e.PlacementType).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobEligibilityRecord
        modelBuilder.Entity<JobEligibilityRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.Level).HasColumnType("text");
            entity.Property(e => e.Criteria).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobEligibilityCourseRecord
        modelBuilder.Entity<JobEligibilityCourseRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.CourseName).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobGenderRecord
        modelBuilder.Entity<JobGenderRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.Gender).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobSkillRecord
        modelBuilder.Entity<JobSkillRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.SkillName).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobHiringFlowRecord
        modelBuilder.Entity<JobHiringFlowRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.Sequence).HasColumnType("text");
            entity.Property(e => e.StageName).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });

        // JobDocumentRecord
        modelBuilder.Entity<JobDocumentRecord>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => e.DocumentIdentifier).IsUnique();
            entity.HasIndex(e => e.SysJobUuid);
            entity.Property(e => e.Id).HasColumnType("text");
            entity.Property(e => e.SysJobUuid).HasColumnType("text");
            entity.Property(e => e.DocumentIdentifier).HasColumnType("text");
            entity.Property(e => e.DocumentName).HasColumnType("text");
            entity.Property(e => e.DocumentUrl).HasColumnType("text");
            entity.Property(e => e.Status).HasColumnType("text");
        });
    }
}
