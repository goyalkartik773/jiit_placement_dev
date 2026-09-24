using System.Data;
using JIITPlacement.Models.App_Code;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JIITPlacement.Controllers
{
    [ApiController]
    [Route("api")]
    [Authorize] // aggregate stats are admin-only
    public class DashboardController : ControllerBase
    {
        private readonly DataEntity _dataEntity;

        public DashboardController(DataEntity dataEntity)
        {
            _dataEntity = dataEntity;
        }

        [HttpGet("dashboard")]
        public ActionResult GetDashboard()
        {
            Common.ReturnResponse response = new Common.ReturnResponse();
            try
            {
                DataTable dt = _dataEntity.ExecuteDataTableFN("fn_api_select_dashboard_v1");

                if (dt.Rows.Count > 0)
                {
                    string json = dt.Rows[0][0].ToString();
                    var result = Common.ParseJson(json);
                    response.status = true;
                    response.Message = "Dashboard fetched successfully";
                    response.Data = result;
                }
                else
                {
                    response.status = true;
                    response.Message = "Dashboard empty";
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
    }
}
