using System.Data;
using System.Data.Common;
using Npgsql;

namespace JIITPlacement.Models.App_Code
{
    public class DataEntity : Common
    {
        private readonly string pgConnection;
        private readonly ILogger<DataEntity>? _logger;

        // Constructor that takes IConfiguration
        public DataEntity(IConfiguration configuration)
        {
            pgConnection = configuration.GetConnectionString("PostgreSQL")
                ?? configuration.GetConnectionString("DefaultConnection")
                ?? throw new ArgumentNullException("PostgreSQL connection string not found");
        }

        // Constructor with logger
        public DataEntity(IConfiguration configuration, ILogger<DataEntity> logger) : this(configuration)
        {
            _logger = logger;
        }

        // Default constructor that loads configuration automatically
        public DataEntity() : this(new ConfigurationBuilder()
            .AddJsonFile("appsettings.json")
            .AddJsonFile($"appsettings.{Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ?? "Production"}.json", optional: true)
            .Build())
        {
        }

        public DataTable ExecuteDataTableFN(string fn_Name, params object[] ParaArray)
        {
            DataTable dt = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = conn.BeginTransaction();
            try
            {
                var strPrams = String.Join(",", ParaArray.Select(p => string.Format("'{0}'", string.Format("{0}", p).Replace('\'', ' '))));
                cmd.CommandText = "select * from " + fn_Name + "(" + strPrams + ");";
                cmd.Connection = conn;
                cmd.CommandTimeout = 300000;
                NpgsqlDataReader dataReader = cmd.ExecuteReader();
                dt.Load(dataReader);
                trans.Commit();
                conn.Close();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[DataEntity] ExecuteDataTableFN error: {ex.Message}");
                trans.Rollback();
                conn.Close();
            }
            return dt;
        }

        public DataTable ExecuteDataTableFN(string fn_Name)
        {
            DataTable dt = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = conn.BeginTransaction();
            try
            {
                cmd.CommandText = "select * from " + fn_Name + "();";
                cmd.Connection = conn;
                cmd.CommandTimeout = 300000;
                NpgsqlDataReader dataReader = cmd.ExecuteReader();
                dt.Load(dataReader);
                trans.Commit();
                conn.Close();
            }
            catch (Exception ex)
            {
                trans.Rollback();
                conn.Close();
            }
            return dt;
        }

        public async Task<DataTable> ExecuteDataTableFNAsync(string fn_Name, params object[] ParaArray)
        {
            DataTable dt = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = await conn.BeginTransactionAsync();
            var strPrams = String.Join(",", ParaArray.Select(p => string.Format("'{0}'", string.Format("{0}", p).Replace('\'', ' '))));
            cmd.CommandText = "select * from " + fn_Name + "(" + strPrams + ");";
            cmd.Connection = conn;
            cmd.CommandTimeout = 300000;
            NpgsqlDataReader dataReader = await cmd.ExecuteReaderAsync();
            dt.Load(dataReader);
            trans.Commit();
            conn.Close();
            return dt;
        }

        public DataTable ExecuteDataTableSP(string sp_Name, params object[] ParaArray)
        {
            DataTable dt = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            cmd.CommandTimeout = 300000;
            NpgsqlTransaction trans = conn.BeginTransaction();
            var strPrams = String.Join(",", ParaArray.Select(p => string.Format("'{0}'", string.Format("{0}", p).Replace('\'', ' '))));
            cmd.CommandText = "Call " + sp_Name + "(" + strPrams + ");";
            cmd.Connection = conn;
            NpgsqlDataReader dataReader = cmd.ExecuteReader();
            dt.Load(dataReader);
            trans.Commit();
            conn.Close();
            return dt;
        }

        public async Task<DataTable> ExecuteDataTableSPAsync(string sp_Name, params object[] ParaArray)
        {
            DataTable dt = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = await conn.BeginTransactionAsync();
            var strPrams = String.Join(",", ParaArray.Select(p => string.Format("'{0}'", string.Format("{0}", p).Replace('\'', ' '))));
            cmd.CommandText = "Call " + sp_Name + "(" + strPrams + ");";
            cmd.Connection = conn;
            cmd.CommandTimeout = 300000;
            NpgsqlDataReader dataReader = await cmd.ExecuteReaderAsync();
            dt.Load(dataReader);
            trans.Commit();
            conn.Close();
            return dt;
        }

