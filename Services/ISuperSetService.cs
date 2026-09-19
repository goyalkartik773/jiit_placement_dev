using JIITPlacement.Models.SuperSet;

namespace JIITPlacement.Services;

public interface ISuperSetService
{
    Task<SuperSetLoginResponse> LoginAsync(string username, string password);
    Task<List<SuperSetNoticeDto>> GetNoticesAsync(string uuid, string sessionKey);
    Task<List<SuperSetJobBasicDto>> GetJobListingsBasicAsync(string uuid, string sessionKey);
    Task<SuperSetJobDetailDto?> GetJobDetailsAsync(string uuid, string sessionKey, string jobId);
    Task<string?> GetDocumentUrlAsync(string uuid, string sessionKey, string jobId, string documentId);
}
