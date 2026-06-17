"""Hard and soft constraint checks for timetable assignments."""

from __future__ import annotations

from collections import defaultdict

import config
from config import (
    BLOCKED_START_TIMES,
    BLOCKED_WEEKS,
    EARLIEST_START_HOUR,
    FIRST_SLOT,
    LAST_SLOT_STARTS,
    LATEST_END_HOUR,
    LUNCH_BLOCKS,
    MAX_CONSECUTIVE_HOURS,
    MAX_TUTOR_IDLE_GAP_HOURS,
    MIN_ROOM_UTILISATION,
    PUBLIC_HOLIDAY_WEEKS,
    TERM_BREAK_WEEKS,
    VALID_DAYS,
)
from data.models import Assignment, Course, Room

MAX_BACK_TO_BACK_GROUP_HOURS = 3


def time_to_hour(time_text: str) -> int:
    """Convert HH:MM text to an integer hour."""
    return int(str(time_text).split(":")[0])


def hour_to_time(hour: int) -> str:
    """Convert an integer hour to HH:MM text."""
    return f"{hour:02d}:00"


def assignment_end_hour(assignment: Assignment) -> int:
    """Return the ending hour of an assignment."""
    if assignment.timeslot is None:
        return 0
    return time_to_hour(assignment.timeslot.start_time) + assignment.course.duration_hrs


def occupied_start_times(assignment: Assignment) -> set[str]:
    """Return all hourly start blocks occupied by an assignment."""
    if assignment.timeslot is None:
        return set()
    start = time_to_hour(assignment.timeslot.start_time)
    return {hour_to_time(hour) for hour in range(start, start + assignment.course.duration_hrs)}


def assignments_overlap(left: Assignment, right: Assignment) -> bool:
    """Return True when two assignments overlap in week, day, and time."""
    if left.timeslot is None or right.timeslot is None:
        return False
    if left.timeslot.week != right.timeslot.week or left.timeslot.day != right.timeslot.day:
        return False
    return bool(occupied_start_times(left) & occupied_start_times(right))


def is_online_course(course: Course) -> bool:
    """Return True if a course uses online delivery."""
    mode = course.delivery_mode.lower()
    return "online" in mode or "virtual" in mode or "async" in mode or "e-learning" in mode


def is_physical_course(course: Course) -> bool:
    """Return True if a course needs a physical teaching room."""
    return not is_online_course(course)


def room_is_exclusive(room: Room | None) -> bool:
    """Return True when the room should block concurrent room use."""
    if room is None:
        return False
    if room.room_type == "virtual" and not config.VIRTUAL_ROOM_IS_EXCLUSIVE:
        return False
    return True


def course_groups(course: Course) -> set[str]:
    """Return all student groups affected by a course."""
    groups = [group.strip() for group in course.group_ids if group and group.strip()]
    if not groups and course.prog_yr.strip():
        groups = [course.prog_yr.strip()]
    return {group.lower() for group in groups}


def _same_group(left: Course, right: Course) -> bool:
    """Return True if two courses share at least one student group."""
    return bool(course_groups(left) & course_groups(right))


def _staff_intersection(left: Course, right: Course) -> set[str]:
    """Return shared staff IDs between two courses."""
    return set(left.staff_ids) & set(right.staff_ids)


def check_room_capacity(assignment: Assignment) -> list[str]:
    """Check whether the room can hold the class size."""
    if assignment.room is None:
        return ["No room assigned"]
    if assignment.room.capacity < assignment.course.class_size:
        return [f"Room capacity too small: {assignment.room.capacity} < {assignment.course.class_size}"]
    return []


def check_delivery_mode_room(assignment: Assignment) -> list[str]:
    """Check delivery mode compatibility with physical or virtual room."""
    if assignment.room is None:
        return []
    course = assignment.course
    room = assignment.room
    if is_online_course(course) and room.room_type != "virtual":
        return ["Online class must use a virtual room"]
    if is_physical_course(course) and room.room_type == "virtual":
        return ["Face-to-face class must not use a virtual room"]
    return []


def check_week_pattern(assignment: Assignment) -> list[str]:
    """Check whether the assigned week matches the course week pattern."""
    if assignment.timeslot is None:
        return ["No timeslot assigned"]
    week = assignment.timeslot.week
    course = assignment.course
    if course.week_pattern == "ODD" and week % 2 == 0:
        return ["Odd-week course scheduled in even week"]
    if course.week_pattern == "EVEN" and week % 2 == 1:
        return ["Even-week course scheduled in odd week"]
    if week not in course.teaching_weeks:
        return [f"Week {week} is not in teaching weeks {course.teaching_weeks}"]
    return []


def check_time_window(assignment: Assignment) -> list[str]:
    """Check day and start/end time boundaries."""
    if assignment.timeslot is None:
        return []
    day = assignment.timeslot.day
    start_hour = time_to_hour(assignment.timeslot.start_time)
    end_hour = assignment_end_hour(assignment)
    violations: list[str] = []
    if day not in VALID_DAYS:
        violations.append(f"Invalid teaching day: {day}")
    if start_hour < EARLIEST_START_HOUR:
        violations.append("Class starts before 09:00")
    if end_hour > LATEST_END_HOUR:
        violations.append("Class ends after 18:00")
    return violations


