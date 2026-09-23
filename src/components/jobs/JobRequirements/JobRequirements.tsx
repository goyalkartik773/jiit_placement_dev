import { useMemo, useState } from 'react';
import type { JobDetail } from '../../../types/job.types';
import { uniqueBy } from '../../../utils/collections';
import { Button } from '../../common/Button/Button';
import { Chip } from '../../common/Chip/Chip';
import { Icon } from '../../common/Icon/Icon';
import { Panel } from '../../common/Panel/Panel';
import { CriteriaChip } from '../CriteriaChip/CriteriaChip';
import './JobRequirements.scss';

const COURSES_PREVIEW_COUNT = 24;

interface JobRequirementsProps {
  job: JobDetail;
}

/**
 * Academic qualifications section (spec): strictness-colored criteria
 * chips, eligible-degree cloud (expandable) and gender/skill chips.
 * Duplicate child rows are deduped; null arrays render as empty states.
 */
export function JobRequirements({ job }: JobRequirementsProps) {
  const [showAllCourses, setShowAllCourses] = useState(false);

  const marks = useMemo(
    () => uniqueBy((job.eligiblitymarks ?? []).filter(Boolean), (mark) => `${mark.level}|${mark.criteria}`),
    [job],
  );
  const courses = useMemo(
    () => uniqueBy((job.eligiblitycourses ?? []).filter(Boolean), (course) => course.coursename),
    [job],
  );
  const genders = useMemo(
    () => uniqueBy((job.allowedgenders ?? []).filter(Boolean), (gender) => gender.gender),
    [job],
  );
  const skills = useMemo(
    () => uniqueBy((job.requiredskills ?? []).filter(Boolean), (skill) => skill.skillname),
    [job],
  );

  const visibleCourses = showAllCourses ? courses : courses.slice(0, COURSES_PREVIEW_COUNT);

  return (
    <Panel icon="checklist" title="Academic Qualifications">
      {/* Criteria — fixed strictness color coding */}
      <div className="req-block">
        <h3 className="req-block__title">Eligibility criteria</h3>
        {marks.length === 0 ? (
          <p className="muted-note">No eligibility criteria listed.</p>
        ) : (
          <div className="req-block__chips">
            {marks.map((mark) => (
              <CriteriaChip key={`${mark.level}-${mark.criteria}`} mark={mark} />
            ))}
          </div>
        )}
      </div>

      {/* Eligible degrees */}
      <div className="req-block">
        <div className="req-block__head">
          <h3 className="req-block__title">Eligible degree disciplines</h3>
          {courses.length > 0 ? <span className="req-block__count">{courses.length} courses</span> : null}
        </div>
        {courses.length === 0 ? (
          <p className="muted-note">No eligible courses listed.</p>
        ) : (
          <>
            <div className="req-block__chips">
              {visibleCourses.map((course) => (
                <Chip key={course.id} tone="muted" title={course.coursename}>
                  {course.coursename}
                </Chip>
              ))}
            </div>
            {courses.length > COURSES_PREVIEW_COUNT ? (
              <Button
                variant="soft"
                size="sm"
                icon="chevron-down"
                className={`req-block__more${showAllCourses ? ' is-open' : ''}`}
                onClick={() => setShowAllCourses((value) => !value)}
              >
                {showAllCourses ? 'Show fewer' : `Show all ${courses.length} courses`}
              </Button>
            ) : null}
          </>
        )}
      </div>

      {/* Genders + skills (only when the tables returned rows) */}
      {genders.length > 0 || skills.length > 0 ? (
        <div className="req-block req-block--split">
          {genders.length > 0 ? (
            <div>
              <h3 className="req-block__title">Allowed genders</h3>
              <div className="req-block__chips">
                {genders.map((gender) => (
                  <Chip key={gender.id} tone="muted" title={gender.gender}>
                    <Icon name="users" size={12} /> {gender.gender}
                  </Chip>
                ))}
              </div>
            </div>
          ) : null}
          {skills.length > 0 ? (
            <div>
              <h3 className="req-block__title">Required skills</h3>
              <div className="req-block__chips">
                {skills.map((skill) => (
                  <Chip key={skill.id} tone="accent" title={skill.skillname}>
                    <Icon name="zap" size={12} /> {skill.skillname}
                  </Chip>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
