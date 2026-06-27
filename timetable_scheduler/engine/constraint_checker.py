"""Hard and soft constraint checks for timetable assignments."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

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
    PREFERRED_ONLINE_DAYS,
    PUBLIC_HOLIDAY_WEEKS,
    SHORT_CAMPUS_DAY_MAX_HOURS,
    SHORT_CAMPUS_DAY_MIN_HOURS,
    SOFT_CONSTRAINT_WEIGHTS,
    SOFT_RULE_BACK_TO_BACK_HOURS,
    SOFT_RULE_ENDS_AFTER_17,
    SOFT_RULE_FIRST_SLOT,
    SOFT_RULE_LOW_ROOM_UTILISATION,
    SOFT_RULE_MAX_CONSECUTIVE_HOURS,
    SOFT_RULE_ONLINE_F2F_SWITCH,
    SOFT_RULE_ONLINE_PREFERRED_DAY,
    SOFT_RULE_PROGRAMME_ONLINE_DAY_SPREAD,
    SOFT_RULE_REMARK_ROOM_TYPE_PREFERENCE,
    SOFT_RULE_SHORT_CAMPUS_DAY,
    SOFT_RULE_TUTOR_IDLE_GAP,
    SOFT_RULE_WASTED_FREE_SLOT,
    TERM_BREAK_WEEKS,
    VALID_DAYS,
    ENABLE_REMARK_INTERPRETATION,
)
from data.models import Assignment, Course, Room
from engine.remarks_interpreter import (
    assignment_rooms,
    course_scheduling_requirements,
    course_remark_requirements,
    room_matches_type,
    room_supports_recording,
)

MAX_BACK_TO_BACK_GROUP_HOURS = 3


def time_to_hour(time_text: str) -> int:
    """Convert HH:MM text to an integer hour."""
    return int(str(time_text).split(":")[0])


def time_to_minutes(time_text: str) -> int:
    """Convert HH:MM text to minutes after midnight."""
    hour_text, minute_text = str(time_text).split(":", 1)
    return int(hour_text) * 60 + int(minute_text)


def hour_to_time(hour: int) -> str:
    """Convert an integer hour to HH:MM text."""
    return f"{hour:02d}:00"


def minutes_to_time(minutes: int) -> str:
    """Convert minutes after midnight to HH:MM text."""
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def assignment_end_minutes(assignment: Assignment) -> int:
    """Return the ending time in minutes after midnight."""
    if assignment.timeslot is None:
        return 0
    return time_to_minutes(assignment.timeslot.start_time) + int(round(float(assignment.course.duration_hrs) * 60))


def assignment_end_time(assignment: Assignment) -> str:
    """Return the ending time as HH:MM text."""
    return minutes_to_time(assignment_end_minutes(assignment))


def assignment_end_hour(assignment: Assignment) -> int:
    """Return the ending hour, rounded up for partial-hour sessions."""
    return math.ceil(assignment_end_minutes(assignment) / 60)


def occupied_start_times(assignment: Assignment) -> set[str]:
    """Return all hourly start blocks occupied by an assignment."""
    if assignment.timeslot is None:
        return set()
    start_minutes = time_to_minutes(assignment.timeslot.start_time)
    end_minutes = assignment_end_minutes(assignment)
    start_hour = start_minutes // 60
    end_hour = math.ceil(end_minutes / 60)
    return {hour_to_time(hour) for hour in range(start_hour, end_hour)}


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


def assignment_delivery_mode(assignment: Assignment) -> str:
    """Return the selected delivery mode for an assignment."""
    return assignment.selected_delivery_mode or assignment.course.delivery_mode


def is_physical_course(course: Course) -> bool:
    """Return True if a course needs a physical teaching room."""
    return not is_online_course(course)


def room_is_exclusive(room: Room | None) -> bool:
    """Return True when the room should block concurrent room use."""
    if room is None:
        return False
    if room.room_type == "external":
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
    left_groups = course_groups(left)
    right_groups = course_groups(right)
    if left_groups & right_groups:
        return True
    for left_group in left_groups:
        for right_group in right_groups:
            if left_group.startswith(f"{right_group}/") or right_group.startswith(f"{left_group}/"):
                return True
    return False


def _staff_intersection(left: Course, right: Course) -> set[str]:
    """Return shared staff IDs between two courses."""
    return set(left.staff_ids) & set(right.staff_ids)


def check_room_capacity(assignment: Assignment) -> list[str]:
    """Check whether the room can hold the class size."""
    rooms = assignment_rooms(assignment)
    if not rooms:
        return ["No room assigned"]
    if any("capacity unavailable" in room.resource_type.casefold() for room in rooms):
        return []
    if any(room.room_type == "external" for room in rooms):
        return []
    total_capacity = sum(room.capacity for room in rooms)
    if total_capacity < assignment.course.class_size:
        return [f"Room capacity too small: {total_capacity} < {assignment.course.class_size}"]
    return []


def check_delivery_mode_room(assignment: Assignment) -> list[str]:
    """Check delivery mode compatibility with physical or virtual room."""
    if assignment.room is None:
        return []
    course = assignment.course
    room = assignment.room
    mode = assignment_delivery_mode(assignment).lower()
    if "hybrid" in mode:
        if room.room_type != "physical":
            return ["Hybrid class must reserve a physical teaching room"]
        return []
    if ("online" in mode or "virtual" in mode or "async" in mode or "e-learning" in mode) and room.room_type != "virtual":
        return ["Online class must use a virtual room"]
    if not ("online" in mode or "virtual" in mode or "async" in mode or "e-learning" in mode) and room.room_type == "virtual":
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
    start_minutes = time_to_minutes(assignment.timeslot.start_time)
    end_minutes = assignment_end_minutes(assignment)
    violations: list[str] = []
    if day not in VALID_DAYS:
        violations.append(f"Invalid teaching day: {day}")
    if start_minutes < EARLIEST_START_HOUR * 60:
        violations.append("Class starts before 09:00")
    if end_minutes > LATEST_END_HOUR * 60:
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
    rooms = [room for room in assignment_rooms(assignment) if room_is_exclusive(room)]
    if not rooms:
        return []
    for other in existing:
        other_rooms = [room for room in assignment_rooms(other) if room_is_exclusive(room)]
        for room in rooms:
            if any(other_room.room_id == room.room_id for other_room in other_rooms) and assignments_overlap(assignment, other):
                return [f"Room clash with {other.course.module_code} {other.course.activity}"]
    return []


def check_remark_requirements(assignment: Assignment) -> list[str]:
    """Check hard constraints created from supported remark interpretations."""
    return check_remark_requirements_for_mode(
        assignment,
        enable_remark_interpretation=ENABLE_REMARK_INTERPRETATION,
    )


def check_remark_requirements_for_mode(
    assignment: Assignment,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[str]:
    """Check hard constraints created from remarks when the feature is enabled."""
    if not enable_remark_interpretation:
        return []
    requirements = course_scheduling_requirements(assignment.course)
    violations: list[str] = []
    if (
        requirements.required_room_count == 1
        and not requirements.required_room_types
        and not requirements.requires_hybrid_delivery
        and not requirements.requires_recording_room
        and not requirements.fixed_days
        and not requirements.fixed_start_times
        and not requirements.fixed_end_times
        and not requirements.fixed_time_ranges
        and not requirements.fixed_venues
        and requirements.duration_override_hours is None
    ):
        return []

    rooms = assignment_rooms(assignment)
    if requirements.required_room_count > len(rooms):
        violations.append(
            f"Remark requires {requirements.required_room_count} room(s), but {len(rooms)} assigned"
        )
    if requirements.required_room_count > 2:
        violations.append("Remark requires more rooms than the output workbook supports")
    if requirements.fixed_days and assignment.timeslot is not None and assignment.timeslot.day not in requirements.fixed_days:
        violations.append(f"Remark requires day in {list(requirements.fixed_days)}")
    if requirements.fixed_start_times and assignment.timeslot is not None and assignment.timeslot.start_time not in requirements.fixed_start_times:
        violations.append(f"Remark requires start time in {list(requirements.fixed_start_times)}")
    if requirements.fixed_end_times and assignment.timeslot is not None and assignment_end_time(assignment) not in requirements.fixed_end_times:
        violations.append(f"Remark requires end time in {list(requirements.fixed_end_times)}")
    if requirements.fixed_time_ranges and assignment.timeslot is not None:
        actual_range = (assignment.timeslot.start_time, assignment_end_time(assignment))
        if actual_range not in requirements.fixed_time_ranges:
            violations.append(f"Remark requires time range in {list(requirements.fixed_time_ranges)}")
    if requirements.duration_override_hours is not None:
        if abs(float(assignment.course.duration_hrs) - requirements.duration_override_hours) > 0.01:
            violations.append(f"Remark requires duration {requirements.duration_override_hours:g} hour(s)")
    if requirements.fixed_venues and rooms:
        assigned = {room.room_id.casefold() for room in rooms}
        required = {venue.casefold() for venue in requirements.fixed_venues}
        if not assigned & required:
            violations.append(f"Remark requires venue in {list(requirements.fixed_venues)}")
    for room_type in requirements.required_room_types:
        if not rooms or not all(room_matches_type(room, room_type) for room in rooms):
            violations.append(f"Remark requires room type: {room_type}")
    if requirements.requires_hybrid_delivery:
        if not rooms or rooms[0].room_type != "physical":
            violations.append("Remark requires hybrid delivery with a physical room")
        elif not room_supports_recording(rooms[0]):
            violations.append("Remark requires a recording or hybrid-capable physical room")
    elif requirements.requires_recording_room:
        if not rooms or not room_supports_recording(rooms[0]):
            violations.append("Remark requires a recording-capable room")
    return violations


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


def check_hard_constraints(
    assignment: Assignment,
    existing: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[str]:
    """Return all hard constraint violations for one candidate assignment."""
    violations: list[str] = []
    violations.extend(check_room_capacity(assignment))
    violations.extend(check_delivery_mode_room(assignment))
    violations.extend(
        check_remark_requirements_for_mode(
            assignment,
            enable_remark_interpretation=enable_remark_interpretation,
        )
    )
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
        return [f"{SOFT_RULE_LOW_ROOM_UTILISATION}: {utilisation:.0%}"]
    return []


def check_remark_preferences(
    assignment: Assignment,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[str]:
    """Penalise supported remark preferences that are not satisfied."""
    if not enable_remark_interpretation:
        return []
    requirements = course_remark_requirements(assignment.course)
    if not requirements.preferred_room_types or assignment.room is None:
        return []
    rooms = assignment_rooms(assignment)
    issues: list[str] = []
    for room_type in requirements.preferred_room_types:
        if not any(room_matches_type(room, room_type) for room in rooms):
            issues.append(f"{SOFT_RULE_REMARK_ROOM_TYPE_PREFERENCE}: {room_type}")
    return issues


def check_first_or_last_slot(assignment: Assignment) -> list[str]:
    """Penalise very early or very late teaching slots."""
    if assignment.timeslot is None:
        return []
    issues: list[str] = []
    if assignment.timeslot.start_time == FIRST_SLOT:
        issues.append(SOFT_RULE_FIRST_SLOT)
    if assignment.timeslot.start_time in LAST_SLOT_STARTS or assignment_end_hour(assignment) > 17:
        issues.append(SOFT_RULE_ENDS_AFTER_17)
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
                    issues[id(right)].append(f"{SOFT_RULE_ONLINE_F2F_SWITCH} for same {label}")
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
                issues[id(right)].append(f"{SOFT_RULE_TUTOR_IDLE_GAP}: {gap} hours")
            elif gap > 0:
                issues[id(right)].append(SOFT_RULE_WASTED_FREE_SLOT)
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
            f"{SOFT_RULE_BACK_TO_BACK_HOURS}: {len(run)} hours"
        )
    if len(run) > MAX_CONSECUTIVE_HOURS:
        issues[id(block_to_assignment[run[-1]])].append(
            f"{SOFT_RULE_MAX_CONSECUTIVE_HOURS}: {len(run)} hours"
        )


def check_short_campus_day(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Penalise one- or two-hour F2F campus days for student groups."""
    grouped: dict[tuple[str, int, str], dict[str, object]] = defaultdict(lambda: {"hours": set(), "assignments": []})
    for assignment in assignments:
        if assignment.timeslot is None or not is_physical_course(assignment.course):
            continue
        for group in course_groups(assignment.course):
            row = grouped[(group, assignment.timeslot.week, assignment.timeslot.day)]
            row["hours"].update(range(time_to_hour(assignment.timeslot.start_time), assignment_end_hour(assignment)))  # type: ignore[union-attr]
            row["assignments"].append(assignment)  # type: ignore[union-attr]

    issues: dict[int, list[str]] = defaultdict(list)
    for (group, week, day), row in grouped.items():
        hours = set(row["hours"])  # type: ignore[arg-type]
        if not (SHORT_CAMPUS_DAY_MIN_HOURS <= len(hours) <= SHORT_CAMPUS_DAY_MAX_HOURS):
            continue
        items = sorted(
            row["assignments"],  # type: ignore[arg-type]
            key=lambda item: (time_to_hour(item.timeslot.start_time) if item.timeslot else 0, item.course.module_code),
        )
        if items:
            issues[id(items[-1])].append(
                f"{SOFT_RULE_SHORT_CAMPUS_DAY}: student group {group} has only {len(hours)} F2F hour(s) on {day} week {week}"
            )
    return issues


