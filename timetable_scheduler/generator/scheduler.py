"""Greedy timetable generator that prioritises hard-constraint feasibility."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from typing import Callable

from config import BLOCKED_WEEKS, LUNCH_BLOCKS, MIN_ROOM_UTILISATION, VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, course_groups, is_online_course, occupied_start_times, room_is_exclusive

MAX_CANDIDATE_PATTERN_LIMIT_REASON = "Stopped after max candidate pattern limit for Engineering demo run"


@dataclass(slots=True)
class ScheduleIndex:
    """Fast lookup tables for occupied room, tutor, and group slots."""

    room_slots: set[tuple[int, str, str, str]] = field(default_factory=set)
    staff_slots: set[tuple[int, str, str, str]] = field(default_factory=set)
    group_slots: set[tuple[int, str, str, str]] = field(default_factory=set)
    group_lunch_blocks: dict[tuple[int, str, str], set[str]] = field(default_factory=lambda: defaultdict(set))

    def add(self, assignment: Assignment) -> None:
        """Index one assignment's occupied slots."""
        if assignment.timeslot is None or assignment.room is None:
            return

        week = assignment.timeslot.week
        day = assignment.timeslot.day
        room_id = assignment.room.room_id
        occupied = occupied_start_times(assignment)

        for block in occupied:
            if room_is_exclusive(assignment.room):
                self.room_slots.add((week, day, block, room_id))
            for staff_id in assignment.course.staff_ids:
                if staff_id:
                    self.staff_slots.add((week, day, block, staff_id))
            for group in course_groups(assignment.course):
                self.group_slots.add((week, day, block, group))

        for group in course_groups(assignment.course):
            self.group_lunch_blocks.setdefault((week, day, group), set()).update(
                block for block in occupied if block in LUNCH_BLOCKS
            )

    def copy(self) -> "ScheduleIndex":
        """Return a shallow copy of the index sets."""
        return ScheduleIndex(
            room_slots=set(self.room_slots),
            staff_slots=set(self.staff_slots),
            group_slots=set(self.group_slots),
            group_lunch_blocks={key: set(value) for key, value in self.group_lunch_blocks.items()},
        )


def build_schedule_index(assignments: list[Assignment]) -> ScheduleIndex:
    """Build fast lookup tables from a schedule."""
    index = ScheduleIndex()
    for assignment in assignments:
        index.add(assignment)
    return index


def schedulable_weeks(weeks: list[int]) -> list[int]:
    """Return teaching weeks that are not blocked by the academic calendar."""
    return [week for week in weeks if week not in BLOCKED_WEEKS]


def generate_timeslots(weeks: list[int]) -> list[TimeSlot]:
    """Generate all candidate timeslots for unblocked teaching weeks."""
    return [
        TimeSlot(day=day, start_time=start, week=week)
        for week, day, start in product(schedulable_weeks(weeks), VALID_DAYS, VALID_START_TIMES)
    ]


def _activity_key(course: Course) -> str:
    """Return lower-case activity text."""
    return course.activity.strip().lower()


def _infer_week_pattern(weeks: list[int]) -> str:
    """Infer ALL, ODD, EVEN, or CUSTOM from teaching weeks."""
    if not weeks:
        return "ALL"
    if all(week % 2 == 1 for week in weeks):
        return "ODD"
    if all(week % 2 == 0 for week in weeks):
        return "EVEN"
    return "CUSTOM"


