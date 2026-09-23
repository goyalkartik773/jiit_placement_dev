/** Formatting helpers — all inputs come straight from the backend contract. */

const dateFormatter = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

const dateTimeFormatter = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "20 Sep 2026" — returns "—" for null/invalid dates. */
export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? dateFormatter.format(date) : '—';
}

/** "20 Sep 2026, 15:55" — returns "—" for null/invalid dates. */
export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? dateTimeFormatter.format(date) : '—';
}

/** Relative label like "2 days ago"; returns null when the date is unknown. */
export function formatRelative(value: string | null | undefined): string | null {
  const date = parseDate(value);
  if (!date) return null;

  const diffMs = date.getTime() - Date.now();
  const absMs = Math.abs(diffMs);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const minutes = Math.round(absMs / 60_000);

  if (minutes < 1) return rtf.format(Math.sign(diffMs) * 0, 'minute');
  if (minutes < 60) return rtf.format(Math.sign(diffMs) * minutes, 'minute');
  const hours = Math.round(minutes / 60);
  if (hours < 24) return rtf.format(Math.sign(diffMs) * hours, 'hour');
  const days = Math.round(hours / 24);
  if (days < 30) return rtf.format(Math.sign(diffMs) * days, 'day');
  const months = Math.round(days / 30);
  if (months < 12) return rtf.format(Math.sign(diffMs) * months, 'month');
  return rtf.format(Math.sign(diffMs) * Math.round(months / 12), 'year');
}

export function isPast(value: string | null | undefined): boolean {
  const date = parseDate(value);
  return date ? date.getTime() < Date.now() : false;
}

/** ₹10,00,000 — returns null when package is missing/zero. */
export function formatINR(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) return null;
  return currencyFormatter.format(value);
}

/** "10 LPA" derived from INR (backend: 8 LPA = 800000). Null when unknown. */
export function formatLpa(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) return null;
  const lpa = value / 100_000;
  const rounded = Math.round(lpa * 100) / 100;
  return `${rounded} LPA`;
}

/** Human file size: 75.7 KB */
export function formatBytes(bytes: number | null | undefined): string | null {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes) || bytes <= 0) return null;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  let index = 0;
  let value = bytes;
  while (value >= 1024 && index < sizes.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${Math.round(value * 10) / 10} ${sizes[index]}`;
}

/** Short file-type label from a MIME type: "application/pdf" -> "PDF". */
export function fileTypeLabel(contentType: string | null | undefined): string {
  if (!contentType) return 'FILE';
  const mime = contentType.toLowerCase().split(';')[0].trim();
  const map: Record<string, string> = {
    'application/pdf': 'PDF',
    'application/msword': 'DOC',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'application/vnd.ms-excel': 'XLS',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/zip': 'ZIP',
    'application/x-zip-compressed': 'ZIP',
    'image/png': 'PNG',
    'image/jpeg': 'JPEG',
    'image/gif': 'GIF',
    'image/webp': 'WEBP',
    'text/plain': 'TXT',
    'application/octet-stream': 'FILE',
  };
  return map[mime] ?? mime.replace('application/', '').toUpperCase().slice(0, 8);
}

/** Icon category for a MIME type, used to pick a file glyph. */
export function fileIconKind(contentType: string | null | undefined): 'pdf' | 'sheet' | 'doc' | 'image' | 'archive' | 'file' {
  const mime = (contentType ?? '').toLowerCase().split(';')[0].trim();
  if (mime === 'application/pdf') return 'pdf';
  if (mime.includes('sheet') || mime.includes('excel')) return 'sheet';
  if (mime.includes('word') || mime.includes('document')) return 'doc';
  if (mime.startsWith('image/')) return 'image';
  if (mime.includes('zip') || mime.includes('compressed')) return 'archive';
  return 'file';
}

/** Truncated plain-text preview (already stripped of HTML by stripHtml). */
export function excerpt(text: string | null | undefined, maxLength = 200): string {
  if (!text) return '';
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trimEnd()}…`;
}

/** Initials for the company avatar: "Infosys" -> "IN", "GreyB Services" -> "GS". */
export function initials(name: string | null | undefined): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
