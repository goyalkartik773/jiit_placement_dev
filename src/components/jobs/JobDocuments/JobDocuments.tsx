import type { JobDocument } from '../../../types/job.types';
import { StateShell } from '../../common/StateShell/StateShell';
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
 *
 * With no documents it renders a real empty state rather than a bare muted
 * line — the folder icon the panel already heads itself with, a title, and a
 * sentence saying what would be here and what could be done with it. It is
 * scoped (`.doc-empty`) because the shared shell is sized for a page-level
 * void: 48px of padding, a 58px icon and a dashed 20px-radius border all
 * fight the panel around it at 330px wide.
 */
export function JobDocuments({ jobId, documents }: JobDocumentsProps) {
  const items = Array.isArray(documents) ? documents.filter(Boolean) : [];

  return (
    <Panel icon="folder" title="Drive Documents" size="sm" count={items.length} id="drive-documents">
      {items.length === 0 ? (
        <StateShell
          icon="folder"
          className="doc-empty"
          title="No drive documents"
          description="Nothing has been attached to this job yet — files will appear here with view and download actions."
        />
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
