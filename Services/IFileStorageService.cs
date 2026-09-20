using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface IFileStorageService
    {
        /// <summary>
        /// Ensure the root storage directory exists.
        /// </summary>
        void EnsureRootDirectory();

        /// <summary>
        /// Download a document from a temporary signed URL and save it locally.
        /// Returns (relativePath, contentType, fileSize) or null on failure.
        /// </summary>
        Task<(string relativePath, string contentType, long fileSize)?> DownloadDocumentAsync(
            string temporaryUrl,
            string jobUuid,
            string documentIdentifier,
            string documentName);

        /// <summary>
        /// Check if a document already exists locally and in the database.
        /// Returns true if both file and DB record exist.
        /// </summary>
        bool DocumentExists(string jobUuid, string documentIdentifier);

        /// <summary>
        /// Get the full physical path for a relative document path.
        /// Validates that the path stays within the configured root.
        /// Returns null if path traversal is detected.
        /// </summary>
        string? GetPhysicalPath(string relativePath);

        /// <summary>
        /// Get the MIME content type for a filename.
        /// </summary>
        string GetContentType(string fileName);
    }
}
