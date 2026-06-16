"""Tests for input preflight validation."""

from __future__ import annotations

from data.models import Course, Room
from engine.preflight_validator import run_preflight_checks, validate_courses, validate_rooms


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
    }
    data.update(overrides)
    return Course(**data)


def test_preflight_detects_invalid_course_size() -> None:
    """Class sizes must be positive."""
    issues = validate_courses([make_course(class_size=0)], [Room("R1", 100, "physical")])

    assert any(issue["issue"] == "Class size is not positive" for issue in issues)


def test_preflight_detects_missing_suitable_room() -> None:
    """Face-to-face courses need a physical room with enough capacity."""
    issues = validate_courses([make_course(class_size=120)], [Room("R1", 80, "physical")])

    assert any("no physical room with enough capacity" in issue["issue"] for issue in issues)


def test_preflight_detects_invalid_room_capacity() -> None:
    """Room capacities must be positive."""
    issues = validate_rooms([Room("R1", 0, "physical")])

    assert any(issue["issue"] == "Room capacity is not positive" for issue in issues)


def test_run_preflight_combines_course_and_room_checks() -> None:
    """The combined preflight runner should include course and room issues."""
    issues = run_preflight_checks([make_course(class_size=-1)], [Room("R1", 0, "unknown")])

    entity_types = {issue["entity_type"] for issue in issues}
    assert {"course", "room"} <= entity_types
