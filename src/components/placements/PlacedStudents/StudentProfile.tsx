import type { ReactNode } from 'react';
import { Icon, type IconName } from '../../common/Icon/Icon';
import { formatDate, formatDateTime, formatINR, initials } from '../../../utils/format';
import { BranchBadge, CampusBadge, RoleBadge } from './StudentBadges';
import { branchOf, campusOf, ctcLabel, shortRoleLabel } from './badgePalette';
import type { PlacedStudent } from '../../../types/dashboard.types';

interface StudentProfileProps {
  /** The row the master list has selected. `null` = nothing to show yet. */
  student: PlacedStudent | null;
  /** Narrow-viewport "Back to the list" affordance. */
  onBack?: () => void;
}

/** One `dt`/`dd` pair. `value` is already rendered — never a raw null. */
function Fact({
  label,
  value,
  note,
  identifier,
}: {
  label: string;
  value: ReactNode;
  /** Provenance line under the value (which source answered this). */
  note?: string | null;
  /** Set for roll numbers / message ids so they align as data, not prose. */
  identifier?: boolean;
}) {
  // Nothing to say: the column is genuinely absent for this student. Omitting
  // the row beats printing an empty dash a dozen times over.
  if (value === null || value === undefined || value === '' || value === '—') return null;

  return (
    <div className="placed-students__fact">
      <dt>{label}</dt>
      <dd className={identifier ? 'placed-students__fact-value is-identifier' : 'placed-students__fact-value'}>
        {value}
        {note ? <span className="placed-students__fact-note">{note}</span> : null}
      </dd>
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: IconName;
  children: ReactNode;
}) {
  return (
    <section className="placed-students__psection" aria-label={title}>
      <h5 className="placed-students__psection-title">
        <Icon name={icon} size={14} />
        {title}
      </h5>
      <dl className="placed-students__facts">{children}</dl>
    </section>
  );
}

/** `null` when the string is blank — callers print nothing instead of "". */
function text(value: string | null | undefined): string | null {
  const trimmed = (value ?? '').trim();
  return trimmed || null;
}

/**
 * `full_time` -> `Full time`. Display only: the token itself is the stored
 * value and is never rewritten, only the way it is printed (the code-style
 * underscore reads as a bug in an otherwise typeset record).
 */
function humanize(value: string | null): string | null {
  if (!value) return null;
  const words = value.replace(/[_-]+/g, ' ').trim();
  if (!words) return null;
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
}

/**
 * The second reading of a derived field — shown ONLY when it disagrees with
 * the value already on screen. When the offer email and the roll rule say the
 * same thing, repeating it would be noise; when they differ, hiding one of
 * them would be quietly picking a winner.
 */
function otherSource(display: string | null, source: string | null): string | null {
  if (!source || !display) return null;
  if (source.localeCompare(display, undefined, { sensitivity: 'base' }) === 0) return null;
  return source;
}

/** How a single-value field was resolved, when that is not obvious. */
function sourceNote(solved: string | null, fromRoll: string | null): string | null {
  if (!solved) return null;
  if (fromRoll && solved === fromRoll) return 'resolved from the roll number';
  return 'from the offer email';
}

/**
 * The reading pane's content: EVERY field `job_placed_students` hands the
 * client, grouped by what a placement office actually asks for.
 *
 * The old drawer showed four facts and three chips — the rest of the row
 * (email, program, both branch readings, CTC basis, stipend, employment type,
 * the offer subject...) was fetched and then thrown away. Nothing here is
 * derived: each value is printed as the feed returned it, with a provenance
 * note where two sources could have answered.
 */
