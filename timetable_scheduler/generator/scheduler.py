"""Greedy timetable generator that prioritises hard-constraint feasibility."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations, product
from typing import Callable

from config import (
    BLOCKED_WEEKS,
    ENABLE_REMARK_INTERPRETATION,
    LUNCH_BLOCKS,
    MAX_REMARK_ROOM_COMBINATIONS,
    MIN_ROOM_UTILISATION,
    VALID_DAYS,
    VALID_START_TIMES,
)
from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, course_groups, is_online_course, occupied_start_times, room_is_exclusive
from engine.remarks_interpreter import (
    RemarkRequirements,
    assignment_rooms,
    course_scheduling_requirements,
    interpret_remarks,
    remark_unscheduled_reason,
    room_matches_type,
    room_supports_recording,
)

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
        occupied = occupied_start_times(assignment)

        for block in occupied:
            for room in assignment_rooms(assignment):
                if room_is_exclusive(room):
                    self.room_slots.add((week, day, block, room.room_id))
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


def _remarks_for_course(course: Course, enabled: bool = ENABLE_REMARK_INTERPRETATION) -> RemarkRequirements:
    """Return remark requirements when the feature flag is enabled."""
    if not enabled:
        return RemarkRequirements()
    return course_scheduling_requirements(course)


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


def _room_matches_required_types(room: Room, requirements: RemarkRequirements) -> bool:
    """Return True when a room satisfies all hard room-type requirements."""
    return all(room_matches_type(room, room_type) for room_type in requirements.required_room_types)


def _room_matches_preferred_types(room: Room, requirements: RemarkRequirements) -> bool:
    """Return True when a room satisfies any supported soft room preference."""
    return not requirements.preferred_room_types or any(
        room_matches_type(room, room_type) for room_type in requirements.preferred_room_types
    )


def _remark_room_sort_key(course: Course, room: Room, requirements: RemarkRequirements) -> tuple[int, int, int, int, int]:
    """Rank rooms using hard remark needs without letting preferences reduce coverage."""
    recording = 0 if not requirements.requires_recording_room or room_supports_recording(room) else 1
    return (recording, *_room_preference_score(course, room))


def get_candidate_rooms(
    course: Course,
    rooms: list[Room],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[Room]:
    """Return rooms compatible with delivery mode and capacity."""
    requirements = _remarks_for_course(course, enable_remark_interpretation)
    required_count = max(requirements.required_room_count, 1)

    if requirements.requires_hybrid_delivery:
        candidates = [
            room
            for room in rooms
            if room.room_type == "physical"
            and _room_matches_required_types(room, requirements)
            and room_supports_recording(room)
            and (required_count > 1 or room.capacity >= course.class_size)
        ]
        return sorted(candidates, key=lambda room: _remark_room_sort_key(course, room, requirements))

    if requirements.allowed_delivery_modes:
        candidates = [
            room
            for room in rooms
            if room.room_type in {"physical", "virtual"}
            and (room.room_type == "virtual" or _room_matches_required_types(room, requirements))
            and (required_count > 1 or room.capacity >= course.class_size)
        ]
        return sorted(candidates, key=lambda room: _remark_room_sort_key(course, room, requirements))

    if is_online_course(course):
        candidates = [room for room in rooms if room.room_type == "virtual" and room.capacity >= course.class_size]
        return sorted(candidates, key=lambda room: _room_preference_score(course, room))

    candidates = [
        room
        for room in rooms
        if room.room_type == "physical"
        and _room_matches_required_types(room, requirements)
        and (required_count > 1 or room.capacity >= course.class_size)
    ]
    return sorted(candidates, key=lambda room: _remark_room_sort_key(course, room, requirements))


def get_candidate_room_groups(
    course: Course,
    rooms: list[Room],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[tuple[Room, ...]]:
    """Return bounded compatible room groups for one course."""
    requirements = _remarks_for_course(course, enable_remark_interpretation)
    count = max(requirements.required_room_count, 1)
    if count == 1:
        return [(room,) for room in get_candidate_rooms(course, rooms, enable_remark_interpretation)]
    if count > 2:
        return []

    candidates = [
        room
        for room in get_candidate_rooms(course, rooms, enable_remark_interpretation)
        if room.room_type == "physical"
    ]
    groups = [
        group
        for group in combinations(candidates, count)
        if sum(room.capacity for room in group) >= course.class_size
    ]
    groups = sorted(
        groups,
        key=lambda group: (
            max(sum(room.capacity for room in group) - course.class_size, 0),
            tuple(room.room_id for room in group),
        ),
    )
    return groups[:MAX_REMARK_ROOM_COMBINATIONS]


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
    source_sheets = _unique_ordered([course.source_sheet for course in courses if course.source_sheet])

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
        source_sheet="; ".join(source_sheets),
        source_row=None,
        remark_requirements=interpret_remarks(remarks),
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


def _selected_delivery_mode(course: Course, room_group: tuple[Room, ...], requirements: RemarkRequirements) -> str:
    """Return the effective delivery mode selected for a candidate."""
    if requirements.requires_hybrid_delivery:
        return "hybrid"
    if requirements.allowed_delivery_modes and room_group and room_group[0].room_type == "virtual":
        return "Online - Synchronous"
    if requirements.allowed_delivery_modes and room_group and room_group[0].room_type == "physical":
        return "f2f"
    return course.delivery_mode


def _candidate_days(requirements: RemarkRequirements) -> list[str]:
    """Return valid days after applying hard fixed-day requirements."""
    if not requirements.fixed_days:
        return VALID_DAYS
    return [day for day in VALID_DAYS if day in requirements.fixed_days]


def _candidate_start_times(requirements: RemarkRequirements) -> list[str]:
    """Return valid starts after applying hard fixed-start requirements."""
    if not requirements.fixed_start_times:
        return VALID_START_TIMES
    return [start_time for start_time in VALID_START_TIMES if start_time in requirements.fixed_start_times]


def make_weekly_assignments(
    course: Course,
    room: Room,
    day: str,
    start_time: str,
    additional_rooms: tuple[Room, ...] = (),
    selected_delivery_mode: str = "",
) -> list[Assignment]:
    """Create one assignment per unblocked teaching week using one weekly pattern."""
    return [
        Assignment(
            course=course,
            room=room,
            timeslot=TimeSlot(day=day, start_time=start_time, week=week),
            additional_rooms=additional_rooms,
            selected_delivery_mode=selected_delivery_mode,
        )
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
    rooms = assignment_rooms(candidate)
    occupied = occupied_start_times(candidate)
    violations: list[str] = []
    groups = course_groups(candidate.course)

    for room in rooms:
        if not room_is_exclusive(room):
            continue
        for block in occupied:
            if (week, day, block, room.room_id) in index.room_slots:
                violations.append("Room clash")
                break
        if violations:
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
    return _unscheduled_assignment(course, MAX_CANDIDATE_PATTERN_LIMIT_REASON, include_remark_reason=False)


def _manual_review_assignment(course: Course, reason: str) -> Assignment:
    """Return an unscheduled placeholder for an unsupported applied remark."""
    return _unscheduled_assignment(course, reason)


def _unscheduled_assignment(
    course: Course,
    base_reason: str,
    include_remark_reason: bool = True,
) -> Assignment:
    """Return an unscheduled placeholder with base and remark-specific reasons."""
    remark_reason = remark_unscheduled_reason(course) if include_remark_reason else ""
    violations = [base_reason]
    if remark_reason and remark_reason not in violations:
        violations.append(remark_reason)
    return Assignment(
        course=course,
        room=None,
        timeslot=None,
        hard_violations=violations,
        base_unscheduled_reason=base_reason,
        remark_unscheduled_reason=remark_reason,
    )


def schedule_course(
    course: Course,
    rooms: list[Room],
    existing: list[Assignment],
    index: ScheduleIndex,
    max_candidate_patterns: int | None = None,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[Assignment]:
    """Schedule one course using a consistent weekly room/day/start pattern."""
    if not schedulable_weeks(course.teaching_weeks):
        return [
            _unscheduled_assignment(
                course,
                "No schedulable teaching weeks after academic calendar blocks",
                include_remark_reason=False,
            )
        ]
    requirements = _remarks_for_course(course, enable_remark_interpretation)
    if requirements.required_room_count > 2:
        return [
            _manual_review_assignment(
                course,
                f"Remark requires {requirements.required_room_count} rooms but the output workbook supports Room1 and Room2 only",
            )
        ]
    checked_patterns = 0
    for room_group in get_candidate_room_groups(course, rooms, enable_remark_interpretation):
        room = room_group[0]
        additional_rooms = tuple(room_group[1:])
        selected_delivery_mode = _selected_delivery_mode(course, room_group, requirements)
        for day in _candidate_days(requirements):
            for start_time in _candidate_start_times(requirements):
                if _reached_candidate_limit(checked_patterns, max_candidate_patterns):
                    return [_candidate_limit_assignment(course)]
                checked_patterns += 1
                candidates = make_weekly_assignments(
                    course,
                    room,
                    day,
                    start_time,
                    additional_rooms=additional_rooms,
                    selected_delivery_mode=selected_delivery_mode,
                )
                if can_place_assignments(candidates, index) and _validate_candidate_pattern(candidates, existing):
                    return candidates
    return [_unscheduled_assignment(course, "Could not find feasible weekly room/day/start pattern")]


def schedule_course_for_weeks(
    course: Course,
    weeks: list[int],
    rooms: list[Room],
    existing: list[Assignment],
    index: ScheduleIndex,
    max_candidate_patterns: int | None = None,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[Assignment]:
    """Place selected teaching weeks independently without moving existing classes."""
    weeks_to_schedule = schedulable_weeks(weeks)
    if not weeks_to_schedule:
        return [
            _unscheduled_assignment(
                course,
                "No schedulable teaching weeks after academic calendar blocks",
                include_remark_reason=False,
            )
        ]
    requirements = _remarks_for_course(course, enable_remark_interpretation)
    if requirements.required_room_count > 2:
        return [
            _manual_review_assignment(
                course,
                f"Remark requires {requirements.required_room_count} rooms but the output workbook supports Room1 and Room2 only",
            )
        ]

    placed: list[Assignment] = []
    staged = existing.copy()
    staged_index = index.copy()
    checked_patterns = 0
    for week in weeks_to_schedule:
        found: Assignment | None = None
        for room_group in get_candidate_room_groups(course, rooms, enable_remark_interpretation):
            room = room_group[0]
            additional_rooms = tuple(room_group[1:])
            selected_delivery_mode = _selected_delivery_mode(course, room_group, requirements)
            for day in _candidate_days(requirements):
                for start_time in _candidate_start_times(requirements):
                    if _reached_candidate_limit(checked_patterns, max_candidate_patterns):
                        placed.append(_candidate_limit_assignment(course))
                        return placed
                    checked_patterns += 1
                    candidate = Assignment(
                        course=course,
                        room=room,
                        timeslot=TimeSlot(day, start_time, week),
                        additional_rooms=additional_rooms,
                        selected_delivery_mode=selected_delivery_mode,
                    )
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
            placed.append(_unscheduled_assignment(course, f"Could not find feasible slot for week {week}"))
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
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
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
            enable_remark_interpretation=enable_remark_interpretation,
        )
    else:
        retry = schedule_course(
            assignment.course,
            rooms,
            existing,
            index,
            max_candidate_patterns=max_candidate_patterns,
            enable_remark_interpretation=enable_remark_interpretation,
        )
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
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
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
            enable_remark_interpretation=enable_remark_interpretation,
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
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
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

        placed = schedule_course(
            course,
            rooms,
            assignments,
            index,
            max_candidate_patterns=max_candidate_patterns,
            enable_remark_interpretation=enable_remark_interpretation,
        )
        stopped_by_limit = placed and MAX_CANDIDATE_PATTERN_LIMIT_REASON in placed[0].hard_violations
        if allow_weekly_fallback and placed and placed[0].hard_violations and not stopped_by_limit:
            placed = schedule_course_for_weeks(
                course,
                course.teaching_weeks,
                rooms,
                assignments,
                index,
                max_candidate_patterns=max_candidate_patterns,
                enable_remark_interpretation=enable_remark_interpretation,
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
        enable_remark_interpretation=enable_remark_interpretation,
    )
