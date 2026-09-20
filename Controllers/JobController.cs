using System.Data;
using JIITPlacement.Models;
using JIITPlacement.Models.App_Code;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    public class JobController : ControllerBase
    {
        private readonly DataEntity _dataEntity;

        public JobController(DataEntity dataEntity)
        {
            _dataEntity = dataEntity;
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

        [HttpPost("jobs")]
        public ActionResult PostJob([FromBody] Cls_Job.JobRequest request)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                // 1. Save main job record
                DataTable jobDt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_post_job_v001",
                    request.SysJobUuid,
                    request.SuperSetJobIdentifier,
                    request.Company,
                    request.JobProfile,
                    request.PlacementCategory,
                    request.PlacementCategoryCode,
                    request.Content,
                    request.CreatedAt,
                    request.Deadline,
                    request.Location,
                    request.Package,
                    request.PackageInfo,
                    request.JobDescription,
                    request.PlacementType
                );

                string jobResult = jobDt.Rows[0][0].ToString();
                var jobJson = Common.ParseJson(jobResult);
                bool jobSuccess = jobJson.TryGetProperty("status", out var js) && js.GetString() == "SUCCESS";

                if (!jobSuccess)
                {
                    response.status = false;
                    response.Message = jobJson.TryGetProperty("message", out var jm) ? jm.GetString() ?? "Failed" : "Failed";
                    return BadRequest(response);
                }

                // Get the job UUID
                string jobUuid = string.Empty;
                if (jobJson.TryGetProperty("id", out var idProp))
                    jobUuid = idProp.GetString() ?? string.Empty;

                // 2. Save eligibility marks
                if (request.EligibilityMarks != null && request.EligibilityMarks.Count > 0)
                {
                    foreach (var mark in request.EligibilityMarks)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobeligibility_v001",
                            jobUuid, mark.Level, mark.Criteria.ToString()
                        );
                    }
                }

                // 3. Save eligibility courses
                if (request.EligibilityCourses != null)
                {
                    foreach (var course in request.EligibilityCourses)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobeligibilitycourse_v001",
                            jobUuid, course
                        );
                    }
                }

                // 4. Save genders
                if (request.AllowedGenders != null)
                {
                    foreach (var gender in request.AllowedGenders)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobgender_v001",
                            jobUuid, gender
                        );
                    }
                }

                // 5. Save skills
                if (request.RequiredSkills != null)
                {
                    foreach (var skill in request.RequiredSkills)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobskill_v001",
                            jobUuid, skill
                        );
                    }
                }

                // 6. Save hiring flow
                if (request.HiringFlow != null)
                {
                    foreach (var stage in request.HiringFlow)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobhiringflow_v001",
                            jobUuid, stage.Sequence.ToString(), stage.StageName
                        );
                    }
                }

                // 7. Save documents
                if (request.Documents != null)
                {
                    foreach (var doc in request.Documents)
                    {
                        _dataEntity.ExecuteDataTableFN(
                            "fn_api_post_jobdocument_v001",
                            jobUuid, doc.DocumentIdentifier, doc.DocumentName, doc.DocumentUrl
                        );
                    }
                }

                response.status = true;
                response.Message = "Job saved successfully";
                response.Data = jobJson;
                return Ok(response);
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
