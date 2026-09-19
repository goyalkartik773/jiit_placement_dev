using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

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
                name: "Jobs",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    SuperSetJobIdentifier = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    Company = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    JobProfile = table.Column<string>(type: "character varying(512)", maxLength: 512, nullable: false),
                    PlacementCategory = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    PlacementCategoryCode = table.Column<int>(type: "integer", nullable: false),
                    Content = table.Column<string>(type: "text", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Deadline = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Location = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    Package = table.Column<float>(type: "real", nullable: false),
                    PackageInfo = table.Column<string>(type: "character varying(512)", maxLength: 512, nullable: false),
                    JobDescription = table.Column<string>(type: "text", nullable: false),
                    PlacementType = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    CreatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    UpdatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Jobs", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Notices",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    SuperSetIdentifier = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    Title = table.Column<string>(type: "character varying(512)", maxLength: 512, nullable: false),
                    Content = table.Column<string>(type: "text", nullable: false),
                    Author = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    CreatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    UpdatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Notices", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "SupersetAccounts",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Email = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    Name = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    Uuid = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    CollegeCode = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
                    Batch = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    IsActive = table.Column<bool>(type: "boolean", nullable: false),
                    CreatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    UpdatedOn = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SupersetAccounts", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "JobDocuments",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    DocumentIdentifier = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    DocumentName = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false),
                    DocumentUrl = table.Column<string>(type: "character varying(1024)", maxLength: 1024, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobDocuments", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobDocuments_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JobEligibilities",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    Level = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: false),
                    Criteria = table.Column<float>(type: "real", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobEligibilities", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobEligibilities_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JobEligibilityCourses",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    CourseName = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobEligibilityCourses", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobEligibilityCourses_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JobGenders",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    Gender = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobGenders", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobGenders_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JobHiringFlows",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    Sequence = table.Column<int>(type: "integer", nullable: false),
                    StageName = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobHiringFlows", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobHiringFlows_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JobSkills",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    JobRecordId = table.Column<int>(type: "integer", nullable: false),
                    SkillName = table.Column<string>(type: "character varying(256)", maxLength: 256, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JobSkills", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JobSkills_Jobs_JobRecordId",
                        column: x => x.JobRecordId,
                        principalTable: "Jobs",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_JobDocuments_DocumentIdentifier",
                table: "JobDocuments",
                column: "DocumentIdentifier",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_JobDocuments_JobRecordId",
                table: "JobDocuments",
                column: "JobRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_JobEligibilities_JobRecordId",
                table: "JobEligibilities",
                column: "JobRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_JobEligibilityCourses_JobRecordId",
                table: "JobEligibilityCourses",
                column: "JobRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_JobGenders_JobRecordId",
                table: "JobGenders",
                column: "JobRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_JobHiringFlows_JobRecordId",
                table: "JobHiringFlows",
                column: "JobRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_SuperSetJobIdentifier",
                table: "Jobs",
                column: "SuperSetJobIdentifier",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_JobSkills_JobRecordId",
                table: "JobSkills",
                column: "JobRecordId");

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
                name: "JobSkills");

            migrationBuilder.DropTable(
                name: "Notices");

            migrationBuilder.DropTable(
                name: "SupersetAccounts");

            migrationBuilder.DropTable(
                name: "Jobs");
        }
    }
}
