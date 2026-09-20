using System.Text.Json.Serialization;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Models;
using JIITPlacement.Services;
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
builder.Services.Configure<FileStorageOptions>(
    builder.Configuration.GetSection(FileStorageOptions.SectionName));
builder.Services.Configure<GoogleGmailSettings>(
    builder.Configuration.GetSection(GoogleGmailSettings.SectionName));
builder.Services.Configure<GeminiSettings>(
    builder.Configuration.GetSection(GeminiSettings.SectionName));

// Register DataEntity (database access layer) - replaces EF Core DbContext
builder.Services.AddScoped<DataEntity>(sp =>
{
    var config = sp.GetRequiredService<IConfiguration>();
    var logger = sp.GetRequiredService<ILogger<DataEntity>>();
    return new DataEntity(config, logger);
});

// Configure HttpClient for SuperSet
builder.Services.AddHttpClient("SuperSet", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["SuperSet:BaseUrl"] ?? "https://app.joinsuperset.com");
    client.Timeout = TimeSpan.FromSeconds(30);
    client.DefaultRequestHeaders.Add("User-Agent", "JIITPlacement/1.0");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

// Configure HttpClient for Gemini API
builder.Services.AddHttpClient("Gemini", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["Gemini:BaseUrl"] ?? "https://generativelanguage.googleapis.com");
    client.Timeout = TimeSpan.FromSeconds(120);
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

// Register application services
builder.Services.AddScoped<ISuperSetService, SuperSetService>();
builder.Services.AddScoped<ISuperSetSyncService, SuperSetSyncService>();
builder.Services.AddScoped<IFileStorageService, FileStorageService>();

// Gmail integration services
builder.Services.AddScoped<IGmailService, GmailSyncService>();
builder.Services.AddScoped<IEmailPreprocessor, EmailPreprocessor>();
builder.Services.AddScoped<IAttachmentProcessor, AttachmentProcessor>();
builder.Services.AddScoped<IEmailExtractionService, EmailExtractionService>();
builder.Services.AddScoped<IEmailValidationService, EmailValidationService>();
builder.Services.AddScoped<IPlacementExtractionService, PlacementExtractionService>();

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

app.Run();
