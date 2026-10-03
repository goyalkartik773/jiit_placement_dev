import { useMemo, useState } from 'react';
import type { JobDetail } from '../../../types/job.types';
import { uniqueBy } from '../../../utils/collections';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Panel } from '../../common/Panel/Panel';
import './JobSelectionProcess.scss';

const FLOW_PREVIEW_COUNT = 8;

interface JobSelectionProcessProps {
  job: JobDetail;
}

/**
 * Selection process pipeline (spec): vertical stepper — numbered markers on
 * a gradient rail, one card per hiring-flow stage with its real status pill.
 * The API can return duplicate stage rows; they are deduped by
 * sequence + stage name before counting or rendering.
 */
export function JobSelectionProcess({ job }: JobSelectionProcessProps) {
  const [showAllStages, setShowAllStages] = useState(false);

  const stages = useMemo(() => {
    if (!Array.isArray(job.hiringflow)) return [];
    const sorted = job.hiringflow
      .filter(Boolean)
      .slice()
      .sort((a, b) => Number.parseInt(a.sequence, 10) - Number.parseInt(b.sequence, 10) || 0);
    return uniqueBy(sorted, (stage) => `${stage.sequence}|${stage.stagename}`);
  }, [job]);

  const visibleStages = showAllStages ? stages : stages.slice(0, FLOW_PREVIEW_COUNT);

  return (
    <Panel
      icon="layers"
      title="Selection Process Pipeline"
      meta={stages.length > 0 ? `${stages.length} Stage${stages.length === 1 ? '' : 's'}` : undefined}
    >
      {stages.length === 0 ? (
        <p className="muted-note">No hiring stages listed for this job.</p>
      ) : (
        <>
          <ol className="pipeline">
            {visibleStages.map((stage) => {
              const tone = statusTone(stage.status);
              // Zero-padded so the rail reads 01 → 02 → 03, which is what
              // makes a vertical list look like a sequence rather than a set
              // of unrelated bullets. Non-numeric sequences fall back to a
              // dash instead of rendering "00".
              const seq = Number.parseInt(stage.sequence, 10);
              const stepNumber = Number.isFinite(seq) && seq > 0 ? String(seq).padStart(2, '0') : '—';
              return (
                <li className="pipeline__step" key={stage.id}>
                  <span className={`pipeline__marker pipeline__marker--${tone}`} aria-hidden="true">
                    {stepNumber}
                  </span>
                  <span className="pipeline__body">
                    <span className="pipeline__name" title={stage.stagename}>
                      {stage.stagename}
                    </span>
                    <Badge tone={tone}>{stage.status || 'Unknown'}</Badge>
                  </span>
                </li>
              );
            })}
          </ol>
          {stages.length > FLOW_PREVIEW_COUNT ? (
            <Button
              variant="soft"
              size="sm"
              icon="chevron-down"
              className={`pipeline__more${showAllStages ? ' is-open' : ''}`}
              onClick={() => setShowAllStages((value) => !value)}
            >
              {showAllStages ? 'Show fewer' : `Show all ${stages.length} stages`}
            </Button>
          ) : null}
        </>
      )}
    </Panel>
  );
}
