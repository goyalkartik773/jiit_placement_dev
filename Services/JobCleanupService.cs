using System.Diagnostics;
using JIITPlacement.Models.App_Code;

namespace JIITPlacement.Services
{
    public class JobCleanupService : IJobCleanupService
    {
        private readonly DataEntity _dataEntity;
        private readonly IFileStorageService _storage;
        private readonly ILogger<JobCleanupService> _logger;

        public JobCleanupService(
            DataEntity dataEntity,
            IFileStorageService storage,
            ILogger<JobCleanupService> logger)
        {
            _dataEntity = dataEntity;
            _storage = storage;
            _logger = logger;
        }

        public async Task<JobCleanupResult> DeleteAllJobsAsync()
        {
            var total = Stopwatch.StartNew();
            var phases = new List<JobCleanupPhase>();

            // 1. Records: one transactional function removes all job rows and
            //    returns the document paths those rows owned.
            var dbWatch = Stopwatch.StartNew();
            int jobsDeleted;
            int documentRowsDeleted;
            List<string> documentPaths;
            try
            {
                var dt = await _dataEntity.ExecuteDataTableFNAsync("fn_api_delete_all_jobs_v001");
                var json = dt.Rows.Count > 0 ? dt.Rows[0][0]?.ToString() : null;
                if (string.IsNullOrEmpty(json))
                {
                    return new JobCleanupResult
                    {
                        Success = false,
                        Message = "The delete function returned no result",
                        DurationMs = total.ElapsedMilliseconds
                    };
                }

                var parsed = Common.ParseJson(json);
                jobsDeleted = parsed.GetProperty("jobsDeleted").GetInt32();
                documentRowsDeleted = parsed.GetProperty("documentRowsDeleted").GetInt32();
                documentPaths = parsed.GetProperty("documentPaths")
                    .EnumerateArray()
                    .Select(p => p.GetString())
                    .Where(p => !string.IsNullOrEmpty(p))
                    .Select(p => p!)
                    .ToList();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to delete job records");
                return new JobCleanupResult
                {
                    Success = false,
                    Message = "Failed to delete jobs: " + ex.Message,
                    DurationMs = total.ElapsedMilliseconds
                };
            }

            dbWatch.Stop();
            phases.Add(new JobCleanupPhase { Phase = "delete_records", DurationMs = dbWatch.ElapsedMilliseconds });

            // 2. Files: remove the documents those records owned, staying
            //    strictly inside the configured storage root.
            var fileWatch = Stopwatch.StartNew();
            int filesDeleted = 0, filesMissing = 0, filesFailed = 0;

            foreach (var relativePath in documentPaths)
            {
                try
                {
                    var physicalPath = _storage.GetPhysicalPath(relativePath);
                    if (physicalPath == null)
                    {
                        filesFailed++;
                        _logger.LogWarning("Refused to delete path outside the storage root: {Path}", relativePath);
                        continue;
                    }

                    if (!File.Exists(physicalPath))
                    {
                        filesMissing++;
                        continue;
                    }

                    File.Delete(physicalPath);
                    filesDeleted++;
                }
                catch (Exception ex)
                {
                    filesFailed++;
                    _logger.LogWarning(ex, "Failed to delete document {Path}", relativePath);
                }
            }

            // Sweep anything left under the Jobs folder (e.g. orphaned files
            // whose rows were already gone) so no job document survives a
            // delete-all. The next sync recreates the folder on demand.
            var jobsFolder = _storage.GetPhysicalPath("Jobs");
            if (jobsFolder != null && Directory.Exists(jobsFolder))
            {
                foreach (var orphan in Directory.EnumerateFiles(jobsFolder, "*", SearchOption.AllDirectories))
                {
                    try
                    {
                        File.Delete(orphan);
                        filesDeleted++;
                    }
                    catch (Exception ex)
                    {
                        filesFailed++;
                        _logger.LogWarning(ex, "Failed to delete leftover document {Path}", orphan);
                    }
                }

                TryDeleteEmptyTree(jobsFolder);
            }

            fileWatch.Stop();
            phases.Add(new JobCleanupPhase { Phase = "delete_files", DurationMs = fileWatch.ElapsedMilliseconds });

            total.Stop();
            _logger.LogInformation(
                "Job cleanup finished: {Jobs} jobs, {Rows} document rows, {Files} files deleted ({Missing} already absent, {Failed} failed)",
                jobsDeleted, documentRowsDeleted, filesDeleted, filesMissing, filesFailed);

            return new JobCleanupResult
            {
                Success = true,
                JobsDeleted = jobsDeleted,
                DocumentRowsDeleted = documentRowsDeleted,
                FilesDeleted = filesDeleted,
                FilesMissing = filesMissing,
                FilesFailed = filesFailed,
                DurationMs = total.ElapsedMilliseconds,
                Phases = phases
            };
        }

        /// <summary>
        /// Best-effort removal of a now-empty folder tree (deepest first).
        /// Only ever called with a folder directly under the storage root,
        /// so the root itself can never be touched.
        /// </summary>
        private static void TryDeleteEmptyTree(string folder)
        {
            try
            {
                if (!Directory.Exists(folder))
                    return;

                var directories = Directory
                    .GetDirectories(folder, "*", SearchOption.AllDirectories)
                    .OrderByDescending(d => d.Split(Path.DirectorySeparatorChar).Length);

                foreach (var directory in directories)
                {
                    try
                    {
                        if (!Directory.EnumerateFileSystemEntries(directory).Any())
                            Directory.Delete(directory);
                    }
                    catch
                    {
                        // locked or already gone — keep going
                    }
                }

                if (!Directory.EnumerateFileSystemEntries(folder).Any())
                    Directory.Delete(folder);
            }
            catch
            {
                // Nothing left to clean up.
            }
        }
    }
}