def _unique_ordered(values: list[str]) -> list[str]:
    """Return unique non-empty values while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _room_preference_score(course: Course, room: Room) -> tuple[int, int, int, int]:
    """Rank room preference by utilisation and tightness."""
    capacity_gap = max(room.capacity - course.class_size, 0)
    utilisation_band = 0 if room.capacity and course.class_size / room.capacity >= MIN_ROOM_UTILISATION else 1
    utilisation_gap = room.capacity - course.class_size
    suitability = _room_suitability_score(course, room)
    return (utilisation_band, capacity_gap, utilisation_gap, suitability[0] + suitability[1])


def _room_suitability_score(course: Course, room: Room) -> tuple[int, int]:
    """Rank room suitability and tightness for a course."""
    activity = _activity_key(course)
    resource = room.resource_type.lower()
    capacity_gap = max(room.capacity - course.class_size, 0)

    if is_online_course(course):
        return (0 if room.room_type == "virtual" else 99, capacity_gap)
    if room.room_type == "virtual":
        return (99, capacity_gap)

    if "lab" in activity or "laboratory" in activity or "practical" in activity:
        return (0 if "lab" in resource or "laboratory" in resource else 2, capacity_gap)
    if "lecture" in activity or "lectorial" in activity:
        return (0 if "lectorial" in resource or "lecture" in resource else 1, capacity_gap)
    if "tutorial" in activity or "seminar" in activity:
        return (0 if "seminar" in resource or "classroom" in resource else 1, capacity_gap)
    return (1, capacity_gap)


def get_candidate_rooms(course: Course, rooms: list[Room]) -> list[Room]:
    """Return rooms compatible with delivery mode and capacity."""
    if is_online_course(course):
        candidates = [room for room in rooms if room.room_type == "virtual" and room.capacity >= course.class_size]
        return sorted(candidates, key=lambda room: _room_preference_score(course, room))

    candidates = [room for room in rooms if room.room_type == "physical" and room.capacity >= course.class_size]
    return sorted(candidates, key=lambda room: _room_preference_score(course, room))


def _course_difficulty(course: Course, rooms: list[Room]) -> tuple[int, int, int, int]:
    """Sort hardest courses first for better greedy feasibility."""
    room_count = len(get_candidate_rooms(course, rooms))
    week_count = len(schedulable_weeks(course.teaching_weeks))
    return (0 if course.is_common_module else 1, -course.class_size, -course.duration_hrs, room_count, -week_count)


def _common_group_key(course: Course) -> tuple[str, str]:
    """Return the grouping key for common-module activities."""
    return (course.module_code.strip().upper(), course.activity.strip().lower())


def build_common_course(courses: list[Course]) -> Course:
    """Combine common-module cohorts into one large-room scheduling request."""
    base = courses[0]
    groups = _unique_ordered([course.prog_yr for course in courses] + [g for course in courses for g in course.group_ids])
    staff_ids = _unique_ordered([staff for course in courses for staff in course.staff_ids])
    staff_names = _unique_ordered([staff for course in courses for staff in course.staff_names])
    weeks = sorted({week for course in courses for week in course.teaching_weeks})
    remarks = " | ".join(_unique_ordered([course.remarks for course in courses if course.remarks]))

    return Course(
        module_code=base.module_code,
        activity=base.activity,
        prog_yr=" / ".join(groups),
        class_size=sum(course.class_size for course in courses),
        delivery_mode=base.delivery_mode,
        teaching_weeks=weeks,
        week_pattern=_infer_week_pattern(weeks),
        staff_ids=staff_ids,
        duration_hrs=max(course.duration_hrs for course in courses),
        is_common_module=True,
        staff_names=staff_names,
        remarks=remarks,
        source_file="; ".join(_unique_ordered([course.source_file for course in courses])),
        group_ids=groups,
    )


def prepare_courses_for_scheduling(courses: list[Course]) -> list[Course]:
    """Merge common modules so all affected cohorts share the same slot and room."""
    common_groups: dict[tuple[str, str], list[Course]] = defaultdict(list)
    normal_courses: list[Course] = []
    for course in courses:
        if course.is_common_module:
            common_groups[_common_group_key(course)].append(course)
        else:
            normal_courses.append(course)

    merged_common = [build_common_course(group) for group in common_groups.values()]
    return merged_common + normal_courses


def make_weekly_assignments(course: Course, room: Room, day: str, start_time: str) -> list[Assignment]:
    """Create one assignment per unblocked teaching week using one weekly pattern."""
    return [
        Assignment(course=course, room=room, timeslot=TimeSlot(day=day, start_time=start_time, week=week))
        for week in schedulable_weeks(course.teaching_weeks)
    ]


def _candidate_precheck(candidate: Assignment, index: ScheduleIndex) -> list[str]:
    """Fast pre-check for slot occupancy and lunch feasibility."""
    if candidate.timeslot is None:
        return ["No timeslot assigned"]
    if candidate.room is None:
        return ["No room assigned"]

    week = candidate.timeslot.week
    day = candidate.timeslot.day
    room_id = candidate.room.room_id
    occupied = occupied_start_times(candidate)
    violations: list[str] = []
    groups = course_groups(candidate.course)

    if room_is_exclusive(candidate.room):
        for block in occupied:
            if (week, day, block, room_id) in index.room_slots:
                violations.append("Room clash")
                break
    for staff_id in candidate.course.staff_ids:
        if not staff_id:
            continue
        if any((week, day, block, staff_id) in index.staff_slots for block in occupied):
            violations.append("Staff clash")
            break
    for group in groups:
        if any((week, day, block, group) in index.group_slots for block in occupied):
            violations.append("Student group clash")
            break

    if groups:
        for group in groups:
            occupied_lunch = set(index.group_lunch_blocks.get((week, day, group), set())) | {block for block in occupied if block in LUNCH_BLOCKS}
            if all(block in occupied_lunch for block in LUNCH_BLOCKS):
                violations.append("Student group has no free lunch block between 11:00 and 14:00")
                break

    return violations


def can_place_assignments(candidates: list[Assignment], index: ScheduleIndex) -> bool:
    """Return True if all candidate assignments pass fast feasibility checks."""
    staged_index = index.copy()
    for candidate in candidates:
        if _candidate_precheck(candidate, staged_index):
            return False
        staged_index.add(candidate)
    return True


def _validate_candidate_pattern(candidates: list[Assignment], existing: list[Assignment]) -> bool:
    """Run the full constraint checker on a candidate pattern once."""
    staged = existing.copy()
    for candidate in candidates:
        if check_hard_constraints(candidate, staged):
            return False
        staged.append(candidate)
    return True


def _reached_candidate_limit(checked: int, max_candidate_patterns: int | None) -> bool:
    """Return True when the optional candidate-pattern cap has been reached."""
    return max_candidate_patterns is not None and checked >= max_candidate_patterns


def _candidate_limit_assignment(course: Course) -> Assignment:
    """Return an unscheduled placeholder for a demo candidate-pattern cap."""
    return Assignment(course=course, room=None, timeslot=None, hard_violations=[MAX_CANDIDATE_PATTERN_LIMIT_REASON])


def schedule_course(
    course: Course,
    rooms: list[Room],
    existing: list[Assignment],
    index: ScheduleIndex,
    max_candidate_patterns: int | None = None,
) -> list[Assignment]:
    """Schedule one course using a consistent weekly room/day/start pattern."""
    if not schedulable_weeks(course.teaching_weeks):
        return [
            Assignment(
                course=course,
                room=None,
                timeslot=None,
                hard_violations=["No schedulable teaching weeks after academic calendar blocks"],
            )
        ]
    checked_patterns = 0
    for room in get_candidate_rooms(course, rooms):
        for day in VALID_DAYS:
            for start_time in VALID_START_TIMES:
                if _reached_candidate_limit(checked_patterns, max_candidate_patterns):
                    return [_candidate_limit_assignment(course)]
                checked_patterns += 1
                candidates = make_weekly_assignments(course, room, day, start_time)
                if can_place_assignments(candidates, index) and _validate_candidate_pattern(candidates, existing):
                    return candidates
    return [Assignment(course=course, room=None, timeslot=None, hard_violations=["Could not find feasible weekly room/day/start pattern"])]


def schedule_course_for_weeks(
    course: Course,
    weeks: list[int],
    rooms: list[Room],
    existing: list[Assignment],
    index: ScheduleIndex,
    max_candidate_patterns: int | None = None,
) -> list[Assignment]:
    """Place selected teaching weeks independently without moving existing classes."""
    weeks_to_schedule = schedulable_weeks(weeks)
    if not weeks_to_schedule:
        return [
            Assignment(
                course=course,
                room=None,
                timeslot=None,
                hard_violations=["No schedulable teaching weeks after academic calendar blocks"],
            )
        ]

    placed: list[Assignment] = []
    staged = existing.copy()
    staged_index = index.copy()
    checked_patterns = 0
    for week in weeks_to_schedule:
        found: Assignment | None = None
        for room in get_candidate_rooms(course, rooms):
            for day in VALID_DAYS:
                for start_time in VALID_START_TIMES:
                    if _reached_candidate_limit(checked_patterns, max_candidate_patterns):
                        placed.append(_candidate_limit_assignment(course))
                        return placed
                    checked_patterns += 1
                    candidate = Assignment(course=course, room=room, timeslot=TimeSlot(day, start_time, week))
                    if _candidate_precheck(candidate, staged_index):
                        continue
                    violations = check_hard_constraints(candidate, staged)
                    if not violations:
                        found = candidate
                        break
                if found:
                    break
            if found:
                break
        if found:
            placed.append(found)
            staged.append(found)
            staged_index.add(found)
        else:
            placed.append(Assignment(course=course, room=None, timeslot=None, hard_violations=[f"Could not find feasible slot for week {week}"]))
    return placed


def schedule_course_by_week(course: Course, rooms: list[Room], existing: list[Assignment], index: ScheduleIndex) -> list[Assignment]:
    """Fallback scheduler that places each unblocked teaching week independently."""
    return schedule_course_for_weeks(course, course.teaching_weeks, rooms, existing, index)


def _is_unscheduled(assignment: Assignment) -> bool:
    """Return True when an assignment still lacks a usable room or timeslot."""
    return assignment.room is None or assignment.timeslot is None


def _is_candidate_limit_assignment(assignment: Assignment) -> bool:
    """Return True when retrying would hit the same candidate-pattern cap."""
    return MAX_CANDIDATE_PATTERN_LIMIT_REASON in assignment.hard_violations


def _target_retry_weeks(assignment: Assignment) -> list[int]:
    """Return the specific teaching weeks represented by an unscheduled placeholder."""
    for violation in assignment.hard_violations:
        match = re.search(r"week (\d+)", violation, flags=re.IGNORECASE)
        if match:
            return [int(match.group(1))]
    return schedulable_weeks(assignment.course.teaching_weeks)


def _retry_unscheduled_assignment(
    assignment: Assignment,
    rooms: list[Room],
    existing: list[Assignment],
    index: ScheduleIndex,
    allow_weekly_fallback: bool,
    max_candidate_patterns: int | None = None,
) -> list[Assignment]:
    """Retry one unscheduled assignment without moving already scheduled ones."""
    if _is_candidate_limit_assignment(assignment):
        return [assignment]
    if allow_weekly_fallback:
        retry = schedule_course_for_weeks(
            assignment.course,
            _target_retry_weeks(assignment),
            rooms,
            existing,
            index,
            max_candidate_patterns=max_candidate_patterns,
        )
    else:
        retry = schedule_course(assignment.course, rooms, existing, index, max_candidate_patterns=max_candidate_patterns)
    if any(not _is_unscheduled(item) for item in retry):
        return retry
    return [assignment]


def retry_unscheduled_assignments(
    assignments: list[Assignment],
    rooms: list[Room],
    index: ScheduleIndex,
    allow_weekly_fallback: bool = True,
    max_retry_assignments: int | None = None,
    max_candidate_patterns: int | None = None,
) -> list[Assignment]:
    """Retry only unscheduled assignments after the greedy pass has finished."""
    scheduled = [assignment for assignment in assignments if not _is_unscheduled(assignment)]
    permanent_failures = [
        assignment
        for assignment in assignments
        if _is_unscheduled(assignment) and _is_candidate_limit_assignment(assignment)
    ]
    retry_queue = [
        assignment
        for assignment in assignments
        if _is_unscheduled(assignment) and not _is_candidate_limit_assignment(assignment)
    ]
    retry_queue = sorted(retry_queue, key=lambda item: _course_difficulty(item.course, rooms), reverse=True)
    if max_retry_assignments is None:
        retry_now = retry_queue
        retry_later: list[Assignment] = permanent_failures
    else:
        retry_now = retry_queue[:max_retry_assignments]
        retry_later = retry_queue[max_retry_assignments:] + permanent_failures

    results: list[Assignment] = list(scheduled)
    for placeholder in retry_now:
        placed = _retry_unscheduled_assignment(
            placeholder,
            rooms,
            results,
            index,
            allow_weekly_fallback,
            max_candidate_patterns=max_candidate_patterns,
        )
        results.extend(placed)
        for item in placed:
            if not _is_unscheduled(item):
                index.add(item)
    results.extend(retry_later)
    return results


ProgressCallback = Callable[[int, int, Course], None]


def generate_schedule(
    courses: list[Course],
    rooms: list[Room],
    allow_weekly_fallback: bool = True,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 25,
    max_retry_assignments: int | None = None,
    max_candidate_patterns: int | None = None,
) -> list[Assignment]:
    """Generate a complete greedy timetable with common modules merged first."""
    assignments: list[Assignment] = []
    index = build_schedule_index(assignments)
    prepared_courses = prepare_courses_for_scheduling(courses)
    ordered_courses = sorted(prepared_courses, key=lambda item: _course_difficulty(item, rooms))
    total = len(ordered_courses)

    for position, course in enumerate(ordered_courses, start=1):
        if progress_callback and (position == 1 or position == total or progress_interval <= 1 or position % progress_interval == 0):
            progress_callback(position, total, course)

        placed = schedule_course(course, rooms, assignments, index, max_candidate_patterns=max_candidate_patterns)
        stopped_by_limit = placed and MAX_CANDIDATE_PATTERN_LIMIT_REASON in placed[0].hard_violations
        if allow_weekly_fallback and placed and placed[0].hard_violations and not stopped_by_limit:
            placed = schedule_course_for_weeks(
                course,
                course.teaching_weeks,
                rooms,
                assignments,
                index,
                max_candidate_patterns=max_candidate_patterns,
            )
        assignments.extend(placed)
        for assignment in placed:
            if assignment.room is not None and assignment.timeslot is not None and not assignment.hard_violations:
                index.add(assignment)

    return retry_unscheduled_assignments(
        assignments,
        rooms,
        index,
        allow_weekly_fallback=allow_weekly_fallback,
        max_retry_assignments=max_retry_assignments,
        max_candidate_patterns=max_candidate_patterns,
    )
