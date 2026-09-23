import type { JobDocument } from '../../../types/job.types';
import { Panel } from '../../common/Panel/Panel';
import { DocumentItem } from '../DocumentItem/DocumentItem';
import './JobDocuments.scss';

interface JobDocumentsProps {
  jobId: string;
  documents: JobDocument[] | null;
}

/**
 * Drive documents sidebar card (spec): count badge in the header plus one
 * file row per document with working view/download actions.
 */
export function JobDocuments({ jobId, documents }: JobDocumentsProps) {
  const items = Array.isArray(documents) ? documents.filter(Boolean) : [];

  return (
    <Panel icon="folder" title="Drive Documents" size="sm" count={items.length} id="drive-documents">
      {items.length === 0 ? (
        <p className="muted-note">No documents are attached to this job.</p>
      ) : (
        <ul className="doc-list">
          {items.map((doc) => (
            <DocumentItem key={doc.id} jobId={jobId} document={doc} />
          ))}
        </ul>
      )}
    </Panel>
  );
}
