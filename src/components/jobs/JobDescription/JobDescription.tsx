import { useEffect, useRef } from 'react';
import type { JobDetail } from '../../../types/job.types';
import { hardenHtmlLinks, highlightMoneyTerms, stripHtml } from '../../../utils/html';
import { Panel } from '../../common/Panel/Panel';
import './JobDescription.scss';

interface JobDescriptionProps {
  job: JobDetail;
}

/**
 * Job description section — renders the backend's HTML (jobdescription,
 * falling back to content) inside a scoped prose container. After render
 * links are hardened and money terms (stipend/package/…) highlighted.
 */
export function JobDescription({ job }: JobDescriptionProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const html = job.jobdescription || job.content;
  const hasDescription = stripHtml(html).length > 0;

  useEffect(() => {
    hardenHtmlLinks(containerRef.current);
    highlightMoneyTerms(containerRef.current);
  }, [html]);

  return (
    <Panel icon="book" title="Job Description">
      {hasDescription ? (
        <div ref={containerRef} className="job-description__prose" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <p className="muted-note">No description has been provided for this job.</p>
      )}
    </Panel>
  );
}