def check_blocked_week(assignment: Assignment) -> list[str]:
    """Check academic calendar week blocks."""
    if assignment.timeslot is None:
        return []
    week = assignment.timeslot.week
    violations: list[str] = []
    if week in PUBLIC_HOLIDAY_WEEKS:
        violations.append("Class scheduled during public holiday week")
    if week in TERM_BREAK_WEEKS:
        violations.append("Class scheduled during term break week")
    if week in BLOCKED_WEEKS and week not in PUBLIC_HOLIDAY_WEEKS and week not in TERM_BREAK_WEEKS:
        violations.append("Class scheduled during blocked academic week")
    return violations


def check_blocked_time(assignment: Assignment) -> list[str]:
    """Check institutional blocked day/time rules."""
    if assignment.timeslot is None:
        return []
    day = assignment.timeslot.day
    blocked = BLOCKED_START_TIMES.get(day, set())
    occupied = occupied_start_times(assignment)
    violations: list[str] = []
    if occupied & blocked:
        violations.append(f"Blocked time used on {day}: {sorted(occupied & blocked)}")
    violations.extend(check_blocked_week(assignment))
    return violations


def check_room_clash(assignment: Assignment, existing: list[Assignment]) -> list[str]:
    """Check whether a room is double-booked."""
    if assignment.room is None or not room_is_exclusive(assignment.room):
        return []
    for other in existing:
        if other.room is None or not room_is_exclusive(other.room):
            continue
        if other.room.room_id == assignment.room.room_id and assignments_overlap(assignment, other):
            return [f"Room clash with {other.course.module_code} {other.course.activity}"]
    return []


def check_staff_clash(assignment: Assignment, existing: list[Assignment]) -> list[str]:
    """Check whether a tutor is double-booked."""
    if not assignment.course.staff_ids:
        return []
    for other in existing:
        shared_staff = _staff_intersection(assignment.course, other.course)
        if shared_staff and assignments_overlap(assignment, other):
            return [f"Staff clash for {sorted(shared_staff)}"]
    return []


def check_group_clash(assignment: Assignment, existing: list[Assignment]) -> list[str]:
    """Check whether a student group is double-booked."""
    for other in existing:
        if _same_group(assignment.course, other.course) and assignments_overlap(assignment, other):
            return [f"Student group clash with {other.course.module_code} {other.course.activity}"]
    return []


def _has_lunch_break(assignments: list[Assignment], group: str, week: int, day: str) -> bool:
    """Return True if a group keeps at least one free lunch block."""
    occupied: set[str] = set()
    target = group.strip().lower()
    for assignment in assignments:
        if assignment.timeslot is None:
            continue
        if assignment.timeslot.week != week or assignment.timeslot.day != day:
            continue
        if target not in course_groups(assignment.course):
            continue
        occupied.update(occupied_start_times(assignment))
    return any(block not in occupied for block in LUNCH_BLOCKS)


def check_lunch_break(assignment: Assignment, existing: list[Assignment]) -> list[str]:
    """Check flexible lunch break for every affected student group."""
    if assignment.timeslot is None:
        return []
    combined = existing + [assignment]
    violations: list[str] = []
    for group in sorted(course_groups(assignment.course)):
        has_break = _has_lunch_break(combined, group, assignment.timeslot.week, assignment.timeslot.day)
        if not has_break:
            violations.append(f"Student group {group} has no free lunch block between 11:00 and 14:00")
    return violations


def check_hard_constraints(assignment: Assignment, existing: list[Assignment]) -> list[str]:
    """Return all hard constraint violations for one candidate assignment."""
    violations: list[str] = []
    violations.extend(check_room_capacity(assignment))
    violations.extend(check_delivery_mode_room(assignment))
    violations.extend(check_week_pattern(assignment))
    violations.extend(check_time_window(assignment))
    violations.extend(check_blocked_time(assignment))
    violations.extend(check_room_clash(assignment, existing))
    violations.extend(check_staff_clash(assignment, existing))
    violations.extend(check_group_clash(assignment, existing))
    violations.extend(check_lunch_break(assignment, existing))
    return violations


def check_room_utilisation(assignment: Assignment) -> list[str]:
    """Penalise poor room utilisation below the configured threshold."""
    if assignment.room is None or assignment.room.room_type == "virtual":
        return []
    if assignment.room.capacity <= 0:
        return []
    utilisation = assignment.course.class_size / assignment.room.capacity
    if utilisation < MIN_ROOM_UTILISATION:
        return [f"Low room utilisation: {utilisation:.0%}"]
    return []


def check_first_or_last_slot(assignment: Assignment) -> list[str]:
    """Penalise very early or very late teaching slots."""
    if assignment.timeslot is None:
        return []
    issues: list[str] = []
    if assignment.timeslot.start_time == FIRST_SLOT:
        issues.append("Uses first teaching slot")
    if assignment.timeslot.start_time in LAST_SLOT_STARTS or assignment_end_hour(assignment) > 17:
        issues.append("Class does not end by 17:00")
    return issues


