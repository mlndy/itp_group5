"""Tests for virtual-room resource auditing."""

from __future__ import annotations

import config
from data.models import Assignment, Course, Room, TimeSlot
from engine.preflight_validator import run_preflight_checks
from engine.resource_audit import audit_resources, normalise_room_type


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "Online - Synchronous",
        "teaching_weeks": [1, 2, 3],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
        "group_ids": ["ENG/YR 1"],
    }
    data.update(overrides)
    return Course(**data)


def test_virtual_room_count_audit() -> None:
    """Resource audit should count loaded physical and virtual rooms."""
    courses = [make_course()]
    rooms = [Room("ONLINE", 9999, "virtual"), Room("R1", 50, "physical")]

    audit = audit_resources(courses, rooms)

    assert audit.total_loaded_rooms == 2
    assert audit.physical_room_count == 1
    assert audit.virtual_room_count == 1
    assert [room.room_id for room in audit.virtual_rooms] == ["ONLINE"]
    assert audit.virtual_room_policy == "Shared delivery-mode placeholder"
    assert "does not remove tutor" in audit.exclusivity_note


def test_duplicate_virtual_room_detection() -> None:
    """Duplicate room IDs should be detected case-insensitively."""
    rooms = [Room("ONLINE", 9999, "virtual"), Room(" online ", 9999, "virtual")]

    audit = audit_resources([], rooms)

    assert audit.duplicate_room_ids == ["ONLINE"]
    assert audit.duplicate_room_id_count == 1


def test_room_type_normalisation() -> None:
    """Audit normalisation should handle common virtual and physical labels."""
    assert normalise_room_type(" Online ") == "virtual"
    assert normalise_room_type("Face-to-Face") == "physical"
    assert normalise_room_type("VIRTUAL") == "virtual"


def test_online_demand_calculation() -> None:
    """Online required and scheduled occurrences should be counted by week."""
    course = make_course(teaching_weeks=[1, 2, 3])
    assignments = [
        Assignment(course, Room("ONLINE", 9999, "virtual"), TimeSlot("Monday", "09:00", 1)),
        Assignment(course, Room("ONLINE", 9999, "virtual"), TimeSlot("Monday", "09:00", 2)),
    ]

    audit = audit_resources([course], [Room("ONLINE", 9999, "virtual")], assignments)

    assert audit.online_course_requirements == 1
    assert audit.required_online_teaching_occurrences == 3
    assert audit.scheduled_online_teaching_occurrences == 2
    assert audit.unscheduled_online_teaching_occurrences == 1


def test_preflight_warns_when_online_courses_have_no_virtual_room() -> None:
    """Preflight should include an advisory warning when no virtual rooms are loaded."""
    issues = run_preflight_checks([make_course()], [Room("R1", 100, "physical")])

    assert any(issue["issue"] == "No virtual rooms loaded while online courses exist" for issue in issues)


def test_preflight_does_not_warn_single_shared_virtual_room_as_shortage() -> None:
    """A shared virtual placeholder should not be treated as one scarce venue."""
    courses = [make_course(module_code=f"ENG{i:04d}", teaching_weeks=[1, 2, 3]) for i in range(20)]

    issues = run_preflight_checks(courses, [Room("ONLINE", 9999, "virtual")])

    assert not any(issue["issue"] == "Only one virtual room loaded with high online demand" for issue in issues)


def test_preflight_warns_single_exclusive_virtual_room_with_high_online_demand(monkeypatch) -> None:
    """One exclusive virtual room with high demand should remain advisory."""
    monkeypatch.setattr(config, "VIRTUAL_ROOM_IS_EXCLUSIVE", True)
    courses = [make_course(module_code=f"ENG{i:04d}", teaching_weeks=[1, 2, 3]) for i in range(20)]

    issues = run_preflight_checks(courses, [Room("ONLINE", 9999, "virtual")])

    assert any(issue["issue"] == "Only one virtual room loaded with high online demand" for issue in issues)
