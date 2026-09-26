using System.Text;
using System.Text.Json.Serialization;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Models;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
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

// Admin authentication: signed JWT bearer tokens with jti-based logout revocation
builder.Services.Configure<AdminOptions>(
    builder.Configuration.GetSection(AdminOptions.SectionName));
builder.Services.Configure<JwtOptions>(
    builder.Configuration.GetSection(JwtOptions.SectionName));
builder.Services.AddSingleton<IAdminTokenService, AdminTokenService>();
builder.Services.AddSingleton<IAdminTokenRevocationStore, AdminTokenRevocationStore>();

var jwtSecret = builder.Configuration[$"{JwtOptions.SectionName}:Secret"] ?? string.Empty;
if (Encoding.UTF8.GetBytes(jwtSecret).Length < 32)
{
    throw new InvalidOperationException(
        "Jwt:Secret is missing or shorter than 32 bytes. Copy the Jwt section from appsettings.example.json " +
        "into appsettings.json (git-ignored) or into user-secrets before starting the API.");
}

var jwtIssuer = builder.Configuration[$"{JwtOptions.SectionName}:Issuer"] ?? "JIITPlacement";
var jwtAudience = builder.Configuration[$"{JwtOptions.SectionName}:Audience"] ?? "JIITPlacement";

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.MapInboundClaims = false; // keep claim names as issued (username, role, jti)
        options.RequireHttpsMetadata = false; // local development runs over http
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidIssuer = jwtIssuer,
            ValidAudience = jwtAudience,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret)),
            NameClaimType = "username",
            RoleClaimType = "role",
            ClockSkew = TimeSpan.FromMinutes(1)
        };
        options.Events = new JwtBearerEvents
        {
            OnTokenValidated = context =>
            {
                // Logout revokes the token's jti; a revoked session no longer authenticates.
                var jti = context.Principal?.FindFirst("jti")?.Value;
                if (!string.IsNullOrEmpty(jti))
                {
                    var store = context.HttpContext.RequestServices.GetRequiredService<IAdminTokenRevocationStore>();
                    if (store.IsRevoked(jti))
                        context.Fail("This session was logged out.");
                }
                return Task.CompletedTask;
            },
            OnChallenge = async context =>
            {
                // Replace the empty 401 body with the documented JSON error.
                context.HandleResponse();
                context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                context.Response.ContentType = "application/json; charset=utf-8";
                await context.Response.WriteAsync("{\"success\":false,\"message\":\"Unauthorized\"}");
            },
            OnForbidden = async context =>
            {
                context.Response.StatusCode = StatusCodes.Status403Forbidden;
                context.Response.ContentType = "application/json; charset=utf-8";
                await context.Response.WriteAsync("{\"success\":false,\"message\":\"Forbidden\"}");
            }
        };
    });
builder.Services.AddAuthorization();

// Background job-sync coordinator (single sync at a time + live status)
builder.Services.AddSingleton<IAdminSyncCoordinator, AdminSyncCoordinator>();

// Admin job deletion (records first, then the stored documents on disk)
builder.Services.AddScoped<IJobCleanupService, JobCleanupService>();

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
    options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Name = "Authorization",
        Type = SecuritySchemeType.Http,
        Scheme = "bearer",
        In = ParameterLocation.Header,
        Description = "Signed admin JWT from POST /api/admin/login"
    });
    options.AddSecurityRequirement(new OpenApiSecurityRequirement
    {
        {
            new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference
                {
                    Type = ReferenceType.SecurityScheme,
                    Id = "Bearer"
                }
            },
            Array.Empty<string>()
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

app.UseAuthentication();

app.UseAuthorization();

app.MapControllers();

app.Run();
