"""Invariant teaching-demand metrics for timetable reports.

Audit note:
- One scheduled Assignment represents one scheduled course-week occurrence.
- One unscheduled Assignment may represent one failed week, a failed recurring
  pattern, or a candidate-limit placeholder for several missing weeks.
- Common modules are first consolidated into one scheduling requirement, so
  demand is counted once for the shared combined-cohort requirement.
- Raw Assignment totals can change when room availability changes because a
  previously unscheduled multi-week placeholder may become several scheduled
  week-level Assignment objects. Required teaching occurrences therefore come
  from consolidated course requirements, not from schedule row counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from data.models import Assignment, Course
from generator.scheduler import prepare_courses_for_scheduling, schedulable_weeks

RequirementKey: TypeAlias = tuple[str, str, str, str, tuple[str, ...], tuple[int, ...], int]


@dataclass(slots=True)
class RequirementDemand:
    """Demand and scheduled coverage for one consolidated requirement."""

    key: RequirementKey
    course: Course
    required_week_count: int
    scheduled_week_count: int
    unscheduled_week_count: int


@dataclass(slots=True)
class DemandMetrics:
    """Invariant demand metrics for a schedule run."""

    input_course_records: int
    consolidated_course_requirements: int
    required_teaching_occurrences: int
    scheduled_teaching_occurrences: int
    unscheduled_teaching_occurrences: int
    courses_fully_scheduled: int
    courses_partially_scheduled: int
    courses_fully_unscheduled: int

    @property
    def coverage_rate_percent(self) -> float:
        """Return scheduled occurrence coverage as a percentage."""
        if self.required_teaching_occurrences == 0:
            return 0.0
        return self.scheduled_teaching_occurrences / self.required_teaching_occurrences * 100

    @property
    def is_consistent(self) -> bool:
        """Return True when occurrence demand balances exactly."""
        return self.required_teaching_occurrences == (
            self.scheduled_teaching_occurrences + self.unscheduled_teaching_occurrences
        )


def requirement_key(course: Course) -> RequirementKey:
    """Return a stable key for matching output assignments to requirements."""
    return (
        course.module_code.strip().upper(),
        course.activity.strip().lower(),
        course.prog_yr.strip(),
        course.source_file.strip(),
        tuple(course.group_ids),
        tuple(schedulable_weeks(course.teaching_weeks)),
        course.duration_hrs,
    )


def consolidated_requirements(courses: list[Course]) -> list[Course]:
    """Return independent scheduling requirements after common-module merging."""
    return prepare_courses_for_scheduling(courses)


def scheduled_occurrences_by_key(assignments: list[Assignment]) -> dict[RequirementKey, int]:
    """Count scheduled week occurrences by requirement key."""
    counts: dict[RequirementKey, int] = {}
    for assignment in assignments:
        if assignment.room is None or assignment.timeslot is None:
            continue
        key = requirement_key(assignment.course)
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_requirement_demands(courses: list[Course], assignments: list[Assignment]) -> list[RequirementDemand]:
    """Map schedule results back to consolidated course requirements."""
    available_scheduled = scheduled_occurrences_by_key(assignments)
    rows: list[RequirementDemand] = []
    for course in consolidated_requirements(courses):
        key = requirement_key(course)
        required = len(schedulable_weeks(course.teaching_weeks))
        scheduled = min(required, available_scheduled.get(key, 0))
        available_scheduled[key] = max(available_scheduled.get(key, 0) - scheduled, 0)
        rows.append(
            RequirementDemand(
                key=key,
                course=course,
                required_week_count=required,
                scheduled_week_count=scheduled,
                unscheduled_week_count=required - scheduled,
            )
        )
    return rows


def requirement_demand_lookup(courses: list[Course], assignments: list[Assignment]) -> dict[RequirementKey, RequirementDemand]:
    """Return aggregate demand counts keyed by consolidated requirement."""
    lookup: dict[RequirementKey, RequirementDemand] = {}
    for row in build_requirement_demands(courses, assignments):
        existing = lookup.get(row.key)
        if existing is None:
            lookup[row.key] = row
            continue
        existing.required_week_count += row.required_week_count
        existing.scheduled_week_count += row.scheduled_week_count
        existing.unscheduled_week_count += row.unscheduled_week_count
    return lookup


def build_demand_metrics(
    courses: list[Course],
    assignments: list[Assignment],
    input_course_records: int | None = None,
) -> DemandMetrics:
    """Build stable teaching-occurrence demand metrics for a schedule."""
    rows = build_requirement_demands(courses, assignments)
    required = sum(row.required_week_count for row in rows)
    scheduled = sum(row.scheduled_week_count for row in rows)
    return DemandMetrics(
        input_course_records=input_course_records if input_course_records is not None else len(courses),
        consolidated_course_requirements=len(rows),
        required_teaching_occurrences=required,
        scheduled_teaching_occurrences=scheduled,
        unscheduled_teaching_occurrences=required - scheduled,
        courses_fully_scheduled=sum(1 for row in rows if row.required_week_count > 0 and row.unscheduled_week_count == 0),
        courses_partially_scheduled=sum(
            1 for row in rows if 0 < row.scheduled_week_count < row.required_week_count
        ),
        courses_fully_unscheduled=sum(
            1 for row in rows if row.required_week_count > 0 and row.scheduled_week_count == 0
        ),
    )
