using System.Data;
using System.Reflection;
using System.Text.Json;
using Microsoft.AspNetCore.StaticFiles;
using System.Globalization;
using Npgsql;

namespace JIITPlacement.Models.App_Code
{
    public class Common
    {
        private string[] _ParaName;

        public class ReturnResponse
        {
            public bool status { get; set; }
            public string Message { get; set; }
            public object Data { get; set; }
        }

        public class ReturnResponse_Pagination
        {
            public bool status { get; set; }
            public string Message { get; set; }
            public object Data { get; set; }
            public long totalRecords { get; set; }
            public int pageNumber { get; set; }
            public int pageSize { get; set; }
        }

        #region ParaNameArray()
        public void ParaNameArray(params string[] paraname)
        {
            _ParaName = paraname;
        }
        #endregion

        #region Set_SelectSP
        public void Set_SelectSP(string SPName, object[] ParaArray, NpgsqlCommand cmd)
        {
            cmd.CommandTimeout = 1200;
            for (int i = 0; i < ParaArray.Length; i++)
            {
                cmd.Parameters.AddWithValue(_ParaName.GetValue(i).ToString(), ParaArray.GetValue(i));
            }
        }
        #endregion

        public List<T> ConvertDataTable<T>(DataTable dt)
        {
            List<T> data = new List<T>();
            foreach (DataRow row in dt.Rows)
            {
                T item = GetItem<T>(row);
                data.Add(item);
            }
            return data;
        }

        public T GetItem<T>(DataRow dr)
        {
            Type temp = typeof(T);
            T obj = Activator.CreateInstance<T>();
            try
            {
                foreach (DataColumn column in dr.Table.Columns)
                {
                    foreach (PropertyInfo pro in temp.GetProperties())
                    {
                        if (pro.Name.ToLower() == column.ColumnName.ToLower())
                            pro.SetValue(obj, dr[column.ColumnName], null);
                        else
                            continue;
                    }
                }
            }
            catch (Exception ex) { }
            return obj;
        }

        public string AsciiToHex(string ascii)
        {
            char[] charValues = ascii.ToCharArray();
            string hexOutput = "";
            foreach (char _eachChar in charValues)
            {
                int value = Convert.ToInt32(_eachChar);
                hexOutput += String.Format("{0:X}", value);
            }
            return hexOutput;
        }

        public string ConvertHex(String hexString)
        {
            try
            {
                string ascii = string.Empty;
                for (int i = 0; i < hexString.Length; i += 2)
                {
                    String hs = string.Empty;
                    hs = hexString.Substring(i, 2);
                    uint decval = System.Convert.ToUInt32(hs, 16);
                    char character = System.Convert.ToChar(decval);
                    ascii += character;
                }
                return ascii;
            }
            catch (Exception ex) { Console.WriteLine(ex.Message); }
            return string.Empty;
        }

        public string GetSizeInMemory(long bytesize)
        {
            string[] sizes = { "B", "KB", "MB", "GB", "TB" };
            double len = Convert.ToDouble(bytesize);
            int order = 0;
            while (len >= 1024D && order < sizes.Length - 1)
            {
                order++;
                len /= 1024;
            }
            return string.Format(CultureInfo.CurrentCulture, "{0:0.##} {1}", len, sizes[order]);
        }

        public string GetMimeType(string fileName)
        {
            var provider = new FileExtensionContentTypeProvider();
            if (!provider.TryGetContentType(fileName, out var contentType))
            {
                contentType = "application/octet-stream";
            }
            return contentType;
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

        /// <summary>
        /// Serialize object to JSON string
        /// </summary>
        public static string ToJson(object obj)
        {
            if (obj == null) return "[]";
            return JsonSerializer.Serialize(obj, new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });
        }
    }
}
