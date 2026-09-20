using System.Text.Json.Serialization;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Models.SuperSet;
using JIITPlacement.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi.Models;

var builder = WebApplication.CreateBuilder(args);

// Load User Secrets in development
if (builder.Environment.IsDevelopment())
{
    builder.Configuration.AddUserSecrets<Program>(optional: true);
}

// Configure strongly-typed options
builder.Services.Configure<SuperSetOptions>(
    builder.Configuration.GetSection(SuperSetOptions.SectionName));
builder.Services.Configure<SyncScheduleOptions>(
    builder.Configuration.GetSection(SyncScheduleOptions.SectionName));

// Configure PostgreSQL
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

// Configure HttpClient for SuperSet
builder.Services.AddHttpClient("SuperSet", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["SuperSet:BaseUrl"] ?? "https://app.joinsuperset.com");
    client.Timeout = TimeSpan.FromSeconds(30);
    client.DefaultRequestHeaders.Add("User-Agent", "JIITPlacement/1.0");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

// Register application services
builder.Services.AddScoped<ISuperSetService, SuperSetService>();
builder.Services.AddScoped<ISuperSetSyncService, SuperSetSyncService>();

// Register background sync service
builder.Services.AddHostedService<SuperSetSyncBackgroundService>();

// Configure Controllers with JSON options
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.PropertyNamingPolicy = null;
        options.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    });

// Configure Swagger/OpenAPI
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "JIIT Placement API",
        Version = "v1",
        Description = "JIIT Placement Management System API - SuperSet Integration",
        Contact = new OpenApiContact
        {
            Name = "JIIT Placement Team"
        }
    });
});

// Configure CORS for React frontend (later)
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowReactApp", policy =>
    {
        policy.WithOrigins("http://localhost:3000", "http://localhost:5173")
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/swagger/v1/swagger.json", "JIIT Placement API v1");
        options.RoutePrefix = "swagger";
    });
}

app.UseCors("AllowReactApp");

app.UseAuthorization();

app.MapControllers();

// Auto-apply migrations on startup (optional - can be removed in production)
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    try
    {
        dbContext.Database.Migrate();
    }
    catch (Exception ex)
    {
        var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();
        logger.LogWarning(ex, "Could not apply database migrations. Database may need to be created manually.");
    }
}

app.Run();
