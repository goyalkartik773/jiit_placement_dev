using System.Data;
using System.Text.Json;
using JIITPlacement.Models.App_Code;
using JIITPlacement.Services;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    public class JobController : ControllerBase
    {
        private readonly DataEntity _dataEntity;
        private readonly IFileStorageService _fileStorageService;

        public JobController(DataEntity dataEntity, IFileStorageService fileStorageService)
        {
            _dataEntity = dataEntity;
            _fileStorageService = fileStorageService;
        }

        [HttpGet("jobs")]
        public ActionResult GetJobs(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20,
            [FromQuery] string company = "",
            [FromQuery] string search = "")
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                pageSize = Math.Min(pageSize, 100);

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_jobs_v1",
                    page, pageSize, company, search
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Jobs fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No jobs found";
                    response.Data = null;
                }
                return Ok(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        [HttpGet("jobs/{id}")]
        public ActionResult GetJob(string id)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_jobdetail_v1",
                    id
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    bool success = result.TryGetProperty("status", out var s) && s.GetString() == "SUCCESS";

                    if (!success)
                    {
                        response.status = false;
                        response.Message = result.TryGetProperty("message", out var m) ? m.GetString() ?? "Not found" : "Not found";
                        return NotFound(response);
                    }

                    response.status = true;
                    response.Message = "Job fetched successfully";
                    response.Data = result;
                    return Ok(response);
                }

                response.status = false;
                response.Message = "Job not found";
                return NotFound(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// Download a job document that was stored locally during synchronization.
        /// </summary>
        [HttpGet("jobs/{jobId}/documents/{documentId}")]
        [ProducesResponseType(typeof(FileStreamResult), 200)]
        public async Task<ActionResult> DownloadJobDocument(string jobId, string documentId)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                // 1. Find the document record
                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_jobdetail_v1",
                    jobId
                );

                if (dt.Rows.Count == 0)
                {
                    response.status = false;
                    response.Message = "Job not found";
                    return NotFound(response);
                }

                string json = dt.Rows[0][0].ToString();
                var result = Common.ParseJson(json);

                if (!result.TryGetProperty("status", out var s) || s.GetString() != "SUCCESS")
                {
                    response.status = false;
                    response.Message = "Job not found";
                    return NotFound(response);
                }

                var jobData = result.GetProperty("data");
                if (!jobData.TryGetProperty("documents", out var docsElement) || docsElement.ValueKind == JsonValueKind.Null)
                {
                    response.status = false;
                    response.Message = "No documents found for this job";
                    return NotFound(response);
                }

                // 2. Find the specific document
                JsonElement? foundDoc = null;
                foreach (var doc in docsElement.EnumerateArray())
                {
                    if (doc.TryGetProperty("id", out var docId) && docId.GetString() == documentId)
                    {
                        foundDoc = doc;
                        break;
                    }
                }

                if (foundDoc == null)
                {
                    response.status = false;
                    response.Message = "Document not found";
                    return NotFound(response);
                }

                var docElement = foundDoc.Value;

                // 3. Get the relative path
                string relativePath = "";
                if (docElement.TryGetProperty("documentpath", out var pathProp))
                    relativePath = pathProp.GetString() ?? "";

                if (string.IsNullOrEmpty(relativePath))
                {
                    response.status = false;
                    response.Message = "Document has not been downloaded locally yet";
                    return NotFound(response);
                }

                // 4. Validate path is safe and inside root
                var physicalPath = _fileStorageService.GetPhysicalPath(relativePath);
                if (physicalPath == null)
                {
                    response.status = false;
                    response.Message = "Invalid document path";
                    return BadRequest(response);
                }

                // 5. Check file exists
                if (!System.IO.File.Exists(physicalPath))
                {
                    response.status = false;
                    response.Message = "Document file not found on server";
                    return NotFound(response);
                }

                // 6. Get content type and filename
                string docName = "";
                if (docElement.TryGetProperty("documentname", out var nameProp))
                    docName = nameProp.GetString() ?? "document";

                string contentType = "application/octet-stream";
                if (docElement.TryGetProperty("contenttype", out var ctProp))
                    contentType = ctProp.GetString() ?? "application/octet-stream";

                // 7. Return the file
                var stream = new FileStream(physicalPath, FileMode.Open, FileAccess.Read, FileShare.Read);
                return File(stream, contentType, docName);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }
    }
}
