using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JIITPlacement.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "JobDocuments",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    DocumentIdentifier = table.Column<string>(type: "text", nullable: false),
                    DocumentName = table.Column<string>(type: "text", nullable: false),
                    DocumentUrl = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobDocuments", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobEligibilities",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    Level = table.Column<string>(type: "text", nullable: false),
                    Criteria = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobEligibilities", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobEligibilityCourses",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    CourseName = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobEligibilityCourses", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobGenders",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    Gender = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobGenders", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobHiringFlows",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    Sequence = table.Column<string>(type: "text", nullable: false),
                    StageName = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobHiringFlows", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Jobs",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SuperSetJobIdentifier = table.Column<string>(type: "text", nullable: false),
                    Company = table.Column<string>(type: "text", nullable: false),
                    JobProfile = table.Column<string>(type: "text", nullable: false),
                    PlacementCategory = table.Column<string>(type: "text", nullable: false),
                    PlacementCategoryCode = table.Column<string>(type: "text", nullable: false),
                    Content = table.Column<string>(type: "text", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Deadline = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Location = table.Column<string>(type: "text", nullable: false),
                    Package = table.Column<float>(type: "real", nullable: false),
                    PackageInfo = table.Column<string>(type: "text", nullable: false),
                    JobDescription = table.Column<string>(type: "text", nullable: false),
                    PlacementType = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Jobs", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobSkills",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SysJobUuid = table.Column<string>(type: "text", nullable: false),
                    SkillName = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobSkills", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Notices",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    SuperSetIdentifier = table.Column<string>(type: "text", nullable: false),
                    Title = table.Column<string>(type: "text", nullable: false),
                    Content = table.Column<string>(type: "text", nullable: false),
                    Author = table.Column<string>(type: "text", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Notices", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "SupersetAccounts",
                columns: table => new
                {
                    Id = table.Column<string>(type: "text", nullable: false),
                    Email = table.Column<string>(type: "text", nullable: false),
                    Name = table.Column<string>(type: "text", nullable: false),
                    Uuid = table.Column<string>(type: "text", nullable: false),
                    CollegeCode = table.Column<string>(type: "text", nullable: false),
                    Batch = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    posteddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updateddatetime = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SupersetAccounts", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_JobDocuments_DocumentIdentifier",
                table: "JobDocuments",
                column: "DocumentIdentifier",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_JobDocuments_SysJobUuid",
                table: "JobDocuments",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_JobEligibilities_SysJobUuid",
                table: "JobEligibilities",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_JobEligibilityCourses_SysJobUuid",
                table: "JobEligibilityCourses",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_JobGenders_SysJobUuid",
                table: "JobGenders",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_JobHiringFlows_SysJobUuid",
                table: "JobHiringFlows",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_SuperSetJobIdentifier",
                table: "Jobs",
                column: "SuperSetJobIdentifier",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_JobSkills_SysJobUuid",
                table: "JobSkills",
                column: "SysJobUuid");

            migrationBuilder.CreateIndex(
                name: "IX_Notices_SuperSetIdentifier",
                table: "Notices",
                column: "SuperSetIdentifier",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_SupersetAccounts_Email",
                table: "SupersetAccounts",
                column: "Email",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_SupersetAccounts_Uuid",
                table: "SupersetAccounts",
                column: "Uuid",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "JobDocuments");

            migrationBuilder.DropTable(
                name: "JobEligibilities");

            migrationBuilder.DropTable(
                name: "JobEligibilityCourses");

            migrationBuilder.DropTable(
                name: "JobGenders");

            migrationBuilder.DropTable(
                name: "JobHiringFlows");

            migrationBuilder.DropTable(
                name: "Jobs");

            migrationBuilder.DropTable(
                name: "JobSkills");

            migrationBuilder.DropTable(
                name: "Notices");

            migrationBuilder.DropTable(
                name: "SupersetAccounts");
        }
    }
}
