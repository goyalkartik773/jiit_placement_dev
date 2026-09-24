using System.Data;
using System.Text.Json;

namespace JIITPlacement.Models.App_Code
{
    public class Common
    {
        public class ReturnResponse
        {
            public bool status { get; set; }
            public string Message { get; set; }
            public object Data { get; set; }
        }

        /// <summary>
        /// Parse JSON text into a single JsonElement
        /// </summary>
        public static JsonElement ParseJson(string json)
        {
            if (string.IsNullOrEmpty(json) || json == "null") return default;
            try
            {
                return JsonDocument.Parse(json).RootElement;
            }
            catch
            {
                return default;
            }
        }

        /// <summary>
        /// Get string value from DataRow with null safety
        /// </summary>
        public static string GetString(DataRow row, string column)
        {
            return row[column] == DBNull.Value ? string.Empty : row[column].ToString() ?? string.Empty;
        }

        public static int GetInt(DataRow row, string column, int defaultValue = 0)
        {
            if (row[column] == DBNull.Value) return defaultValue;
            return Convert.ToInt32(row[column]);
        }

        public static long GetLong(DataRow row, string column, long defaultValue = 0)
        {
            if (row[column] == DBNull.Value) return defaultValue;
            return Convert.ToInt64(row[column]);
        }

        public static decimal GetDecimal(DataRow row, string column, decimal defaultValue = 0)
        {
            if (row[column] == DBNull.Value) return defaultValue;
            return Convert.ToDecimal(row[column]);
        }

        public static DateTime? GetDateTime(DataRow row, string column)
        {
            if (row[column] == DBNull.Value) return null;
            return Convert.ToDateTime(row[column]);
        }

        public static bool GetBool(DataRow row, string column, bool defaultValue = false)
        {
            if (row[column] == DBNull.Value) return defaultValue;
            return Convert.ToBoolean(row[column]);
        }
    }
}