def _group_by_person_day(assignments: list[Assignment], by_staff: bool) -> dict[tuple[str, int, str], list[Assignment]]:
    """Group assignments by staff/group, week, and day."""
    grouped: dict[tuple[str, int, str], list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        if assignment.timeslot is None:
            continue
        people = assignment.course.staff_ids if by_staff else sorted(course_groups(assignment.course))
        for person in people:
            if person:
                grouped[(person, assignment.timeslot.week, assignment.timeslot.day)].append(assignment)
    return grouped


def check_online_f2f_switch(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Penalise adjacent online/F2F switches for the same staff or group."""
    issues: dict[int, list[str]] = defaultdict(list)
    for by_staff in [False, True]:
        grouped = _group_by_person_day(assignments, by_staff=by_staff)
        label = "staff" if by_staff else "group"
        for _, items in grouped.items():
            items = sorted(items, key=lambda item: time_to_hour(item.timeslot.start_time))
            for left, right in zip(items, items[1:]):
                if left.timeslot is None or right.timeslot is None:
                    continue
                if assignment_end_hour(left) != time_to_hour(right.timeslot.start_time):
                    continue
                if is_online_course(left.course) != is_online_course(right.course):
                    issues[id(right)].append(f"Adjacent online/F2F switch for same {label}")
    return issues


def check_long_idle_gaps(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Penalise tutor idle gaps longer than the configured limit."""
    issues: dict[int, list[str]] = defaultdict(list)
    grouped = _group_by_person_day(assignments, by_staff=True)
    for _, items in grouped.items():
        items = sorted(items, key=lambda item: time_to_hour(item.timeslot.start_time))
        for left, right in zip(items, items[1:]):
            if left.timeslot is None or right.timeslot is None:
                continue
            gap = time_to_hour(right.timeslot.start_time) - assignment_end_hour(left)
            if gap > MAX_TUTOR_IDLE_GAP_HOURS:
                issues[id(right)].append(f"Tutor idle gap longer than {MAX_TUTOR_IDLE_GAP_HOURS} hours")
            elif gap > 0:
                issues[id(right)].append("Tutor timetable has wasted free slot")
    return issues


def check_consecutive_hours(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Penalise student groups with too many consecutive teaching hours."""
    issues: dict[int, list[str]] = defaultdict(list)
    grouped = _group_by_person_day(assignments, by_staff=False)
    for _, items in grouped.items():
        block_to_assignment: dict[int, Assignment] = {}
        for assignment in items:
            if assignment.timeslot is None:
                continue
            start = time_to_hour(assignment.timeslot.start_time)
            end = assignment_end_hour(assignment)
            for hour in range(start, end):
                block_to_assignment[hour] = assignment
        if not block_to_assignment:
            continue
        sorted_hours = sorted(block_to_assignment)
        run: list[int] = []
        for hour in sorted_hours:
            if not run or hour == run[-1] + 1:
                run.append(hour)
            else:
                _record_consecutive_issue(run, block_to_assignment, issues)
                run = [hour]
        _record_consecutive_issue(run, block_to_assignment, issues)
    return issues


def _record_consecutive_issue(
    run: list[int],
    block_to_assignment: dict[int, Assignment],
    issues: dict[int, list[str]],
) -> None:
    """Record soft penalties for long student group runs."""
    if len(run) > MAX_BACK_TO_BACK_GROUP_HOURS:
        issues[id(block_to_assignment[run[-1]])].append(
            f"Back-to-back classes exceed {MAX_BACK_TO_BACK_GROUP_HOURS} consecutive hours"
        )
    if len(run) > MAX_CONSECUTIVE_HOURS:
        issues[id(block_to_assignment[run[-1]])].append(
            f"More than {MAX_CONSECUTIVE_HOURS} consecutive teaching hours"
        )


def annotate_schedule_violations(assignments: list[Assignment]) -> list[Assignment]:
    """Refresh hard and soft violation lists for a full schedule."""
    checked: list[Assignment] = []
    for assignment in assignments:
        previous = [item for item in checked]
        assignment.hard_violations = check_hard_constraints(assignment, previous)
        assignment.soft_violations = []
        assignment.soft_violations.extend(check_room_utilisation(assignment))
        assignment.soft_violations.extend(check_first_or_last_slot(assignment))
        checked.append(assignment)

    global_soft_maps = [
        check_online_f2f_switch(checked),
        check_long_idle_gaps(checked),
        check_consecutive_hours(checked),
    ]
    for assignment in checked:
        for issue_map in global_soft_maps:
            assignment.soft_violations.extend(issue_map.get(id(assignment), []))
    return checked


def count_hard_violations(assignments: list[Assignment]) -> int:
    """Count hard violations in a schedule."""
    annotate_schedule_violations(assignments)
    return sum(len(assignment.hard_violations) for assignment in assignments)


def count_soft_violations(assignments: list[Assignment]) -> int:
    """Count soft violations in a schedule."""
    annotate_schedule_violations(assignments)
    return sum(len(assignment.soft_violations) for assignment in assignments)
