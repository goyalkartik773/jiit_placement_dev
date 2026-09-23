import { absoluteUrl } from './apiClient';
import { ApiError } from './apiClient';
import type { JobDocument } from '../types/job.types';

/**
 * Document service — consumes the existing download endpoint:
 *   GET /api/jobs/{jobId}/documents/{documentId}   (returns raw file bytes)
 *
 * Files are fetched as blobs so the UI can:
 *   - verify the download actually succeeded (and surface real errors), and
 *   - open PDFs/images inline via object URLs even though the backend sends
 *     `Content-Disposition: attachment` (which would otherwise force a download).
 */

/** MIME types that can be meaningfully displayed in a browser tab. */
const VIEWABLE_TYPES = new Set(['application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml', 'text/plain']);

export function isViewable(doc: JobDocument): boolean {
  return VIEWABLE_TYPES.has((doc.contenttype || '').toLowerCase().split(';')[0].trim());
}

function downloadPath(jobId: string, documentId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/documents/${encodeURIComponent(documentId)}`;
}

async function fetchDocumentBlob(jobId: string, doc: JobDocument, signal?: AbortSignal): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(absoluteUrl(downloadPath(jobId, doc.id)), {
      method: 'GET',
      signal,
    });
  } catch {
    throw new ApiError('Could not reach the server to fetch the document.', { isNetworkError: true });
  }

  if (!res.ok) {
    let message = '';
    try {
      const text = await res.text();
      const parsed = JSON.parse(text) as { Message?: string };
      message = parsed?.Message ?? '';
    } catch {
      /* empty error body (backend 404s can be empty) */
    }
    throw new ApiError(message || `The document could not be retrieved (${res.status}).`, { httpStatus: res.status });
  }

  const blob = await res.blob();
  if (blob.size === 0) {
    throw new ApiError('The document file is empty on the server.', { httpStatus: res.status });
  }
  return blob;
}

/** Downloads the real backend file using the document's own name. */
export async function downloadDocument(jobId: string, doc: JobDocument): Promise<void> {
  const blob = await fetchDocumentBlob(jobId, doc);
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = doc.documentname || 'document';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // Give the browser a moment to start the download before revoking.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
  }
}

/**
 * Opens the document in a new tab for inline viewing (PDFs/images render in
 * the browser). The tab is opened synchronously so popup blockers allow it,
 * then filled with the fetched bytes — the backend's
 * `Content-Disposition: attachment` never triggers a download here.
 * If the popup is blocked an error is surfaced instead: downloads happen
 * only through downloadDocument().
 */
export async function openDocument(jobId: string, doc: JobDocument): Promise<void> {
  const previewWindow = window.open('', '_blank');
  if (!previewWindow) {
    throw new ApiError('The preview tab was blocked — allow pop-ups for this site to view documents online.');
  }
  previewWindow.opener = null; // preview stays independent of the app window

  try {
    const blob = await fetchDocumentBlob(jobId, doc);
    const objectUrl = URL.createObjectURL(blob);
    previewWindow.location.replace(objectUrl);
    // Give the tab a moment to load before the object URL is revoked.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch (error) {
    previewWindow.close();
    throw error;
  }
}
