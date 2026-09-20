using System.Text;
using System.Text.RegularExpressions;
using Google.Apis.Gmail.v1.Data;
using JIITPlacement.Models;

namespace JIITPlacement.Services
{
    public interface IEmailPreprocessor
    {
        /// <summary>
        /// Parse a raw Gmail message into a ParsedEmail model.
        /// </summary>
        ParsedEmail ParseMessage(Message message, string? sourceGroup, string? sourceGroupEmail);

        /// <summary>
        /// Build combined extraction content from parsed email.
        /// </summary>
        string BuildCombinedContent(ParsedEmail parsed);
    }

    public class EmailPreprocessor : IEmailPreprocessor
    {
        private readonly ILogger<EmailPreprocessor> _logger;

        public EmailPreprocessor(ILogger<EmailPreprocessor> logger)
        {
            _logger = logger;
        }

        // Tracking domains to ignore
        private static readonly HashSet<string> TrackingDomains = new(StringComparer.OrdinalIgnoreCase)
        {
            "google-analytics.com", "doubleclick.net", "facebook.com", "twitter.com",
            "linkedin.com", "pixel.", "tracker.", "beacon.", "click.",
            "mailchimp.com", "sendgrid.net", "mandrillapp.com"
        };

        // Unsubscribe/ignore patterns
        private static readonly string[] IgnorePatterns = new[]
        {
            "unsubscribe", "opt-out", "manage preferences", "view in browser",
            "social media icons", "follow us on"
        };

        /// <summary>
        /// Parse a raw Gmail message into structured data.
        /// </summary>
        public ParsedEmail ParseMessage(Message message, string? sourceGroup, string? sourceGroupEmail)
        {
            var parsed = new ParsedEmail
            {
                GmailMessageId = message.Id ?? "",
                SourceGroup = sourceGroup,
                SourceGroupEmail = sourceGroupEmail,
                Snippet = message.Snippet,
                LabelIds = message.LabelIds != null ? string.Join(",", message.LabelIds) : null,
                RawPayload = System.Text.Json.JsonSerializer.Serialize(message)
            };

            // Extract headers
            if (message.Payload?.Headers != null)
            {
                foreach (var header in message.Payload.Headers)
                {
                    switch (header.Name?.ToLowerInvariant())
                    {
                        case "from": parsed.Sender = header.Value; break;
                        case "to": parsed.Recipient = header.Value; break;
                        case "cc": parsed.Cc = header.Value; break;
                        case "bcc": parsed.Bcc = header.Value; break;
                        case "reply-to": parsed.ReplyTo = header.Value; break;
                        case "subject": parsed.Subject = header.Value; break;
                        case "date": parsed.ReceivedAt = header.Value; break;
                    }
                }
            }

            // Extract body content recursively
            if (message.Payload != null)
            {
                ExtractParts(message.Payload, parsed);
            }

            // Clean the content
            parsed.CleanedContent = CleanHtml(parsed.BodyHtml, parsed.BodyText);

            // Extract links
            parsed.Links = ExtractLinks(parsed.BodyHtml);

            // Check for attachments
            parsed.HasAttachments = message.Payload?.Parts?.Any(p =>
                !string.IsNullOrEmpty(p.Filename) && p.Body?.AttachmentId != null) ?? false;

            return parsed;
        }

        /// <summary>
        /// Recursively extract parts from a Gmail message payload.
        /// </summary>
        private void ExtractParts(MessagePart part, ParsedEmail parsed)
        {
            if (part == null) return;

            // Handle multipart types
            if (part.Parts != null && part.Parts.Count > 0)
            {
                foreach (var subPart in part.Parts)
                {
                    ExtractParts(subPart, parsed);
                }
                return;
            }

            // Extract body data
            if (part.Body?.Data != null)
            {
                var decoded = DecodeBase64Url(part.Body.Data);

                switch (part.MimeType?.ToLowerInvariant())
                {
                    case "text/plain":
                        parsed.BodyText += decoded;
                        break;
                    case "text/html":
                        parsed.BodyHtml += decoded;
                        break;
                }
            }

            // Collect attachment metadata
            if (!string.IsNullOrEmpty(part.Filename) && part.Body?.AttachmentId != null)
            {
                parsed.Attachments.Add(new ParsedAttachment
                {
                    AttachmentId = part.Body.AttachmentId,
                    Filename = SanitizeFilename(part.Filename),
                    MimeType = part.MimeType ?? "application/octet-stream",
                    FileSize = part.Body.Size ?? 0
                });
            }
        }

