"""Unit tests for critical hard constraints."""

from __future__ import annotations

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, count_hard_violations


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "DSC1001",
        "activity": "Tutorial",
        "prog_yr": "DSC/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
    }
    data.update(overrides)
    return Course(**data)


def test_room_capacity_violation() -> None:
    """Room capacity must be at least class size."""
    assignment = Assignment(
        course=make_course(class_size=50),
        room=Room("R1", 30, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    assert any("capacity" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_online_requires_virtual_room() -> None:
    """Online activities must use virtual rooms."""
    assignment = Assignment(
        course=make_course(delivery_mode="Online - Synchronous"),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    assert any("virtual" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_f2f_cannot_use_virtual_room() -> None:
    """Face-to-face activities must not use virtual rooms."""
    assignment = Assignment(
        course=make_course(delivery_mode="f2f"),
        room=Room("ONLINE_ROOM", 9999, "virtual"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    assert any("virtual" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_room_clash_violation() -> None:
    """Two classes cannot use the same room at overlapping times."""
    existing = [
        Assignment(
            course=make_course(module_code="DSC1001"),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    candidate = Assignment(
        course=make_course(module_code="DSC1002", staff_ids=["S002"], prog_yr="DSC/YR 2"),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )
    assert any("room clash" in issue.lower() for issue in check_hard_constraints(candidate, existing))


def test_staff_clash_violation() -> None:
    """A tutor cannot teach two overlapping classes."""
    existing = [
        Assignment(
            course=make_course(module_code="DSC1001", staff_ids=["S001"], prog_yr="DSC/YR 1"),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    candidate = Assignment(
        course=make_course(module_code="DSC1002", staff_ids=["S001"], prog_yr="DSC/YR 2"),
        room=Room("R2", 100, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )
    assert any("staff clash" in issue.lower() for issue in check_hard_constraints(candidate, existing))


def test_student_group_clash_violation() -> None:
    """A student group cannot attend overlapping classes."""
    existing = [
        Assignment(
            course=make_course(module_code="DSC1001", staff_ids=["S001"], prog_yr="DSC/YR 1"),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    candidate = Assignment(
        course=make_course(module_code="DSC1002", staff_ids=["S002"], prog_yr="DSC/YR 1"),
        room=Room("R2", 100, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )
    assert any("student group clash" in issue.lower() for issue in check_hard_constraints(candidate, existing))


def test_wednesday_afternoon_blocked() -> None:
    """Wednesday classes from 13:00 are blocked."""
    assignment = Assignment(
        course=make_course(),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Wednesday", "13:00", 1),
    )
    assert any("blocked" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_friday_lunch_blocked() -> None:
    """Friday 12:00 to 14:00 is blocked."""
    assignment = Assignment(
        course=make_course(),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Friday", "12:00", 1),
    )
    assert any("blocked" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_odd_week_course_not_even_week() -> None:
    """Odd-week activities cannot be scheduled in an even week."""
    assignment = Assignment(
        course=make_course(teaching_weeks=[1, 3, 5], week_pattern="ODD"),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 2),
    )
    assert any("odd-week" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_common_module_combines_cohorts_and_uses_big_room() -> None:
    """Common modules should be scheduled once using combined enrolment."""
    from generator.scheduler import generate_schedule

    courses = [
        make_course(module_code="UCM1001", prog_yr="DSC/YR 1", class_size=40, is_common_module=True),
        make_course(module_code="UCM1001", prog_yr="MEC/YR 1", class_size=35, is_common_module=True, staff_ids=["S002"]),
    ]
    rooms = [Room("SMALL", 50, "physical"), Room("BIG", 100, "physical")]

    schedule = generate_schedule(courses, rooms, allow_weekly_fallback=False)

    assert len(schedule) == 1
    assert schedule[0].course.class_size == 75
    assert set(schedule[0].course.group_ids) == {"DSC/YR 1", "MEC/YR 1"}
    assert schedule[0].room is not None
    assert schedule[0].room.room_id == "BIG"


def test_common_module_blocks_all_linked_groups() -> None:
    """A merged common module should clash with every cohort taking it."""
    common = make_course(
        module_code="UCM1001",
        prog_yr="DSC/YR 1 / MEC/YR 1",
        class_size=75,
        staff_ids=["S001"],
        is_common_module=True,
        group_ids=["DSC/YR 1", "MEC/YR 1"],
    )
    existing = [Assignment(common, Room("BIG", 100, "physical"), TimeSlot("Monday", "09:00", 1))]
    candidate = Assignment(
        make_course(module_code="MEC1001", prog_yr="MEC/YR 1", staff_ids=["S099"]),
        Room("R2", 100, "physical"),
        TimeSlot("Monday", "10:00", 1),
    )

    assert any("student group clash" in issue.lower() for issue in check_hard_constraints(candidate, existing))


def test_exporter_puts_assigned_room_id_in_room1() -> None:
    """Template 2 Room1 column should contain the assigned room ID."""
    from output.exporter import assignment_to_row

    assignment = Assignment(
        course=make_course(group_ids=["DSC/YR 1"]),
        room=Room("PGB-LT-01", 120, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )

    row = assignment_to_row(assignment)

    assert row["Room1"] == "PGB-LT-01"
    assert row["Location Hostkey"] == "PGB-LT-01"
    assert row["Group"] == "DSC/YR 1"


def test_public_holiday_week_causes_hard_violation(monkeypatch) -> None:
    """Public holiday weeks should be blocked by hard constraints."""
    import engine.constraint_checker as checker

    monkeypatch.setattr(checker, "PUBLIC_HOLIDAY_WEEKS", {4})
    monkeypatch.setattr(checker, "BLOCKED_WEEKS", {4})
    assignment = Assignment(
        course=make_course(teaching_weeks=[4]),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 4),
    )

    violations = check_hard_constraints(assignment, [])

    assert "Class scheduled during public holiday week" in violations


def test_term_break_week_causes_hard_violation() -> None:
    """Term break weeks should be blocked by hard constraints."""
    assignment = Assignment(
        course=make_course(teaching_weeks=[7]),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 7),
    )

    violations = check_hard_constraints(assignment, [])

    assert "Class scheduled during term break week" in violations


def test_scheduler_does_not_generate_timeslots_for_blocked_weeks(monkeypatch) -> None:
    """Candidate timeslots should exclude blocked academic weeks."""
    import generator.scheduler as scheduler

    monkeypatch.setattr(scheduler, "BLOCKED_WEEKS", {2})

    timeslots = scheduler.generate_timeslots([1, 2, 3])

    assert {slot.week for slot in timeslots} == {1, 3}


def test_normal_teaching_week_remains_valid() -> None:
    """A normal teaching week should not trigger calendar hard violations."""
    assignment = Assignment(
        course=make_course(teaching_weeks=[1]),
        room=Room("R1", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )

    violations = check_hard_constraints(assignment, [])

    assert violations == []


def test_indexed_scheduler_still_prevents_room_clashes(monkeypatch) -> None:
    """The indexed scheduler should avoid assigning two classes to the same room and slot."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])

    courses = [
        make_course(module_code="DSC2001", prog_yr="DSC/YR 1", staff_ids=["S001"]),
        make_course(module_code="DSC2002", prog_yr="DSC/YR 2", staff_ids=["S002"]),
    ]
    rooms = [Room("R1", 100, "physical")]

    schedule = scheduler.generate_schedule(courses, rooms, allow_weekly_fallback=False)

    scheduled = [item for item in schedule if item.room is not None and item.timeslot is not None]
    assert len(scheduled) == 1
    assert scheduled[0].room.room_id == "R1"


def test_indexed_scheduler_still_prevents_tutor_clashes(monkeypatch) -> None:
    """The indexed scheduler should avoid tutor double-booking."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])

    courses = [
        make_course(module_code="DSC3001", prog_yr="DSC/YR 1", staff_ids=["S001"]),
        make_course(module_code="DSC3002", prog_yr="DSC/YR 2", staff_ids=["S001"]),
    ]
    rooms = [Room("R1", 100, "physical"), Room("R2", 100, "physical")]

    schedule = scheduler.generate_schedule(courses, rooms, allow_weekly_fallback=False)

    scheduled = [item for item in schedule if item.room is not None and item.timeslot is not None]
    assert len(scheduled) == 1


def test_indexed_scheduler_still_prevents_group_clashes(monkeypatch) -> None:
    """The indexed scheduler should avoid student group double-booking."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])

    courses = [
        make_course(module_code="DSC4001", prog_yr="DSC/YR 1", staff_ids=["S001"]),
        make_course(module_code="DSC4002", prog_yr="DSC/YR 1", staff_ids=["S002"]),
    ]
    rooms = [Room("R1", 100, "physical"), Room("R2", 100, "physical")]

    schedule = scheduler.generate_schedule(courses, rooms, allow_weekly_fallback=False)

    scheduled = [item for item in schedule if item.room is not None and item.timeslot is not None]
    assert len(scheduled) == 1


def test_room_ordering_prefers_smaller_sufficient_rooms() -> None:
    """Room ordering should try the tightest sufficient room first."""
    from generator.scheduler import get_candidate_rooms

    course = make_course(class_size=50)
    rooms = [Room("LARGE", 120, "physical"), Room("SMALL", 60, "physical")]

    ordered = get_candidate_rooms(course, rooms)

    assert [room.room_id for room in ordered] == ["SMALL", "LARGE"]


def test_course_ordering_prioritises_more_constrained_courses() -> None:
    """Course difficulty should put larger courses with fewer suitable rooms first."""
    from generator.scheduler import _course_difficulty

    rooms = [Room("SMALL", 40, "physical"), Room("LARGE", 100, "physical")]
    constrained = make_course(module_code="DSC6010", class_size=60)
    flexible = make_course(module_code="DSC6020", class_size=30)

    ordered = sorted([flexible, constrained], key=lambda course: _course_difficulty(course, rooms))

    assert ordered[0].module_code == "DSC6010"


def test_constrained_course_ordering_is_deterministic() -> None:
    """Repeated constrained-first sorting should produce the same order."""
    from generator.scheduler import _course_difficulty

    rooms = [Room("SMALL", 40, "physical"), Room("LARGE", 100, "physical")]
    courses = [
        make_course(module_code="DSC6030", class_size=30, duration_hrs=1),
        make_course(module_code="DSC6010", class_size=60, duration_hrs=2),
        make_course(module_code="DSC6020", class_size=45, duration_hrs=3),
    ]

    first = [course.module_code for course in sorted(courses, key=lambda course: _course_difficulty(course, rooms))]
    second = [course.module_code for course in sorted(courses, key=lambda course: _course_difficulty(course, rooms))]

    assert first == second


def test_engineering_candidate_generation_excludes_blocked_weeks(monkeypatch) -> None:
    """Engineering candidate generation should skip blocked weeks before search."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "BLOCKED_WEEKS", {7})

    timeslots = scheduler.generate_timeslots([6, 7, 8])

    assert {slot.week for slot in timeslots} == {6, 8}


def test_dsc_input_still_has_zero_hard_violations() -> None:
    """The DSC schedule should remain hard-feasible after scheduler changes."""
    from config import DEFAULT_COMMON_MODULE_FILE, DEFAULT_COURSE_FILE, DEFAULT_ROOM_FILE
    from data.loader import load_common_modules, load_courses_from_requirements, load_rooms_from_csv
    from engine.constraint_checker import count_hard_violations
    from generator.scheduler import generate_schedule

    common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
    courses, _ = load_courses_from_requirements(DEFAULT_COURSE_FILE, common_modules=common_modules)
    rooms = load_rooms_from_csv(DEFAULT_ROOM_FILE)

    schedule = generate_schedule(courses, rooms)

    assert count_hard_violations(schedule) == 0



def test_retry_pass_can_schedule_failed_assignment(monkeypatch) -> None:
    """The retry pass should recover a course that the first pass left unscheduled."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])

    existing = [
        Assignment(
            course=make_course(module_code="DSC5001", prog_yr="DSC/YR 1", staff_ids=["S001"]),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=make_course(module_code="DSC5002", prog_yr="DSC/YR 2", staff_ids=["S002"]),
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible weekly room/day/start pattern"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 100, "physical"), Room("R2", 100, "physical")], scheduler.build_schedule_index(existing))
    scheduled = [item for item in result if item.room is not None and item.timeslot is not None]

    assert len(scheduled) == 2
    assert count_hard_violations(result) == 0


def test_retry_pass_targets_failed_week_only(monkeypatch) -> None:
    """The retry pass should not reschedule weeks that already have placements."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])

    course = make_course(
        module_code="DSC5050",
        activity="Quiz",
        prog_yr="DSC/YR 2",
        staff_ids=["S002"],
        duration_hrs=1,
        teaching_weeks=[1, 2],
    )
    existing = [
        Assignment(
            course=course,
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=course,
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible slot for week 2"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 100, "physical")], scheduler.build_schedule_index(existing))
    scheduled_weeks = sorted(item.timeslot.week for item in result if item.timeslot is not None)

    assert scheduled_weeks == [1, 2]
    assert count_hard_violations(result) == 0


def test_retry_pass_does_not_create_room_clashes(monkeypatch) -> None:
    """The retry pass should keep room occupancy clash-free."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])

    existing = [
        Assignment(
            course=make_course(module_code="DSC5101", activity="Quiz", prog_yr="DSC/YR 1", staff_ids=["S001"], duration_hrs=1),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=make_course(module_code="DSC5102", activity="Quiz", prog_yr="DSC/YR 2", staff_ids=["S002"], duration_hrs=1),
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible weekly room/day/start pattern"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 100, "physical"), Room("R2", 100, "physical")], scheduler.build_schedule_index(existing))
    scheduled = [item for item in result if item.room is not None and item.timeslot is not None]

    occupied = {(item.timeslot.week, item.timeslot.day, item.timeslot.start_time, item.room.room_id) for item in scheduled}
    assert len(occupied) == len(scheduled)
    assert count_hard_violations(result) == 0


def test_retry_pass_does_not_create_tutor_clashes(monkeypatch) -> None:
    """The retry pass should keep tutor occupancy clash-free."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])

    existing = [
        Assignment(
            course=make_course(module_code="DSC5201", activity="Quiz", prog_yr="DSC/YR 1", staff_ids=["S001"], duration_hrs=1),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=make_course(module_code="DSC5202", activity="Quiz", prog_yr="DSC/YR 2", staff_ids=["S001"], duration_hrs=1),
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible weekly room/day/start pattern"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 100, "physical"), Room("R2", 100, "physical")], scheduler.build_schedule_index(existing))
    scheduled = [item for item in result if item.room is not None and item.timeslot is not None]

    assert len(scheduled) == 2
    assert count_hard_violations(result) == 0


def test_retry_pass_does_not_create_group_clashes(monkeypatch) -> None:
    """The retry pass should keep student-group occupancy clash-free."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])

    existing = [
        Assignment(
            course=make_course(module_code="DSC5301", activity="Quiz", prog_yr="DSC/YR 1", staff_ids=["S001"], duration_hrs=1),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=make_course(module_code="DSC5302", activity="Quiz", prog_yr="DSC/YR 1", staff_ids=["S002"], duration_hrs=1),
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible weekly room/day/start pattern"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 100, "physical"), Room("R2", 100, "physical")], scheduler.build_schedule_index(existing))
    scheduled = [item for item in result if item.room is not None and item.timeslot is not None]

    assert len(scheduled) == 2
    assert count_hard_violations(result) == 0


def test_retry_pass_keeps_unscheduled_assignments_reported_separately(monkeypatch) -> None:
    """Impossible courses should remain unscheduled after the retry pass."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])

    existing = [
        Assignment(
            course=make_course(module_code="DSC5401", prog_yr="DSC/YR 1", staff_ids=["S001"]),
            room=Room("R1", 10, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        )
    ]
    failed = Assignment(
        course=make_course(module_code="DSC5402", activity="Quiz", prog_yr="DSC/YR 2", class_size=50, staff_ids=["S002"], duration_hrs=1),
        room=None,
        timeslot=None,
        hard_violations=["Could not find feasible weekly room/day/start pattern"],
    )

    result = scheduler.retry_unscheduled_assignments(existing + [failed], [Room("R1", 10, "physical")], scheduler.build_schedule_index(existing))
    scheduled = [item for item in result if item.room is not None and item.timeslot is not None]
    unscheduled = [item for item in result if item.room is None or item.timeslot is None]

    assert len(scheduled) == 1
    assert len(unscheduled) == 1
    assert unscheduled[0].room is None
    assert unscheduled[0].timeslot is None
    assert unscheduled[0].hard_violations


def test_max_candidate_patterns_can_leave_course_unscheduled() -> None:
    """A demo candidate-pattern cap should stop search and leave the course unscheduled."""
    from generator import scheduler

    course = make_course(module_code="DSC5501")
    rooms = [Room("R1", 100, "physical")]

    schedule = scheduler.generate_schedule([course], rooms, max_candidate_patterns=0)

    assert len(schedule) == 1
    assert schedule[0].room is None
    assert schedule[0].timeslot is None
    assert scheduler.MAX_CANDIDATE_PATTERN_LIMIT_REASON in schedule[0].hard_violations


def test_candidate_limit_excludes_incompatible_rooms() -> None:
    """Physical rooms should not consume candidate budget for online courses."""
    from generator import scheduler

    course = make_course(module_code="DSC5601", delivery_mode="Online - Synchronous")
    rooms = [Room("PHYSICAL", 100, "physical"), Room("ONLINE", 100, "virtual")]

    schedule = scheduler.generate_schedule([course], rooms, max_candidate_patterns=1)

    assert len(schedule) == 1
    assert schedule[0].room is not None
    assert schedule[0].room.room_id == "ONLINE"
    assert count_hard_violations(schedule) == 0
