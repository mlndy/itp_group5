"""Tests for the local-search optimiser."""

from __future__ import annotations

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import count_hard_violations, count_soft_violations, soft_score
from optimiser.local_search import optimise_schedule_with_report


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "OPT1001",
        "activity": "Lecture",
        "prog_yr": "OPT/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 1,
        "is_common_module": False,
    }
    data.update(overrides)
    return Course(**data)


def _signature(assignments: list[Assignment]) -> list[tuple[str, str | None, str | None, int | None]]:
    """Return a compact schedule signature for equality checks."""
    return [
        (
            item.course.module_code,
            item.room.room_id if item.room else None,
            item.timeslot.day if item.timeslot else None,
            item.timeslot.week if item.timeslot else None,
        )
        for item in assignments
    ]


def test_optimizer_improves_poor_room_utilisation() -> None:
    """The optimiser should move a class into a smaller sufficient room."""
    assignment = Assignment(
        course=make_course(class_size=30),
        room=Room("BIG", 100, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )
    rooms = [Room("SMALL", 40, "physical"), Room("BIG", 100, "physical")]

    optimised, report = optimise_schedule_with_report([assignment], rooms, max_iterations=4)

    assert optimised[0].room is not None
    assert optimised[0].room.room_id == "SMALL"
    assert count_hard_violations(optimised) == 0
    assert count_soft_violations(optimised) <= count_soft_violations([assignment])
    assert report.accepted_moves >= 1


def test_optimizer_improves_first_slot_placement() -> None:
    """The optimiser should move a class away from the first slot if possible."""
    assignment = Assignment(
        course=make_course(class_size=30),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    rooms = [Room("R1", 40, "physical")]

    optimised, report = optimise_schedule_with_report([assignment], rooms, max_iterations=4)

    assert optimised[0].timeslot is not None
    assert optimised[0].timeslot.start_time != "09:00"
    assert count_hard_violations(optimised) == 0
    assert soft_score(optimised) < soft_score([assignment])
    assert report.accepted_moves >= 1


def test_optimizer_rejects_room_clash_move(monkeypatch) -> None:
    """The optimiser must not accept a move that creates a room clash."""
    from optimiser import local_search

    monkeypatch.setattr(local_search, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(local_search, "VALID_START_TIMES", ["09:00", "10:00"])

    first = Assignment(
        course=make_course(module_code="OPT2001", staff_ids=["S001"]),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    second = Assignment(
        course=make_course(module_code="OPT2002", staff_ids=["S002"]),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )

    optimised, report = optimise_schedule_with_report([first, second], [Room("R1", 40, "physical")], max_iterations=4)

    assert _signature(optimised) == _signature([first, second])
    assert count_hard_violations(optimised) == 0
    assert report.accepted_moves == 0


def test_optimizer_rejects_tutor_clash_move(monkeypatch) -> None:
    """The optimiser must not accept a move that creates a tutor clash."""
    from optimiser import local_search

    monkeypatch.setattr(local_search, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(local_search, "VALID_START_TIMES", ["09:00", "10:00"])

    first = Assignment(
        course=make_course(module_code="OPT3001", staff_ids=["S001"]),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    second = Assignment(
        course=make_course(module_code="OPT3002", staff_ids=["S001"]),
        room=Room("R2", 40, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )

    optimised, report = optimise_schedule_with_report([first, second], [Room("R1", 40, "physical"), Room("R2", 40, "physical")], max_iterations=4)

    assert _signature(optimised) == _signature([first, second])
    assert count_hard_violations(optimised) == 0
    assert report.accepted_moves == 0


def test_optimizer_rejects_group_clash_move(monkeypatch) -> None:
    """The optimiser must not accept a move that creates a group clash."""
    from optimiser import local_search

    monkeypatch.setattr(local_search, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(local_search, "VALID_START_TIMES", ["09:00", "10:00"])

    first = Assignment(
        course=make_course(module_code="OPT4001", prog_yr="OPT/YR 1", staff_ids=["S001"]),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    second = Assignment(
        course=make_course(module_code="OPT4002", prog_yr="OPT/YR 1", staff_ids=["S002"]),
        room=Room("R2", 40, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )

    optimised, report = optimise_schedule_with_report([first, second], [Room("R1", 40, "physical"), Room("R2", 40, "physical")], max_iterations=4)

    assert _signature(optimised) == _signature([first, second])
    assert count_hard_violations(optimised) == 0
    assert report.accepted_moves == 0


def test_optimizer_preserves_zero_hard_violations_for_scheduled_assignments() -> None:
    """Optimisation should keep a feasible schedule hard-feasible."""
    assignment = Assignment(
        course=make_course(),
        room=Room("R1", 40, "physical"),
        timeslot=TimeSlot("Monday", "10:00", 1),
    )

    optimised, _ = optimise_schedule_with_report([assignment], [Room("R1", 40, "physical")], max_iterations=4)

    assert count_hard_violations(optimised) == 0


def test_optimizer_is_deterministic_for_same_input() -> None:
    """The optimiser should produce repeatable output for the same input."""
    assignment = Assignment(
        course=make_course(class_size=30),
        room=Room("BIG", 100, "physical"),
        timeslot=TimeSlot("Monday", "09:00", 1),
    )
    rooms = [Room("SMALL", 40, "physical"), Room("BIG", 100, "physical")]

    first_run, _ = optimise_schedule_with_report([assignment], rooms, max_iterations=4)
    second_run, _ = optimise_schedule_with_report([assignment], rooms, max_iterations=4)

    assert _signature(first_run) == _signature(second_run)
    assert first_run[0].room is not None and first_run[0].room.room_id == second_run[0].room.room_id
    assert first_run[0].timeslot == second_run[0].timeslot
