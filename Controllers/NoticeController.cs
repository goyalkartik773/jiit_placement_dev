using System.Data;
using JIITPlacement.Models.App_Code;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    public class NoticeController : ControllerBase
    {
        private readonly DataEntity _dataEntity;

        public NoticeController(DataEntity dataEntity)
        {
            _dataEntity = dataEntity;
        }

        [HttpGet("notices")]
        public ActionResult GetNotices(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20,
            [FromQuery] string search = "")
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                pageSize = Math.Min(pageSize, 100);

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_notices_v1",
                    page, pageSize, search
                );

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Notices fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "No notices found";
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

        /// <summary>
        /// GET /api/notices/email - notices extracted from the Gmail corpus
        /// (shortlists, selection process, hackathons, events, webinars, ...).
        /// The congratulation / final-offer data is intentionally excluded: it is
        /// shown by the Company-Wise Placement section instead.
        /// Optional ?type= filters by the classifier label (see ?facets in Data).
        /// </summary>
        [HttpGet("notices/email")]
        public ActionResult GetEmailNotices(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 20,
            [FromQuery] string search = "",
            [FromQuery] string type = "")
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                page = Math.Max(page, 1);
                pageSize = Math.Min(Math.Max(pageSize, 1), 100);
                search = (search ?? string.Empty).Trim();
                type = (type ?? string.Empty).Trim().ToUpperInvariant();

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_email_notices_v1", page, pageSize, search, type);

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Email notices fetched successfully";
                    response.Data = result;
                    return Ok(response);
                }

                response.status = true;
                response.Message = "No email notices found";
                response.Data = null;
                return Ok(response);
            }
            catch (Exception ex)
            {
                response.status = false;
                response.Message = "Error: " + ex.Message;
                return StatusCode(500, response);
            }
        }

        /// <summary>
        /// GET /api/notices/email/{id} - full detail for ONE email notice:
        /// the complete body, the parsed shortlist students, funnel counts
        /// with their evidence sentence, attachments and event extras.
        /// The list endpoint only ships a 300-char snippet; this is the
        /// "Read more" payload. Returns Data = {"found": false} for an
        /// unknown id.
        /// </summary>
        [HttpGet("notices/email/{id}")]
        public ActionResult GetEmailNoticeDetail(string id)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                id = (id ?? string.Empty).Trim();
                if (id.Length == 0)
                {
                    response.status = false;
                    response.Message = "Email id is required";
                    return BadRequest(response);
                }

                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_select_email_notice_detail_v1", id);

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Email notice detail fetched successfully";
                    response.Data = result;
                    return Ok(response);
                }

                response.status = true;
                response.Message = "No email notice found";
                response.Data = null;
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
