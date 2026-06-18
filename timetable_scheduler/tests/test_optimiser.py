"""Tests for optimiser acceptance safety."""

from __future__ import annotations

import random

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, count_hard_violations
from optimiser import local_search


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
        "group_ids": ["ENG/YR 1"],
    }
    data.update(overrides)
    return Course(**data)


def _scheduled_count(assignments: list[Assignment]) -> int:
    """Return scheduled assignment count."""
    return sum(1 for item in assignments if item.room is not None and item.timeslot is not None)


def test_optimiser_cannot_accept_hard_invalid_move() -> None:
    """The optimiser should reject moves that create delivery-mode hard violations."""
    course = make_course(delivery_mode="Online - Synchronous")
    original = Assignment(course, Room("ONLINE_ROOM", 9999, "virtual"), TimeSlot("Monday", "10:00", 1))
    schedule = [original]

    result = local_search.try_move_assignment(
        0,
        schedule,
        [Room("R1", 100, "physical")],
        random.Random(1),
        max_candidates=4,
    )

    assert result[0].room is not None
    assert result[0].room.room_id == "ONLINE_ROOM"
    assert count_hard_violations(result) == 0


def test_optimiser_rollback_restores_assignments() -> None:
    """Rejected moves should leave the original schedule untouched."""
    course = make_course()
    original = Assignment(course, Room("R1", 100, "physical"), TimeSlot("Monday", "10:00", 1))
    schedule = [original]

    result = local_search.try_move_assignment(
        0,
        schedule,
        [Room("TOO_SMALL", 10, "physical")],
        random.Random(1),
        max_candidates=4,
    )

    assert result[0].room is not None
    assert result[0].room.room_id == "R1"
    assert schedule[0].room is not None
    assert schedule[0].room.room_id == "R1"


def test_optimiser_coverage_remains_unchanged() -> None:
    """Optimisation should not schedule or remove residual placeholders."""
    scheduled = Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Monday", "10:00", 1))
    unscheduled = Assignment(
        make_course(module_code="ENG1002", staff_ids=["S002"], group_ids=["ENG/YR 2"], prog_yr="ENG/YR 2"),
        None,
        None,
        hard_violations=["Could not find feasible slot for week 1"],
    )
    schedule = [scheduled, unscheduled]

    result = local_search.optimise_schedule(schedule, [Room("R1", 100, "physical")], max_iterations=2)

    assert _scheduled_count(result) == _scheduled_count(schedule)
    assert result[1].room is None
    assert result[1].timeslot is None
    assert result[1].hard_violations == ["Could not find feasible slot for week 1"]


def test_optimiser_preserves_shared_online_concurrency() -> None:
    """Shared ONLINE_ROOM concurrency should remain hard-feasible."""
    schedule = [
        Assignment(
            make_course(module_code="ENG1001", delivery_mode="Online - Synchronous", staff_ids=["S001"], group_ids=["ENG/YR 1"]),
            Room("ONLINE_ROOM", 9999, "virtual"),
            TimeSlot("Monday", "10:00", 1),
        ),
        Assignment(
            make_course(module_code="ENG1002", delivery_mode="Online - Synchronous", staff_ids=["S002"], group_ids=["ENG/YR 2"], prog_yr="ENG/YR 2"),
            Room("ONLINE_ROOM", 9999, "virtual"),
            TimeSlot("Monday", "10:00", 1),
        ),
    ]

    result = local_search.optimise_schedule(schedule, [Room("ONLINE_ROOM", 9999, "virtual")], max_iterations=1)

    assert _scheduled_count(result) == 2
    assert count_hard_violations(result) == 0


def test_physical_room_conflicts_remain_invalid() -> None:
    """Physical room double-booking should remain a hard violation."""
    existing = [
        Assignment(make_course(module_code="ENG1001"), Room("R1", 100, "physical"), TimeSlot("Monday", "10:00", 1))
    ]
    candidate = Assignment(
        make_course(module_code="ENG1002", staff_ids=["S002"], group_ids=["ENG/YR 2"], prog_yr="ENG/YR 2"),
        Room("R1", 100, "physical"),
        TimeSlot("Monday", "10:00", 1),
    )

    assert any("room clash" in issue.lower() for issue in check_hard_constraints(candidate, existing))


def test_worse_soft_score_result_is_rejected(monkeypatch) -> None:
    """A worse soft-score candidate should not replace the baseline."""
    baseline = [Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Tuesday", "10:00", 1))]
    worse = [Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Monday", "09:00", 1))]

    def fake_try_move_assignment(index, assignments, rooms, rng, max_candidates=8, **kwargs):
        return worse

    monkeypatch.setattr(local_search, "try_move_assignment", fake_try_move_assignment)

    result = local_search.optimise_schedule(baseline, [Room("R1", 100, "physical")], max_iterations=1)

    assert result[0].timeslot == TimeSlot("Tuesday", "10:00", 1)


def test_optimiser_reports_early_stopped_with_patience() -> None:
    """A patience setting should stop after configured non-improving iterations."""
    baseline = [Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Tuesday", "10:00", 1))]

    result = local_search.optimise_schedule_with_stats(
        baseline,
        [Room("R1", 100, "physical")],
        max_iterations=5,
        patience=1,
    )

    assert result.status in {"Early stopped", "Improved"}
    assert result.iterations_completed <= 5
    assert _scheduled_count(result.assignments) == _scheduled_count(baseline)


def test_optimiser_reports_time_limit_reached() -> None:
    """A zero-second limit should stop before running the search loop."""
    baseline = [Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Tuesday", "10:00", 1))]

    result = local_search.optimise_schedule_with_stats(
        baseline,
        [Room("R1", 100, "physical")],
        max_iterations=5,
        time_limit_seconds=0,
    )

    assert result.status == "Time limit reached"
    assert result.iterations_completed == 0
    assert _scheduled_count(result.assignments) == _scheduled_count(baseline)


def test_time_limited_large_schedule_preserves_baseline_without_search() -> None:
    """Large time-limited runs should exit cleanly instead of overrunning the demo window."""
    baseline = [
        Assignment(
            make_course(module_code=f"ENG{index}", staff_ids=[f"S{index}"], group_ids=[f"ENG/YR {index}"], prog_yr=f"ENG/YR {index}"),
            Room(f"R{index}", 100, "physical"),
            TimeSlot("Tuesday", "10:00", 1),
        )
        for index in range(1001)
    ]

    result = local_search.optimise_schedule_with_stats(
        baseline,
        [Room("R1", 100, "physical")],
        max_iterations=5,
        time_limit_seconds=120,
        patience=2,
    )

    assert result.status == "Early stopped"
    assert result.iterations_completed == 0
    assert _scheduled_count(result.assignments) == len(baseline)
