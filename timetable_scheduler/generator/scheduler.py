"""Greedy timetable generator that prioritises hard-constraint feasibility."""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from config import BLOCKED_WEEKS, VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, is_online_course


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
        return [room for room in rooms if room.room_type == "virtual" and room.capacity >= course.class_size]

    candidates = [room for room in rooms if room.room_type == "physical" and room.capacity >= course.class_size]
    return sorted(candidates, key=lambda room: _room_suitability_score(course, room))


def _course_difficulty(course: Course, rooms: list[Room]) -> tuple[int, int, int, int]:
    """Sort hardest courses first for better greedy feasibility."""
    room_count = len(get_candidate_rooms(course, rooms))
    return (0 if course.is_common_module else 1, room_count, -course.class_size, -course.duration_hrs)


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


def can_place_assignments(candidates: list[Assignment], existing: list[Assignment]) -> bool:
    """Return True if all candidate assignments satisfy hard constraints together."""
    staged = existing.copy()
    for candidate in candidates:
        violations = check_hard_constraints(candidate, staged)
        if violations:
            return False
        staged.append(candidate)
    return True


def schedule_course(course: Course, rooms: list[Room], existing: list[Assignment]) -> list[Assignment]:
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
    for room in get_candidate_rooms(course, rooms):
        for day in VALID_DAYS:
            for start_time in VALID_START_TIMES:
                candidates = make_weekly_assignments(course, room, day, start_time)
                if can_place_assignments(candidates, existing):
                    return candidates
    return [Assignment(course=course, room=None, timeslot=None, hard_violations=["Could not find feasible weekly room/day/start pattern"])]


def schedule_course_by_week(course: Course, rooms: list[Room], existing: list[Assignment]) -> list[Assignment]:
    """Fallback scheduler that places each unblocked teaching week independently."""
    weeks = schedulable_weeks(course.teaching_weeks)
    if not weeks:
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
    for week in weeks:
        found: Assignment | None = None
        for room in get_candidate_rooms(course, rooms):
            for day in VALID_DAYS:
                for start_time in VALID_START_TIMES:
                    candidate = Assignment(course=course, room=room, timeslot=TimeSlot(day, start_time, week))
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
        else:
            placed.append(Assignment(course=course, room=None, timeslot=None, hard_violations=[f"Could not find feasible slot for week {week}"]))
    return placed


def generate_schedule(courses: list[Course], rooms: list[Room], allow_weekly_fallback: bool = True) -> list[Assignment]:
    """Generate a complete greedy timetable with common modules merged first."""
    assignments: list[Assignment] = []
    prepared_courses = prepare_courses_for_scheduling(courses)
    for course in sorted(prepared_courses, key=lambda item: _course_difficulty(item, rooms)):
        placed = schedule_course(course, rooms, assignments)
        if allow_weekly_fallback and placed and placed[0].hard_violations:
            placed = schedule_course_by_week(course, rooms, assignments)
        assignments.extend(placed)
    return assignments
