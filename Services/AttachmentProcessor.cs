using System.Text;
using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface IAttachmentProcessor
    {
        /// <summary>
        /// Extract text content from an attachment.
        /// </summary>
        Task<string> ExtractTextAsync(ParsedAttachment attachment);
    }

    public class AttachmentProcessor : IAttachmentProcessor
    {
        private readonly ILogger<AttachmentProcessor> _logger;

        public AttachmentProcessor(ILogger<AttachmentProcessor> logger)
        {
            _logger = logger;
        }

        /// <summary>
        /// Extract text from an attachment based on its MIME type.
        /// Supports: PDF, DOCX, XLSX, plain text, images (stub for OCR).
        /// </summary>
        public async Task<string> ExtractTextAsync(ParsedAttachment attachment)
        {
            if (attachment.Data == null || attachment.Data.Length == 0)
            {
                _logger.LogWarning("No data available for attachment {Filename}", attachment.Filename);
                return "";
            }

            try
            {
                var mimeType = attachment.MimeType?.ToLowerInvariant() ?? "";

                if (mimeType.Contains("pdf"))
                {
                    return await ExtractPdfTextAsync(attachment.Data);
                }
                else if (mimeType.Contains("wordprocessingml") || mimeType.Contains("msword") ||
                         attachment.Filename.EndsWith(".docx", StringComparison.OrdinalIgnoreCase) ||
                         attachment.Filename.EndsWith(".doc", StringComparison.OrdinalIgnoreCase))
                {
                    return await ExtractDocxTextAsync(attachment.Data);
                }
                else if (mimeType.Contains("spreadsheetml") || mimeType.Contains("excel") ||
                         mimeType.Contains("ms-excel") ||
                         attachment.Filename.EndsWith(".xlsx", StringComparison.OrdinalIgnoreCase))
                {
                    return await ExtractXlsxTextAsync(attachment.Data);
                }
                else if (mimeType.StartsWith("text/"))
                {
                    return Encoding.UTF8.GetString(attachment.Data);
                }
                else if (mimeType.StartsWith("image/"))
                {
                    // OCR would go here - for now return placeholder
                    _logger.LogInformation("Image attachment detected ({Filename}), OCR not yet implemented",
                        attachment.Filename);
                    return $"[Image attachment: {attachment.Filename}]";
                }

                _logger.LogInformation("Unsupported attachment type: {MimeType} for {Filename}",
                    mimeType, attachment.Filename);
                return $"[Unsupported file type: {mimeType}]";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to extract text from attachment {Filename}", attachment.Filename);
                return $"[Extraction failed: {ex.Message}]";
            }
        }

        /// <summary>
        /// Extract text from PDF using iTextSharp.
        /// </summary>
        private Task<string> ExtractPdfTextAsync(byte[] data)
        {
            try
            {
                using var reader = new iTextSharp.text.pdf.PdfReader(data);
                var sb = new StringBuilder();

                for (int i = 1; i <= reader.NumberOfPages; i++)
                {
                    var pageDictionary = reader.GetPageN(i);
                    if (pageDictionary != null)
                    {
                        var contentStream = reader.GetPageContent(i);
                        if (contentStream != null)
                        {
                            var text = Encoding.UTF8.GetString(contentStream);
                            text = CleanPdfRawText(text);
                            if (!string.IsNullOrWhiteSpace(text))
                                sb.AppendLine(text);
                        }
                    }
                }

                var result = sb.ToString().Trim();
                if (string.IsNullOrWhiteSpace(result))
                {
                    _logger.LogInformation("PDF appears to be image-only (no extractable text)");
                    return Task.FromResult("[Scanned/image PDF - no extractable text]");
                }

                return Task.FromResult(result);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to extract PDF text");
                return Task.FromResult($"[PDF extraction failed: {ex.Message}]");
            }
        }

        private string CleanPdfRawText(string raw)
        {
            // Remove PDF operators and keep text content
            var lines = raw.Split('\n');
            var result = new StringBuilder();
            foreach (var line in lines)
            {
                var trimmed = line.Trim();
                if (string.IsNullOrEmpty(trimmed)) continue;
                // Skip PDF operator lines
                if (trimmed.StartsWith("BT") || trimmed.StartsWith("ET") ||
                    trimmed.StartsWith("Tf") || trimmed.StartsWith("Tm") ||
                    trimmed.StartsWith("Td") || trimmed.StartsWith("TD") ||
                    trimmed.StartsWith("T*") || trimmed.StartsWith("TJ") ||
                    trimmed.StartsWith("Tj") || trimmed.StartsWith("'") ||
                    trimmed.StartsWith("\"") || trimmed.StartsWith("q") ||
                    trimmed.StartsWith("Q") || trimmed.StartsWith("cm") ||
                    trimmed.StartsWith("re") || trimmed.StartsWith("f") ||
                    trimmed.StartsWith("n") || trimmed.StartsWith("W") ||
                    trimmed.StartsWith("S") || trimmed.StartsWith("B") ||
                    trimmed.StartsWith("[]") || trimmed.StartsWith("0."))
                    continue;

                // Extract text between parentheses (PDF text objects)
                var textMatches = System.Text.RegularExpressions.Regex.Matches(trimmed, @"\(([^)]*)\)");
                foreach (System.Text.RegularExpressions.Match match in textMatches)
                {
                    result.Append(match.Groups[1].Value);
                }

                // Also check for hex-encoded text
                var hexMatches = System.Text.RegularExpressions.Regex.Matches(trimmed, @"<([0-9A-Fa-f]+)>");
                foreach (System.Text.RegularExpressions.Match match in hexMatches)
                {
                    try
                    {
                        var hex = match.Groups[1].Value;
                        if (hex.Length % 2 == 0)
                        {
                            var bytes = new byte[hex.Length / 2];
                            for (int j = 0; j < hex.Length; j += 2)
                                bytes[j / 2] = Convert.ToByte(hex.Substring(j, 2), 16);
                            result.Append(Encoding.UTF8.GetString(bytes));
                        }
                    }
                    catch { }
                }
            }
            return result.ToString();
        }

        /// <summary>
        /// Extract text from DOCX using DocumentFormat.OpenXml.
        /// </summary>
        private Task<string> ExtractDocxTextAsync(byte[] data)
        {
            try
            {
                using var stream = new MemoryStream(data);
                using var doc = DocumentFormat.OpenXml.Packaging.WordprocessingDocument.Open(stream, false);

                var sb = new StringBuilder();

                // Extract paragraphs
                if (doc.MainDocumentPart?.Document?.Body != null)
                {
                    foreach (var para in doc.MainDocumentPart.Document.Body.Elements<DocumentFormat.OpenXml.Wordprocessing.Paragraph>())
                    {
                        var text = para.InnerText?.Trim();
                        if (!string.IsNullOrWhiteSpace(text))
                        {
                            sb.AppendLine(text);
                        }
                    }
                }

                // Extract tables
                if (doc.MainDocumentPart?.Document?.Body != null)
                {
                    foreach (var table in doc.MainDocumentPart.Document.Body.Descendants<DocumentFormat.OpenXml.Wordprocessing.Table>())
                    {
                        sb.AppendLine();
                        sb.AppendLine("[Table]");
                        foreach (var row in table.Elements<DocumentFormat.OpenXml.Wordprocessing.TableRow>())
                        {
                            var cells = row.Elements<DocumentFormat.OpenXml.Wordprocessing.TableCell>()
                                .Select(c => c.InnerText?.Trim() ?? "")
                                .ToArray();
                            sb.AppendLine(string.Join(" | ", cells));
                        }
                    }
                }

                return Task.FromResult(sb.ToString().Trim());
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to extract DOCX text");
                return Task.FromResult($"[DOCX extraction failed: {ex.Message}]");
            }
        }

        /// <summary>
        /// Extract text from XLSX using DocumentFormat.OpenXml.
        /// </summary>
        private Task<string> ExtractXlsxTextAsync(byte[] data)
        {
            try
            {
                using var stream = new MemoryStream(data);
                using var doc = DocumentFormat.OpenXml.Packaging.SpreadsheetDocument.Open(stream, false);

                var sb = new StringBuilder();

                if (doc.WorkbookPart?.Workbook?.Sheets != null)
                {
                    foreach (var sheet in doc.WorkbookPart.Workbook.Sheets.Elements<DocumentFormat.OpenXml.Spreadsheet.Sheet>())
                    {
                        sb.AppendLine($"=== Sheet: {sheet.Name} ===");

                        var sheetPart = doc.WorkbookPart.GetPartById(sheet.Id?.Value ?? "") as DocumentFormat.OpenXml.Packaging.WorksheetPart;
                        if (sheetPart?.Worksheet?.Descendants<DocumentFormat.OpenXml.Spreadsheet.SheetData>() == null)
                            continue;

                        foreach (var sheetData in sheetPart.Worksheet.Descendants<DocumentFormat.OpenXml.Spreadsheet.SheetData>())
                        {
                            foreach (var row in sheetData.Elements<DocumentFormat.OpenXml.Spreadsheet.Row>())
                            {
                                var cells = row.Elements<DocumentFormat.OpenXml.Spreadsheet.Cell>()
                                    .Select(c => c.InnerText?.Trim() ?? "")
                                    .ToArray();
                                sb.AppendLine(string.Join(" | ", cells));
                            }
                        }
                    }
                }

                return Task.FromResult(sb.ToString().Trim());
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to extract XLSX text");
                return Task.FromResult($"[XLSX extraction failed: {ex.Message}]");
            }
        }
    }
}