def _day_order(day: str) -> int:
    """Return configured weekday order for deterministic clustering checks."""
    return VALID_DAYS.index(day) if day in VALID_DAYS else len(VALID_DAYS)


def check_programme_online_day_clustering(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Penalise programme/year online classes spread beyond one preferred day."""
    grouped: dict[tuple[str, int], list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        if assignment.timeslot is None or not is_online_course(assignment.course):
            continue
        programme = assignment.course.prog_yr.strip().lower()
        if programme:
            grouped[(programme, assignment.timeslot.week)].append(assignment)

    issues: dict[int, list[str]] = defaultdict(list)
    for (programme, week), items in grouped.items():
        days = sorted({item.timeslot.day for item in items if item.timeslot is not None}, key=_day_order)
        preferred_days = [day for day in days if day in PREFERRED_ONLINE_DAYS]
        anchor_day = preferred_days[0] if preferred_days else (days[0] if days else "")
        for assignment in items:
            if assignment.timeslot is None:
                continue
            day = assignment.timeslot.day
            if day not in PREFERRED_ONLINE_DAYS:
                issues[id(assignment)].append(f"{SOFT_RULE_ONLINE_PREFERRED_DAY}: {day}")
            if len(days) > 1 and day != anchor_day:
                issues[id(assignment)].append(
                    f"{SOFT_RULE_PROGRAMME_ONLINE_DAY_SPREAD}: {programme} has online classes on {len(days)} days in week {week}"
                )
    return issues


def annotate_schedule_violations(
    assignments: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> list[Assignment]:
    """Refresh hard and soft violation lists for a full schedule."""
    checked: list[Assignment] = []
    for assignment in assignments:
        previous = [item for item in checked]
        assignment.hard_violations = check_hard_constraints(
            assignment,
            previous,
            enable_remark_interpretation=enable_remark_interpretation,
        )
        assignment.soft_violations = []
        assignment.soft_violations.extend(check_room_utilisation(assignment))
        assignment.soft_violations.extend(
            check_remark_preferences(
                assignment,
                enable_remark_interpretation=enable_remark_interpretation,
            )
        )
        assignment.soft_violations.extend(check_first_or_last_slot(assignment))
        checked.append(assignment)

    global_soft_maps = [
        check_online_f2f_switch(checked),
        check_long_idle_gaps(checked),
        check_consecutive_hours(checked),
        check_short_campus_day(checked),
        check_programme_online_day_clustering(checked),
    ]
    for assignment in checked:
        for issue_map in global_soft_maps:
            assignment.soft_violations.extend(issue_map.get(id(assignment), []))
    return checked


def soft_violation_rule(violation: str) -> str:
    """Return the canonical soft-rule name for one violation string."""
    for rule_name in SOFT_CONSTRAINT_WEIGHTS:
        if violation.startswith(rule_name):
            return rule_name
    return violation.split(":", 1)[0]


def soft_violation_breakdown(
    assignments: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> dict[str, int]:
    """Return raw soft-violation counts by canonical rule name."""
    annotate_schedule_violations(assignments, enable_remark_interpretation=enable_remark_interpretation)
    counts: Counter[str] = Counter()
    for assignment in assignments:
        counts.update(soft_violation_rule(violation) for violation in assignment.soft_violations)
    return dict(sorted(counts.items()))


def weighted_soft_score(
    assignments: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> int:
    """Return weighted soft score using configured soft-constraint weights."""
    annotate_schedule_violations(assignments, enable_remark_interpretation=enable_remark_interpretation)
    total = 0
    for assignment in assignments:
        for violation in assignment.soft_violations:
            total += SOFT_CONSTRAINT_WEIGHTS.get(soft_violation_rule(violation), 1)
    return total


def count_hard_violations(
    assignments: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> int:
    """Count hard violations in a schedule."""
    annotate_schedule_violations(assignments, enable_remark_interpretation=enable_remark_interpretation)
    return sum(len(assignment.hard_violations) for assignment in assignments)


def count_soft_violations(
    assignments: list[Assignment],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> int:
    """Count soft violations in a schedule."""
    annotate_schedule_violations(assignments, enable_remark_interpretation=enable_remark_interpretation)
    return sum(len(assignment.soft_violations) for assignment in assignments)
