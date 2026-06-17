"""Tests for invariant demand and coverage metrics."""

from __future__ import annotations

import config
from data.models import Assignment, Course, Room, TimeSlot
from engine.demand_metrics import build_demand_metrics
from generator.scheduler import generate_schedule


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1, 2, 3],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
        "group_ids": ["ENG/YR 1"],
    }
    data.update(overrides)
    return Course(**data)


def test_three_week_course_fully_scheduled() -> None:
    """A three-week scheduled course should count three occurrences."""
    course = make_course()
    assignments = [
        Assignment(course, Room("R1", 100, "physical"), TimeSlot("Monday", "09:00", week))
        for week in [1, 2, 3]
    ]

    metrics = build_demand_metrics([course], assignments)

    assert metrics.required_teaching_occurrences == 3
    assert metrics.scheduled_teaching_occurrences == 3
    assert metrics.unscheduled_teaching_occurrences == 0
    assert metrics.courses_fully_scheduled == 1


def test_three_week_course_unscheduled_placeholder_counts_all_missing_weeks() -> None:
    """One multi-week placeholder should count every missing week occurrence."""
    course = make_course()
    assignments = [
        Assignment(
            course=course,
            room=None,
            timeslot=None,
            hard_violations=["Could not find feasible weekly room/day/start pattern"],
        )
    ]

    metrics = build_demand_metrics([course], assignments)

    assert metrics.required_teaching_occurrences == 3
    assert metrics.scheduled_teaching_occurrences == 0
    assert metrics.unscheduled_teaching_occurrences == 3
    assert metrics.courses_fully_unscheduled == 1


def test_partially_scheduled_course_counts_missing_weeks() -> None:
    """Partial schedule output should split scheduled and missing occurrences."""
    course = make_course()
    assignments = [
        Assignment(course, Room("R1", 100, "physical"), TimeSlot("Monday", "09:00", 1)),
        Assignment(course, Room("R1", 100, "physical"), TimeSlot("Monday", "09:00", 2)),
        Assignment(course, None, None, hard_violations=["Could not find feasible slot for week 3"]),
    ]

    metrics = build_demand_metrics([course], assignments)

    assert metrics.required_teaching_occurrences == 3
    assert metrics.scheduled_teaching_occurrences == 2
    assert metrics.unscheduled_teaching_occurrences == 1
    assert metrics.courses_partially_scheduled == 1


def test_common_module_consolidated_demand_counted_once() -> None:
    """Common module demand should follow the existing shared-requirement design."""
    courses = [
        make_course(module_code="ENG1001", prog_yr="ENG/YR 1", class_size=30, is_common_module=True),
        make_course(module_code="ENG1001", prog_yr="DSC/YR 1", class_size=20, is_common_module=True, staff_ids=["S002"]),
    ]
    schedule = generate_schedule(courses, [Room("BIG", 100, "physical")], allow_weekly_fallback=False)

    metrics = build_demand_metrics(courses, schedule)

    assert metrics.input_course_records == 2
    assert metrics.consolidated_course_requirements == 1
    assert metrics.required_teaching_occurrences == 3
    assert metrics.scheduled_teaching_occurrences == 3


def test_room_changes_do_not_change_required_teaching_occurrences() -> None:
    """Required demand should be independent of room availability."""
    course = make_course(class_size=80)
    no_room_schedule = generate_schedule([course], [Room("SMALL", 20, "physical")], allow_weekly_fallback=False)
    enough_room_schedule = generate_schedule([course], [Room("BIG", 100, "physical")], allow_weekly_fallback=False)

    no_room_metrics = build_demand_metrics([course], no_room_schedule)
    enough_room_metrics = build_demand_metrics([course], enough_room_schedule)

    assert no_room_metrics.required_teaching_occurrences == enough_room_metrics.required_teaching_occurrences == 3
    assert no_room_metrics.scheduled_teaching_occurrences == 0
    assert enough_room_metrics.scheduled_teaching_occurrences == 3


def test_candidate_limits_do_not_change_required_teaching_occurrences() -> None:
    """Candidate caps should affect coverage, not required demand."""
    course = make_course()
    rooms = [Room("R1", 100, "physical")]
    capped_schedule = generate_schedule([course], rooms, allow_weekly_fallback=False, max_candidate_patterns=0)
    full_schedule = generate_schedule([course], rooms, allow_weekly_fallback=False)

    capped_metrics = build_demand_metrics([course], capped_schedule)
    full_metrics = build_demand_metrics([course], full_schedule)

    assert capped_metrics.required_teaching_occurrences == full_metrics.required_teaching_occurrences == 3
    assert capped_metrics.is_consistent
    assert full_metrics.is_consistent


def test_virtual_room_policy_does_not_change_required_teaching_occurrences(monkeypatch) -> None:
    """Virtual-room exclusivity is resource policy, not input teaching demand."""
    from generator import scheduler

    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    rooms = [Room("ONLINE_ROOM", 9999, "virtual")]
    courses = [
        make_course(module_code="ENG1001", delivery_mode="Online - Synchronous", staff_ids=["S001"], prog_yr="ENG/YR 1"),
        make_course(module_code="ENG1002", delivery_mode="Online - Synchronous", staff_ids=["S002"], prog_yr="ENG/YR 2"),
    ]

    monkeypatch.setattr(config, "VIRTUAL_ROOM_IS_EXCLUSIVE", True)
    exclusive_metrics = build_demand_metrics(
        courses,
        generate_schedule(courses, rooms, allow_weekly_fallback=False),
    )
    monkeypatch.setattr(config, "VIRTUAL_ROOM_IS_EXCLUSIVE", False)
    shared_metrics = build_demand_metrics(
        courses,
        generate_schedule(courses, rooms, allow_weekly_fallback=False),
    )

    assert exclusive_metrics.required_teaching_occurrences == shared_metrics.required_teaching_occurrences == 6
    assert shared_metrics.scheduled_teaching_occurrences >= exclusive_metrics.scheduled_teaching_occurrences


def test_engineering_dataset_required_teaching_occurrences_remain_stable() -> None:
    """Engineering input demand should remain fixed for final comparisons."""
    from config import DEFAULT_COMMON_MODULE_FILE, DEFAULT_ENGINEERING_FOLDER
    from data.loader import load_common_modules, load_courses_from_folder

    common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
    courses, _ = load_courses_from_folder(DEFAULT_ENGINEERING_FOLDER, common_modules=common_modules)

    metrics = build_demand_metrics(courses, [], input_course_records=len(courses))

    assert metrics.input_course_records == 507
    assert metrics.consolidated_course_requirements == 465
    assert metrics.required_teaching_occurrences == 2777
