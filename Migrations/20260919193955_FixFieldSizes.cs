using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JIITPlacement.Migrations
{
    /// <inheritdoc />
    public partial class FixFieldSizes : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "PackageInfo",
                table: "Jobs",
                type: "text",
                nullable: false,
                oldClrType: typeof(string),
                oldType: "character varying(512)",
                oldMaxLength: 512);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "PackageInfo",
                table: "Jobs",
                type: "character varying(512)",
                maxLength: 512,
                nullable: false,
                oldClrType: typeof(string),
                oldType: "text");
        }
    }
}