        /// <summary>
        /// Decode Gmail's URL-safe base64 encoding.
        /// </summary>
        private string DecodeBase64Url(string data)
        {
            try
            {
                // Convert URL-safe base64 to standard base64
                var standardBase64 = data.Replace('-', '+').Replace('_', '/');

                // Add padding if necessary
                switch (standardBase64.Length % 4)
                {
                    case 2: standardBase64 += "=="; break;
                    case 3: standardBase64 += "="; break;
                }

                var bytes = Convert.FromBase64String(standardBase64);
                return Encoding.UTF8.GetString(bytes);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to decode base64url data");
                return "";
            }
        }

        /// <summary>
        /// Clean HTML content to produce readable text while preserving structure.
        /// </summary>
        private string CleanHtml(string html, string? plainText)
        {
            if (string.IsNullOrWhiteSpace(html))
                return plainText ?? "";

            try
            {
                var doc = new HtmlAgilityPack.HtmlDocument();
                doc.LoadHtml(html);

                // Remove script, style, hidden elements
                RemoveNodes(doc, "//script");
                RemoveNodes(doc, "//style");
                RemoveNodes(doc, "//noscript");
                RemoveNodes(doc, "//*[contains(@style,'display:none') or contains(@style,'visibility:hidden')]");

                // Remove tracking images
                RemoveNodes(doc, "//img[contains(@width,'0') or contains(@height,'0')]");

                // Get text content
                var text = doc.DocumentNode.InnerText;

                // Normalize whitespace
                text = Regex.Replace(text, @"\s+", " ").Trim();

                // Decode HTML entities
                text = System.Net.WebUtility.HtmlDecode(text);

                // If cleaned HTML is too short, fall back to plain text
                if (text.Length < 50 && !string.IsNullOrWhiteSpace(plainText))
                {
                    return plainText;
                }

                return text;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to clean HTML, using plain text fallback");
                return plainText ?? "";
            }
        }

        private void RemoveNodes(HtmlAgilityPack.HtmlDocument doc, string xpath)
        {
            var nodes = doc.DocumentNode.SelectNodes(xpath);
            if (nodes != null)
            {
                foreach (var node in nodes.ToList())
                {
                    node.Remove();
                }
            }
        }

