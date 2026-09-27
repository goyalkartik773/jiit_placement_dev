import { Button } from '../../common/Button/Button';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Icon } from '../../common/Icon/Icon';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import type { AdminOverview } from '../../../types/admin.types';
import './InventoryStrip.scss';

interface InventoryStripProps {
  /** Raw `data` of GET /api/admin/overview — every number below comes from here. */
  overview: AdminOverview | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

interface InventoryTile {
  key: string;
  /** Category accent — the tile's 2px solid top border. */
  accent: 'blue' | 'indigo' | 'green' | 'purple' | 'teal' | 'pink';
  label: string;
  value: string;
  /** Single faint footer line (every part below comes from the API). */
  foot?: string | null;
}

/** Skeleton tile keys — the loading grid keeps the final tile count and accents. */
const TILE_ACCENT: Record<string, InventoryTile['accent']> = {
  jobs: 'blue',
  mailbox: 'indigo',
  emails: 'green',
  placements: 'purple',
  integrity: 'teal',
  shortlist: 'pink',
};

/** Server number → tabular string; unknown renders an em dash, never a guess. */
function num(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '—';
}

/** Sum of the known values only (null when none of them was reported). */
function sumKnown(...values: (number | null | undefined)[]): number | null {
  const known = values.filter((value): value is number => typeof value === 'number');
  return known.length > 0 ? known.reduce((total, value) => total + value, 0) : null;
}

/** One footer line: known parts only, joined with a middot. */
function footLine(...parts: (string | null | undefined)[]): string | null {
  const known = parts.filter((part): part is string => Boolean(part));
  return known.length > 0 ? known.join(' · ') : null;
}

/** Reads `overview.data` into the fixed set of tiles (missing data → em dash). */
function buildTiles(overview: AdminOverview): InventoryTile[] {
  const counts = overview.counts;
  const mailbox = overview.mailbox;
  const classification = overview.classification;
  const matching = overview.matching;
  const integrity = overview.integrity;

  const orphans = sumKnown(integrity?.orphanMappings, integrity?.orphanOffers);
  const duplicates = sumKnown(integrity?.duplicateMappings);
  const blanks = sumKnown(integrity?.blankRolls);
  const flagged = sumKnown(orphans, duplicates, blanks);
  const complete = orphans !== null && duplicates !== null && blanks !== null;
  const verdict = !complete ? 'unknown' : flagged === 0 ? 'clean' : 'flagged';

  const mailboxParts: string[] = [];
  if (typeof mailbox?.finishedRate === 'number') mailboxParts.push(`${mailbox.finishedRate}% finished`);
  if (typeof mailbox?.reviewRate === 'number') mailboxParts.push(`${mailbox.reviewRate}% awaiting review`);

  const placementParts: string[] = [];
  if (typeof matching?.studentsMapped === 'number') placementParts.push(`${num(matching.studentsMapped)} students mapped`);
  if (typeof matching?.companiesMatched === 'number') placementParts.push(`${num(matching.companiesMatched)} matched`);
  if (typeof matching?.companiesSkipped === 'number') placementParts.push(`${num(matching.companiesSkipped)} skipped`);

  return [
    {
      key: 'jobs',
      accent: 'blue',
      label: 'Jobs',
      value: num(counts?.jobs),
      foot: typeof counts?.jobsActive === 'number' ? `${num(counts.jobsActive)} active` : null,
    },
    {
      key: 'mailbox',
      accent: 'indigo',
      label: 'Mailbox',
      value: num(mailbox?.total),
      foot: footLine(...mailboxParts),
    },
    {
      key: 'emails',
      accent: 'green',
      label: 'Parsed e-mails',
      value: num(counts?.emails),
      foot: typeof classification?.coverage === 'number' ? `${classification.coverage}% classified` : null,
    },
    {
      key: 'placements',
      accent: 'purple',
      label: 'Placements',
      value: num(counts?.mappings),
      foot: footLine(...placementParts),
    },
    {
      key: 'integrity',
      accent: 'teal',
      label: 'Integrity',
      value: flagged === null ? '—' : num(flagged),
      foot: footLine(
        typeof orphans === 'number' ? `${num(orphans)} orphans` : null,
        typeof duplicates === 'number' ? `${num(duplicates)} duplicates` : null,
        typeof blanks === 'number' ? `${num(blanks)} blank rolls` : null,
        verdict,
      ),
    },
    {
      key: 'shortlist',
      accent: 'pink',
      label: 'Shortlist',
      value: num(counts?.shortlistStudents),
      foot: typeof counts?.shortlistEvents === 'number' ? `${num(counts.shortlistEvents)} events` : null,
    },
  ];
}

/**
 * Accuracy / inventory strip: one tile per cluster of `GET /api/admin/overview`
 * numbers (counts, mailbox rates, classification coverage, matching, integrity,
 * shortlist). Every value is a server number — only formatting happens here.
 */
export function InventoryStrip({ overview, loading, error, onRetry }: InventoryStripProps) {
  if (!overview) {
    if (error) {
      return (
        <section className="inventory" aria-label="System inventory">
          <ErrorState title="Inventory unavailable" message={error} onRetry={onRetry} />
        </section>
      );
    }

    return (
      <section className="inventory" aria-label="System inventory">
        <div className="inventory__grid" role="status" aria-label="Loading inventory">
          {Object.entries(TILE_ACCENT).map(([key, accent]) => (
            <article className={`stat-tile stat-tile--${accent}`} key={key} aria-hidden="true">
              <span className="stat-tile__label">
                <Skeleton width="sm" height="xs" />
              </span>
              <span className="stat-tile__value">
                <Skeleton width="md" height="xl" />
              </span>
              <span className="stat-tile__foot">
                <Skeleton width="xl" height="md" shape="pill" />
              </span>
            </article>
          ))}
        </div>
        {loading ? <span className="sr-only">Loading inventory…</span> : null}
      </section>
    );
  }

  const tiles = buildTiles(overview);

  return (
    <section className="inventory" aria-label="System inventory">
      {error ? (
        <p className="inventory__error" role="alert">
          <Icon name="alert-circle" size={15} />
          <span className="inventory__error-text">{error}</span>
          <Button variant="soft" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </p>
      ) : null}

      <div className="inventory__grid">
        {tiles.map((tile) => (
          <article className={`stat-tile stat-tile--${tile.accent}`} key={tile.key}>
            <span className="stat-tile__label">{tile.label}</span>
            <span className="stat-tile__value">{tile.value}</span>
            <span className="stat-tile__foot">{tile.foot ?? ''}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
