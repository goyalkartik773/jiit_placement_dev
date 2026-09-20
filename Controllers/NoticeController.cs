using System.Data;
using JIITPlacement.Models;
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

        [HttpPost("notices")]
        public ActionResult PostNotice([FromBody] Cls_Notice.NoticeRequest request)
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN(
                    "fn_api_post_notice_v001",
                    request.SysIdentifier,
                    request.Title,
                    request.Content,
                    request.Author,
                    request.CreatedAt,
                    request.UpdatedAt,
                    request.PostedBy
                );

                string result = dt.Rows[0][0].ToString();
                var jsonResult = Common.ParseJson(result);
                response.status = jsonResult.TryGetProperty("status", out var s) && s.GetString() == "SUCCESS";
                response.Message = jsonResult.TryGetProperty("message", out var m) ? m.GetString() ?? result : result;
                response.Data = jsonResult;
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
