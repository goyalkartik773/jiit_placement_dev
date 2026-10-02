import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { CtcChip } from '../../common/CtcChip/CtcChip';
import { Icon } from '../../common/Icon/Icon';
import { Avatar } from '../../ui/Avatar/Avatar';
import { Card } from '../../ui/Card/Card';
import { PlacedStudentsDialog } from '../PlacedStudents/PlacedStudentsDialog';
import { formatDate, formatDateTime } from '../../../utils/format';
import type { CompanyJob, CompanyRow } from '../../../types/dashboard.types';
import './CompanyCard.scss';

interface CompanyCardProps {
  row: CompanyRow;
}

/**
 * One company in the company-wise table: identity + placed count in the
 * header, roles / job listings behind an expandable disclosure, and the
 * per-job student roster opened as a MASTER-DETAIL DIALOG rather than a
 * table nested inside this card (four levels deep, with no room left for
 * its columns).
 */
export function CompanyCard({ row }: CompanyCardProps) {
  const [open, setOpen] = useState(false);
  const [roster, setRoster] = useState<{ job: CompanyJob; trigger: HTMLElement | null } | null>(null);
  const panelId = useId();

  const jobs = row.jobs ?? [];
  const roles = row.roles ?? [];
  const branches = row.branches ?? [];
  const campuses = row.campuses ?? [];
  const jobLabel = `${row.jobcount} job${row.jobcount === 1 ? '' : 's'}`;

  /** `trigger` is the button itself, so closing the dialog can refocus it. */
  function openRoster(job: CompanyJob, trigger: HTMLElement | null): void {
    setRoster({ job, trigger });
  }

  return (
    <Card as="article" className="company-card">
      <h3 className="company-card__heading">
        <button
          type="button"
          className="company-card__head"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          <Avatar name={row.company} size={44} radius={12} />

          <span className="company-card__identity">
            <span className="company-card__name">{row.company}</span>
            <span className="company-card__meta">
              <span className="company-card__jobcount" title={`${row.jobcount} job(s), ${row.activejobs} active`}>
                {jobLabel}
              </span>
              <span className="company-card__meta-dot" aria-hidden="true">
                ·
              </span>
              {row.lastplacedat ? (
                <span className="company-card__last">Last offer {formatDate(row.lastplacedat)}</span>
              ) : (
                <span className="company-card__last">No offers recorded</span>
              )}
            </span>
          </span>

          <span className="company-card__placed">
            <span className="company-card__placed-value">{row.placedstudents.toLocaleString()}</span>
            <span className="company-card__placed-label">placed</span>
          </span>

          <span className="company-card__chevron" aria-hidden="true">
            <Icon name="chevron-down" size={16} />
          </span>
        </button>
      </h3>

      <div className="company-card__body" id={panelId} hidden={!open}>
        {roles.length > 0 ? (
          <div className="company-card__section">
            <p className="company-card__section-title">Offered roles ({roles.length})</p>
            <ul className="company-card__roles">
              {roles.map((role) => (
                <li className="company-card__role" key={role.role}>
                  <span className="company-card__role-name" title={role.role}>
                    {role.role}
                  </span>
                  <span className="company-card__role-count">
                    {role.students} <span className="company-card__role-count-suffix">placed</span>
                  </span>
                  {typeof role.ctcmax === 'number' && role.ctcmax > 0 ? (
                    <CtcChip package={role.ctcmax} size="sm" />
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {branches.length > 0 || campuses.length > 0 ? (
          <div className="company-card__section">
            <p className="company-card__section-title">
              Branch &amp; campus ({row.placedstudents} placed)
            </p>
            <div className="company-card__breakdowns">
              {campuses.length > 0 ? (
                <div className="company-card__breakdown">
                  <p className="company-card__breakdown-label">Campus</p>
                  <ul className="company-card__roles">
                    {campuses.map((entry) => (
                      <li className="company-card__role" key={`campus-${entry.campus ?? '?'}`}>
                        <span className="company-card__role-name">{entry.campus ?? 'Unknown'}</span>
                        <span className="company-card__role-count">
                          {entry.students}{' '}
                          <span className="company-card__role-count-suffix">placed</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {branches.length > 0 ? (
                <div className="company-card__breakdown">
                  <p className="company-card__breakdown-label">Branch</p>
                  <ul className="company-card__roles">
                    {branches.map((entry) => (
                      <li className="company-card__role" key={`branch-${entry.branch ?? '?'}`}>
                        <span className="company-card__role-name">{entry.branch ?? 'Unknown'}</span>
                        <span className="company-card__role-count">
                          {entry.students}{' '}
                          <span className="company-card__role-count-suffix">placed</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="company-card__section">
          <p className="company-card__section-title">
            Job listings ({jobs.length}) {row.activejobs !== row.jobcount ? ` - ${row.activejobs} active` : ''}
          </p>

          {jobs.length === 0 ? (
            <p className="company-card__note">No job listings are attached to this company.</p>
          ) : (
            <ul className="company-card__jobs">
              {jobs.map((job) => (
                <li className="company-card__job" key={job.id}>
                  <Link className="company-card__job-title" to={`/jobs/${job.id}`}>
                    {job.jobprofile}
                  </Link>

                  <span className="company-card__job-facts">
                    <CtcChip package={job.package} packageinfo={job.packageinfo} />
                    <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                    {job.deadline ? (
                      <span className="company-card__deadline">
                        <Icon name="calendar" size={13} />
                        Closes {formatDate(job.deadline)}
                      </span>
                    ) : null}
                  </span>

                  <Button
                    variant="soft"
                    size="sm"
                    icon="users"
                    onClick={(event) => openRoster(job, event.currentTarget)}
                    title="Open the full roster of students placed through this job"
                  >
                    Placed students
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {row.firstplacedat ? (
          <p className="company-card__window">
            Offers recorded between {formatDateTime(row.firstplacedat)} and {formatDateTime(row.lastplacedat)}.
          </p>
        ) : null}
      </div>

      {/* Portalled to <body>: a dialog must escape this card's stacking
          context, and closing it returns focus to `roster.trigger`. */}
      {roster ? (
        <PlacedStudentsDialog
          job={roster.job}
          trigger={roster.trigger}
          onClose={() => setRoster(null)}
        />
      ) : null}
    </Card>
  );
}
