import { useState } from 'react';
import type { JobDocument } from '../../../types/job.types';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { useToast } from '../../common/Toast/Toast';
import { downloadDocument, isViewable, openDocument } from '../../../services/documentService';
import { fileIconKind, fileTypeLabel, formatBytes, formatDate } from '../../../utils/format';
import './DocumentItem.scss';

interface DocumentItemProps {
  jobId: string;
  document: JobDocument;
}

/** Modifier for the tinted file tiles; unknown types use the base tint. */
function tileKindClass(contentType: string): string {
  const kind = fileIconKind(contentType);
  return kind === 'file' ? '' : ` doc-item__icon--${kind}`;
}

/**
 * Document row — top line: file tile + name/meta; footer: status badge +
 * View (inline preview in a new tab) and Download actions. View never
 * downloads; Download is the only path that saves the file.
 */
export function DocumentItem({ jobId, document: doc }: DocumentItemProps) {
  const { showToast } = useToast();
  const [busy, setBusy] = useState<null | 'download' | 'view'>(null);

  const size = formatBytes(doc.filesize);
  const canView = isViewable(doc);

  const handleDownload = async () => {
    setBusy('download');
    try {
      await downloadDocument(jobId, doc);
      showToast('Download started', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Download failed.', 'error');
    } finally {
      setBusy(null);
    }
  };

  const handleView = async () => {
    setBusy('view');
    try {
      await openDocument(jobId, doc);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not open the document.', 'error');
    } finally {
      setBusy(null);
    }
  };

  return (
    <li className="doc-item">
      <div className="doc-item__row">
        <span className={`doc-item__icon${tileKindClass(doc.contenttype)}`} aria-hidden="true">
          <Icon name="file" size={16} />
          <span className="doc-item__type">{fileTypeLabel(doc.contenttype)}</span>
        </span>

        <div className="doc-item__body">
          <span className="doc-item__name" title={doc.documentname}>
            {doc.documentname || 'Unnamed document'}
          </span>
          <div className="doc-item__meta">
            {size ? <span>{size}</span> : null}
            <span title={doc.posteddatetime ?? undefined}>
              {doc.posteddatetime ? formatDate(doc.posteddatetime) : 'Upload date unknown'}
            </span>
          </div>
        </div>
      </div>

      <div className="doc-item__foot">
        <Badge tone={statusTone(doc.status)}>{doc.status || 'Unknown'}</Badge>

        <div className="doc-item__actions">
          {canView ? (
            <Button
              variant="soft"
              size="sm"
              icon="eye"
              onClick={handleView}
              loading={busy === 'view'}
              disabled={busy !== null}
            >
              View
            </Button>
          ) : null}
          <Button
            variant="primary"
            size="sm"
            icon="download"
            onClick={handleDownload}
            loading={busy === 'download'}
            disabled={busy !== null}
          >
            Download
          </Button>
        </div>
      </div>
    </li>
  );
}
