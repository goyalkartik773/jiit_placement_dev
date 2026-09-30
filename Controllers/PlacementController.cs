using System.Data;
using System.Text.Json;
using JIITPlacement.Models.App_Code;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    /// <summary>
    /// Public, read-only dashboard APIs (same { status, Message, Data } envelope
    /// as the job APIs):
    ///   GET /api/placements/company-wise?page&amp;pageSize&amp;search
    ///   GET /api/placements/branch-stats
    ///   GET /api/placements/jobs/{jobId}/placed-students
    ///
    /// Both read job_placed_students, which is only ever written by the
    /// admin-triggered POST /api/admin/jobs/sync-offer-students.
    /// </summary>
    [ApiController]
    [Route("api")]
    public class PlacementController : ControllerBase
    {
        private readonly DataEntity _dataEntity;
        private readonly ILogger<PlacementController> _logger;

        public PlacementController(DataEntity dataEntity, ILogger<PlacementController> logger)
        {
            _dataEntity = dataEntity;
            _logger = logger;
        }

        /// <summary>GET /api/placements/company-wise - one row per company that has a job.</summary>
        [HttpGet("placements/company-wise")]
        public ActionResult GetCompanyWise(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20,
            [FromQuery] string search = "")
        {
            var response = new Common.ReturnResponse();
            try
            {
                page = Math.Max(page, 1);
                pageSize = Math.Min(Math.Max(pageSize, 1), 100);
                search = (search ?? string.Empty).Trim();

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_company_placements_v1", page, pageSize, search);

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Company-wise placements fetched successfully";
                    response.Data = result;
                    return Ok(response);
                }

                response.status = true;
                response.Message = "No placements found";
                response.Data = null;
                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load company-wise placements");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// GET /api/placements/branch-stats - branch-wise statistics for the
        /// graduating batch (placement rate, package quartiles, distribution,
        /// monthly timeline). Read-only; the whole payload is computed by
        /// fn_api_select_branch_stats_v1, which hardcodes the head-count
        /// denominators taken from the reference repo's BATCH_CONFIGS.
        /// </summary>
        [HttpGet("placements/branch-stats")]
        public ActionResult GetBranchStats()
        {
            var response = new Common.ReturnResponse();
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_select_branch_stats_v1");

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Branch statistics fetched successfully";
                    response.Data = result;
                    return Ok(response);
                }

                response.status = true;
                response.Message = "No statistics found";
                response.Data = null;
                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load branch statistics");
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// GET /api/placements/jobs/{jobId}/placed-students - student-level detail
        /// for one job (job id or Superset job identifier).
        /// </summary>
        [HttpGet("placements/jobs/{jobId}/placed-students")]
        public ActionResult GetPlacedStudents(string jobId)
        {
            var response = new Common.ReturnResponse();
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFNParam(
                    "fn_api_select_placed_students_v1", ("jobid", jobId));

                if (dt.Rows.Count == 0)
                {
                    response.status = false;
                    response.Message = "Job not found";
                    return NotFound(response);
                }

                var result = Common.ParseJson(dt.Rows[0][0].ToString());
                if (!IsSuccess(result, out string message))
                {
                    response.status = false;
                    response.Message = message;
                    return NotFound(response);
                }

                response.status = true;
                response.Message = "Placed students fetched successfully";
                response.Data = new
                {
                    job = GetProperty(result, "job"),
                    placedCount = GetInt32(result, "placedCount"),
                    students = GetProperty(result, "students")
                };
                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load placed students for job {JobId}", jobId);
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        internal static bool IsSuccess(JsonElement result, out string message)
        {
            message = string.Empty;
            if (result.ValueKind != JsonValueKind.Object) return false;
            if (result.TryGetProperty("message", out var m) && m.ValueKind == JsonValueKind.String)
                message = m.GetString() ?? string.Empty;
            return result.TryGetProperty("status", out var s)
                   && s.ValueKind == JsonValueKind.String
                   && s.GetString() == "SUCCESS";
        }

        internal static JsonElement GetProperty(JsonElement element, string name)
        {
            return element.TryGetProperty(name, out var value) ? value : default;
        }

        internal static int GetInt32(JsonElement element, string name)
        {
            return element.TryGetProperty(name, out var value)
                   && value.ValueKind == JsonValueKind.Number
                   && value.TryGetInt32(out int parsed)
                ? parsed
                : 0;
        }
    }
}