        /// <summary>
        /// Execute a PostgreSQL function with properly parameterized queries (safe for special characters).
        /// </summary>
        public DataTable ExecuteDataTableFNParam(string fn_Name, params (string name, object? value)[] parameters)
        {
            DataTable dt = new DataTable();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = conn.BeginTransaction();
            try
            {
                var paramNames = new List<string>();
                using var cmd = new NpgsqlCommand();
                for (int i = 0; i < parameters.Length; i++)
                {
                    var pname = $"@p{i}";
                    paramNames.Add(pname);
                    cmd.Parameters.AddWithValue(pname, parameters[i].value ?? DBNull.Value);
                }
                cmd.CommandText = $"SELECT * FROM {fn_Name}({string.Join(",", paramNames)})";
                cmd.Connection = conn;
                cmd.Transaction = trans;
                cmd.CommandTimeout = 300;
                using var reader = cmd.ExecuteReader();
                dt.Load(reader);
                trans.Commit();
            }
            catch (Exception ex)
            {
                _logger?.LogError(ex, "ExecuteDataTableFNParam error on {FnName}", fn_Name);
                System.Diagnostics.Debug.WriteLine($"[DataEntity] ExecuteDataTableFNParam error on {fn_Name}: {ex.Message}");
                trans.Rollback();
            }
            finally { conn.Close(); }
            return dt;
        }

        public DataSet ExecuteDataSetFN(string fn_Name)
        {
            DataSet ds = new DataSet();
            DataTable dt = new DataTable();
            DataTable dt1 = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            cmd.CommandTimeout = 300000;
            NpgsqlTransaction trans = conn.BeginTransaction();
            try
            {
                cmd.CommandText = "select * from " + fn_Name + "();";
                cmd.Connection = conn;
                NpgsqlDataReader dataReader = cmd.ExecuteReader();
                dt.Load(dataReader);
                foreach (DataRow row in dt.Rows)
                {
                    dt1 = new DataTable();
                    string cursor = row[fn_Name].ToString();
                    cmd.CommandText = "fetch all in \"" + cursor + "\"";
                    cmd.CommandType = CommandType.Text;
                    NpgsqlDataReader cursorDataReader = cmd.ExecuteReader();
                    dt1.Load(dataReader);
                    ds.Tables.Add(dt1);
                }
                trans.Commit();
                conn.Close();
            }
            catch (Exception ex)
            {
                trans.Rollback();
                conn.Close();
            }
            return ds;
        }

        public DataSet ExecuteDataSetFN(string fn_Name, params object[] ParaArray)
        {
            DataSet ds = new DataSet();
            DataTable dt = new DataTable();
            DataTable dt1 = new DataTable();
            NpgsqlCommand cmd = new NpgsqlCommand();
            NpgsqlConnection conn = new NpgsqlConnection(pgConnection);
            conn.Open();
            NpgsqlTransaction trans = conn.BeginTransaction();
            try
            {
                var strPrams = String.Join(",", ParaArray.Select(p => string.Format("'{0}'", string.Format("{0}", p).Replace('\'', ' '))));
                cmd.CommandText = "select * from " + fn_Name + "(" + strPrams + ");";
                cmd.Connection = conn;
                cmd.CommandTimeout = 300000;
                NpgsqlDataReader dataReader = cmd.ExecuteReader();
                dt.Load(dataReader);
                foreach (DataRow row in dt.Rows)
                {
                    dt1 = new DataTable();
                    string cursor = row[fn_Name].ToString();
                    cmd.CommandText = "fetch all in \"" + cursor + "\"";
                    cmd.CommandType = CommandType.Text;
                    NpgsqlDataReader cursorDataReader = cmd.ExecuteReader();
                    dt1.Load(dataReader);
                    ds.Tables.Add(dt1);
                }
                trans.Commit();
                conn.Close();
            }
            catch (Exception ex)
            {
                trans.Rollback();
                conn.Close();
            }
            return ds;
        }
    }
}