export function StudentProfile({ student, onBack }: StudentProfileProps) {
  if (!student) {
    return (
      <div className="placed-students__profile is-empty">
        <Icon name="users" size={20} />
        <p>Select a student from the list to see their full record.</p>
      </div>
    );
  }

  const name = text(student.studentname) ?? 'Unnamed student';
  const roll = text(student.rollno);
  const program = text(student.program);
  const batch = student.batchyear ?? null;

  const branchEmail = text(student.branch);
  const branchRoll = text(student.branchfromroll);
  const branch = branchOf(student);

  const campusEmail = text(student.campusextracted);
  const campusRoll = text(student.campusfromroll);
  const campus = campusOf(student);

  const roleShort = shortRoleLabel(student);
  const roleFull = text(student.rolelevel) ?? text(student.role);

  const ctcTotal = student.ctctotal ?? null;
  const stipend = student.stipend ?? null;
  const ctcHeadline = ctcLabel(student.ctcraw, student.ctctotal);

  const offerSubject = text(student.offersubject);
  const offerEmailId = text(student.offeremailid);
  const offerUrl = offerEmailId && /^https?:\/\//i.test(offerEmailId) ? offerEmailId : null;

  return (
    <div className="placed-students__profile">
      {onBack ? (
        <button type="button" className="placed-students__profile-back" onClick={onBack}>
          <Icon name="arrow-left" size={15} />
          Back to list
        </button>
      ) : null}

      {/* ----- identity ----- */}
      <header className="placed-students__profile-head">
        <span className="placed-students__profile-avatar" aria-hidden="true">
          {initials(name)}
        </span>
        <div className="placed-students__profile-ident">
          <p className="placed-students__profile-eyebrow">Student record</p>
          <h4 className="placed-students__profile-name">{name}</h4>
          <p className="placed-students__profile-sub">
            {roll ?? 'Roll number not on file'}
            {program ? ` · ${program}` : ''}
            {batch ? ` · Batch ${batch}` : ''}
          </p>
        </div>
      </header>

      {/* Grouped facts. Sections are rendered in the order a placement office
          reads them; every value below is straight from the feed. */}
      <ul className="placed-students__profile-chips">
        <li>{branch ? <BranchBadge branch={branch} /> : null}</li>
        <li>{campus ? <CampusBadge campus={campus} /> : null}</li>
        <li>{roleShort ? <RoleBadge role={roleShort} /> : null}</li>
      </ul>

      {/* ----- the three figures people open this record for ----- */}
      <div className="placed-students__profile-figures">
        <div className="placed-students__figure placed-students__figure--money">
          <p className="placed-students__figure-label">CTC</p>
          <p className="placed-students__figure-value">{ctcHeadline}</p>
        </div>
        <div className="placed-students__figure">
          <p className="placed-students__figure-label">Offer date</p>
          <p className="placed-students__figure-value">
            {formatDate(student.offerreceivedat ?? student.placedat)}
          </p>
        </div>
        <div className="placed-students__figure">
          <p className="placed-students__figure-label">Employment</p>
          <p className="placed-students__figure-value">
            {humanize(text(student.employmenttype)) ?? '—'}
          </p>
        </div>
      </div>

      <Section title="Offer" icon="briefcase">
        <Fact label="Company" value={text(student.companyname)} />
        <Fact label="Role" value={roleFull} />
        <Fact label="Employment type" value={humanize(text(student.employmenttype))} />
        <Fact label="CTC as written" value={text(student.ctcraw)} />
        <Fact
          label="Annual total"
          value={formatINR(ctcTotal)}
          note={formatINR(ctcTotal) ? 'CTC reported by the offer mail' : null}
        />
        <Fact label="CTC basis" value={text(student.ctcbasis)} />
        <Fact label="Stipend" value={formatINR(stipend)} />
        <Fact label="Offer received" value={formatDateTime(student.offerreceivedat)} />
        <Fact label="Placed on" value={formatDate(student.placedat)} />
      </Section>

      <Section title="Academics" icon="book">
        <Fact label="Program" value={program} />
        <Fact label="Branch" value={branch} note={sourceNote(branch, branchRoll)} />
        <Fact label="Branch (roll rule)" value={otherSource(branch, branchRoll)} />
        <Fact label="Branch (offer email)" value={otherSource(branch, branchEmail)} />
        <Fact
          label="Campus"
          value={campus}
          note={sourceNote(campus, campusRoll) ?? (campusEmail && campus ? 'from the offer email' : null)}
        />
        <Fact label="Campus (roll rule)" value={otherSource(campus, campusRoll)} />
        <Fact label="Campus (offer email)" value={otherSource(campus, campusEmail)} />
        <Fact label="Batch year" value={batch ? String(batch) : null} />
      </Section>

      <Section title="Contact" icon="inbox">
        <Fact label="Name" value={text(student.studentname)} />
        <Fact label="Roll number" value={roll} identifier />
        <Fact label="Email" value={text(student.email)} identifier />
      </Section>

      <Section title="Source record" icon="file">
        <Fact label="Offer subject" value={offerSubject} />
        <Fact
          label="Offer email id"
          value={
            offerUrl ? (
              <a href={offerUrl} target="_blank" rel="noopener noreferrer" className="placed-students__link">
                {offerUrl}
                <Icon name="external-link" size={13} />
              </a>
            ) : (
              offerEmailId
            )
          }
          identifier={!offerUrl}
        />
        <Fact label="Record id" value={student.id} identifier />
      </Section>
    </div>
  );
}
