using System.Net.Http;
using JIITPlacement.Models;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.Extensions.Options;

namespace JIITPlacement.Services
{
    public class FileStorageService : IFileStorageService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly FileStorageOptions _options;
        private readonly ILogger<FileStorageService> _logger;
        private readonly FileExtensionContentTypeProvider _contentTypeProvider = new();

        public FileStorageService(
            IHttpClientFactory httpClientFactory,
            IOptions<FileStorageOptions> options,
            ILogger<FileStorageService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _options = options.Value;
            _logger = logger;
        }

        public void EnsureRootDirectory()
        {
            if (!string.IsNullOrEmpty(_options.RootPath) && !Directory.Exists(_options.RootPath))
            {
                Directory.CreateDirectory(_options.RootPath);
                _logger.LogInformation("Created root storage directory: {RootPath}", _options.RootPath);
            }
        }

        public string GetContentType(string fileName)
        {
            if (_contentTypeProvider.TryGetContentType(fileName, out var contentType))
                return contentType;
            return "application/octet-stream";
        }

        public string? GetPhysicalPath(string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath))
                return null;

            // Normalize separators
            var normalizedRelative = relativePath.Replace('/', '\\').TrimStart('\\');

            // Resolve root
            var rootFull = Path.GetFullPath(_options.RootPath);

            // Combine and resolve
            var combined = Path.Combine(rootFull, normalizedRelative);
            var full = Path.GetFullPath(combined);

            // Security check: must be inside root
            if (!full.StartsWith(rootFull, StringComparison.OrdinalIgnoreCase))
            {
                _logger.LogWarning("Path traversal attempt blocked: {RelativePath}", relativePath);
                return null;
            }

            return full;
        }

        public bool DocumentExists(string jobUuid, string documentIdentifier)
        {
            var relativePath = BuildRelativePath(jobUuid, documentIdentifier);
            var physicalPath = GetPhysicalPath(relativePath);
            return physicalPath != null && File.Exists(physicalPath);
        }

        public async Task<(string relativePath, string contentType, long fileSize)?> DownloadDocumentAsync(
            string temporaryUrl,
            string jobUuid,
            string documentIdentifier,
            string documentName)
        {
            EnsureRootDirectory();

            var safeFileName = SanitizeFileName(documentName);
            if (string.IsNullOrEmpty(safeFileName))
                safeFileName = $"{documentIdentifier}.bin";

            var relativePath = Path.Combine("Jobs", jobUuid, "Documents", safeFileName);
            var physicalPath = GetPhysicalPath(relativePath);

            if (physicalPath == null)
            {
                _logger.LogWarning("Invalid path for document {DocId}: {RelPath}", documentIdentifier, relativePath);
                return null;
            }

            // Check if already downloaded
            if (File.Exists(physicalPath))
            {
                var existingSize = new FileInfo(physicalPath).Length;
                _logger.LogInformation("Document already exists, skipping download: {RelPath}", relativePath);
                return (relativePath, GetContentType(safeFileName), existingSize);
            }

            // Create directory if needed
            var dir = Path.GetDirectoryName(physicalPath);
            if (dir != null && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            var tempPath = physicalPath + ".download";

            try
            {
                var client = _httpClientFactory.CreateClient("SuperSet");
                client.Timeout = TimeSpan.FromMinutes(5);

                using var response = await client.GetAsync(temporaryUrl, HttpCompletionOption.ResponseHeadersRead);
                response.EnsureSuccessStatusCode();

                var contentType = response.Content.Headers.ContentType?.MediaType ?? GetContentType(safeFileName);
                var fileSize = response.Content.Headers.ContentLength ?? 0;

                // Stream to temp file
                await using var stream = await response.Content.ReadAsStreamAsync();
                await using var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, true);
                await stream.CopyToAsync(fileStream);
                await fileStream.FlushAsync();
                await fileStream.DisposeAsync();

                // Get actual file size if header was 0
                if (fileSize == 0)
                    fileSize = new FileInfo(tempPath).Length;

                // Atomic move: temp -> final
                File.Move(tempPath, physicalPath, overwrite: true);

                _logger.LogInformation(
                    "Downloaded document {DocName} for job {JobUuid} to {RelPath} ({Size} bytes)",
                    documentName, jobUuid, relativePath, fileSize);

                return (relativePath, contentType, fileSize);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to download document {DocName} for job {JobUuid}", documentName, jobUuid);

                // Cleanup temp file
                try { if (File.Exists(tempPath)) File.Delete(tempPath); } catch { }

                return null;
            }
        }

        /// <summary>
        /// Build relative path for a document given jobUuid and documentIdentifier.
        /// </summary>
        private static string BuildRelativePath(string jobUuid, string documentIdentifier)
        {
            var safeId = documentIdentifier.Replace('/', '_').Replace('\\', '_');
            return Path.Combine("Jobs", jobUuid, "Documents", safeId);
        }

        /// <summary>
        /// Sanitize a filename for safe use on Windows filesystem.
        /// </summary>
        public static string SanitizeFileName(string fileName)
        {
            if (string.IsNullOrWhiteSpace(fileName))
                return string.Empty;

            // Remove path traversal
            fileName = Path.GetFileName(fileName);

            // Replace invalid chars
            var invalid = Path.GetInvalidFileNameChars();
            var sanitized = new char[fileName.Length];
            for (int i = 0; i < fileName.Length; i++)
            {
                sanitized[i] = Array.IndexOf(invalid, fileName[i]) >= 0 ? '_' : fileName[i];
            }
            var result = new string(sanitized).Trim().Trim('.');

            // Limit length
            if (result.Length > 200)
            {
                var ext = Path.GetExtension(result);
                result = result.Substring(0, 200 - ext.Length) + ext;
            }

            return result;
        }
    }
}
