"""Unit tests for critical hard constraints."""

from __future__ import annotations

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints


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