        /// <summary>
        /// Extract relevant links from HTML content.
        /// </summary>
        private List<ParsedLink> ExtractLinks(string? html)
        {
            var links = new List<ParsedLink>();
            if (string.IsNullOrWhiteSpace(html)) return links;

            try
            {
                var doc = new HtmlAgilityPack.HtmlDocument();
                doc.LoadHtml(html);

                var anchorNodes = doc.DocumentNode.SelectNodes("//a[@href]");
                if (anchorNodes == null) return links;

                foreach (var anchor in anchorNodes)
                {
                    var href = anchor.GetAttributeValue("href", "");
                    var label = anchor.InnerText?.Trim() ?? "";

                    if (string.IsNullOrWhiteSpace(href)) continue;

                    // Skip tracking and internal links
                    if (IsTrackingUrl(href)) continue;
                    if (href.StartsWith("mailto:", StringComparison.OrdinalIgnoreCase)) continue;
                    if (href.StartsWith("tel:", StringComparison.OrdinalIgnoreCase)) continue;

                    var linkType = ClassifyLink(href, label);
                    links.Add(new ParsedLink
                    {
                        Url = href,
                        Label = label,
                        LinkType = linkType
                    });
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to extract links from HTML");
            }

            return links;
        }

        private bool IsTrackingUrl(string url)
        {
            try
            {
                var uri = new Uri(url);
                return TrackingDomains.Any(d => uri.Host.Contains(d, StringComparison.OrdinalIgnoreCase));
            }
            catch
            {
                return false;
            }
        }

        private string ClassifyLink(string url, string label)
        {
            var urlLower = url.ToLowerInvariant();
            var labelLower = label.ToLowerInvariant();

            if (urlLower.Contains("apply") || urlLower.Contains("register") || urlLower.Contains("signup"))
                return "registration";
            if (urlLower.Contains("job") || urlLower.Contains("career") || urlLower.Contains("jd"))
                return "job_description";
            if (urlLower.Contains("document") || urlLower.Contains("attachment") || urlLower.Contains("download"))
                return "document";
            if (urlLower.Contains("meeting") || urlLower.Contains("zoom") || urlLower.Contains("teams"))
                return "meeting";
            if (urlLower.Contains("application"))
                return "application";
            if (labelLower.Contains("official") || urlLower.Contains("official"))
                return "official_information";

            return "unknown";
        }

        /// <summary>
        /// Build combined extraction content from parsed email.
        /// This is what gets sent to the LLM for classification and extraction.
        /// </summary>
        public string BuildCombinedContent(ParsedEmail parsed)
        {
            var sb = new StringBuilder();

            sb.AppendLine("=== EMAIL INFORMATION ===");
            sb.AppendLine($"From: {parsed.Sender}");
            sb.AppendLine($"To: {parsed.Recipient}");
            if (!string.IsNullOrEmpty(parsed.Cc))
                sb.AppendLine($"Cc: {parsed.Cc}");
            sb.AppendLine($"Subject: {parsed.Subject}");
            sb.AppendLine($"Date: {parsed.ReceivedAt}");
            sb.AppendLine();

            if (!string.IsNullOrEmpty(parsed.SourceGroup))
            {
                sb.AppendLine($"Source Group: {parsed.SourceGroup} ({parsed.SourceGroupEmail})");
                sb.AppendLine();
            }

            // Content - prefer cleaned HTML-derived text
            if (!string.IsNullOrWhiteSpace(parsed.CleanedContent))
            {
                sb.AppendLine("=== CONTENT ===");
                sb.AppendLine(parsed.CleanedContent);
            }
            else if (!string.IsNullOrWhiteSpace(parsed.BodyText))
            {
                sb.AppendLine("=== CONTENT ===");
                sb.AppendLine(parsed.BodyText);
            }

            // Links
            if (parsed.Links.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("=== LINKS ===");
                foreach (var link in parsed.Links)
                {
                    sb.AppendLine($"[{link.LinkType}] {link.Label}: {link.Url}");
                }
            }

            // Attachments
            if (parsed.Attachments.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("=== ATTACHMENTS ===");
                foreach (var att in parsed.Attachments)
                {
                    sb.AppendLine($"- {att.Filename} ({att.MimeType}, {att.FileSize} bytes)");
                    if (!string.IsNullOrEmpty(att.ExtractedText))
                    {
                        sb.AppendLine($"  Extracted Text: {att.ExtractedText}");
                    }
                }
            }

            return sb.ToString();
        }

        /// <summary>
        /// Sanitize a filename to prevent path traversal.
        /// </summary>
        private string SanitizeFilename(string filename)
        {
            // Remove path separators and dangerous characters
            var sanitized = Path.GetFileName(filename);
            sanitized = Regex.Replace(sanitized, @"[<>:""/\\|?*]", "_");
            sanitized = sanitized.Trim('.', ' ');

            if (string.IsNullOrWhiteSpace(sanitized))
                sanitized = "attachment";

            return sanitized;
        }
    }
}
