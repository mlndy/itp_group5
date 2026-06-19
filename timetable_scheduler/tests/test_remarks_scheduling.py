"""Tests for scheduler integration of interpreted remarks."""

from __future__ import annotations

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, count_hard_violations
from engine.remarks_interpreter import assignment_rooms, interpret_remarks
from generator import scheduler


def make_course(**overrides: object) -> Course:
    """Create a small course for remark scheduling tests."""
    data = {
        "module_code": "ENG9001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 1,
        "is_common_module": False,
        "group_ids": ["ENG/YR 1"],
    }
    data.update(overrides)
    course = Course(**data)
    course.remark_requirements = interpret_remarks(course.remarks)
    return course


def test_small_class_requiring_two_rooms_receives_two_rooms(monkeypatch) -> None:
    """Explicit room-count remarks should allocate both rooms atomically."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, remarks="2 rooms")
    rooms = [Room("R1", 20, "physical"), Room("R2", 20, "physical")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert len(schedule) == 1
    assert [room.room_id for room in assignment_rooms(schedule[0])] == ["R1", "R2"]
    assert schedule[0].timeslot.day == "Monday"
    assert schedule[0].timeslot.start_time == "09:00"
    assert count_hard_violations(schedule) == 0


def test_two_room_assignment_uses_same_day_start_for_all_weeks(monkeypatch) -> None:
    """Multi-week two-room placements should use one recurring room/day/start pattern."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, teaching_weeks=[1, 2], remarks="two rooms")
    rooms = [Room("R1", 20, "physical"), Room("R2", 20, "physical")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert len(schedule) == 2
    assert {item.timeslot.day for item in schedule} == {"Monday"}
    assert {item.timeslot.start_time for item in schedule} == {"09:00"}
    assert {tuple(room.room_id for room in assignment_rooms(item)) for item in schedule} == {("R1", "R2")}


def test_either_room_unavailable_rejects_two_room_candidate(monkeypatch) -> None:
    """A multi-room candidate should fail when either room is already occupied."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    existing = [
        Assignment(
            make_course(module_code="ENG8000", class_size=10, staff_ids=["S900"], prog_yr="ENG/YR 9"),
            Room("R2", 20, "physical"),
            TimeSlot("Monday", "09:00", 1),
        )
    ]
    index = scheduler.build_schedule_index(existing)
    course = make_course(class_size=30, remarks="2 rooms")

    result = scheduler.schedule_course(
        course,
        [Room("R1", 20, "physical"), Room("R2", 20, "physical")],
        existing,
        index,
    )

    assert result[0].room is None
    assert "Could not find feasible" in result[0].hard_violations[0]


def test_failed_two_room_placement_does_not_pollute_index(monkeypatch) -> None:
    """Rejected multi-room attempts should not reserve any new room slots."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    existing = [
        Assignment(
            make_course(module_code="ENG8000", class_size=10, staff_ids=["S900"], prog_yr="ENG/YR 9"),
            Room("R2", 20, "physical"),
            TimeSlot("Monday", "09:00", 1),
        )
    ]
    index = scheduler.build_schedule_index(existing)
    before = set(index.room_slots)

    scheduler.schedule_course(
        make_course(class_size=30, remarks="2 rooms"),
        [Room("R1", 20, "physical"), Room("R2", 20, "physical")],
        existing,
        index,
    )

    assert index.room_slots == before


def test_two_room_combined_capacity_is_checked() -> None:
    """The hard checker should use combined capacity for multiple assigned rooms."""
    assignment = Assignment(
        make_course(class_size=35, remarks="2 rooms"),
        Room("R1", 20, "physical"),
        TimeSlot("Monday", "09:00", 1),
        additional_rooms=(Room("R2", 20, "physical"),),
    )

    assert not any("capacity" in issue.lower() for issue in check_hard_constraints(assignment, []))


def test_required_room_type_applies_to_both_rooms(monkeypatch) -> None:
    """Required room-type remarks should filter all rooms in a multi-room placement."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, remarks="must use computer lab 2 rooms")
    rooms = [
        Room("COMP1", 20, "physical", resource_type="Computer Lab"),
        Room("COMP2", 20, "physical", resource_type="Computer Lab"),
        Room("SEM1", 50, "physical", resource_type="Seminar Room"),
    ]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert [room.room_id for room in assignment_rooms(schedule[0])] == ["COMP1", "COMP2"]
    assert count_hard_violations(schedule) == 0


def test_more_rooms_than_output_supports_remains_unscheduled(monkeypatch) -> None:
    """Requests needing more than Room1/Room2 should go to review instead of being truncated."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, remarks="Split into 3 parallel tracks at one go")
    rooms = [Room("R1", 20, "physical"), Room("R2", 20, "physical"), Room("R3", 20, "physical")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room is None
    assert "Room1 and Room2" in schedule[0].hard_violations[0]


def test_hybrid_class_uses_recording_capable_physical_room(monkeypatch) -> None:
    """Hybrid remarks should select a physical recording-capable room."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Room to support hybrid due to overseas IWSP students")
    rooms = [
        Room("NORMAL", 100, "physical", recording="No"),
        Room("REC", 100, "physical", recording="Yes"),
        Room("ONLINE_ROOM", 9999, "virtual"),
    ]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "REC"
    assert schedule[0].selected_delivery_mode == "hybrid"
    assert count_hard_violations(schedule) == 0


def test_missing_hybrid_capable_room_remains_unscheduled(monkeypatch) -> None:
    """Hybrid-capable room scarcity should leave the class unscheduled."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="hybrid")
    rooms = [Room("NORMAL", 100, "physical", recording="No")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room is None
    assert schedule[0].hard_violations


def test_flexible_delivery_can_choose_virtual_room(monkeypatch) -> None:
    """Either-or delivery remarks should allow one feasible selected mode."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="online or physical")
    rooms = [Room("ONLINE_ROOM", 9999, "virtual")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "ONLINE_ROOM"
    assert schedule[0].selected_delivery_mode == "Online - Synchronous"
    assert count_hard_violations(schedule) == 0
