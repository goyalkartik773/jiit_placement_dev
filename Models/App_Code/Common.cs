namespace JIITPlacement.Models.App_Code;

/// <summary>
/// Common API response wrapper
/// </summary>
public class ApiResponse<T>
{
    public bool Success { get; set; }
    public string Message { get; set; } = string.Empty;
    public T? Data { get; set; }
    public List<string> Errors { get; set; } = new();
    
    public static ApiResponse<T> Ok(T data, string message = "Success")
    {
        return new ApiResponse<T> { Success = true, Message = message, Data = data };
    }
    
    public static ApiResponse<T> Fail(string message, List<string>? errors = null)
    {
        return new ApiResponse<T> { Success = false, Message = message, Errors = errors ?? new() };
    }
}

/// <summary>
/// Sync result statistics
/// </summary>
public class SyncResult
{
    public bool Success { get; set; }
    public string Message { get; set; } = string.Empty;
    public int Fetched { get; set; }
    public int Inserted { get; set; }
    public int Updated { get; set; }
    public int Skipped { get; set; }
    public int Failed { get; set; }
}

/// <summary>
/// Paginated response wrapper
/// </summary>
public class PaginatedResponse<T>
{
    public List<T> Items { get; set; } = new();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalPages => (int)Math.Ceiling(TotalCount / (double)PageSize);
    public bool HasPrevious => Page > 1;
    public bool HasNext => Page < TotalPages;
}
