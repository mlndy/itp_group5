"""Tests for scheduler integration of interpreted remarks."""

from __future__ import annotations

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, count_hard_violations
from engine.remarks_interpreter import assignment_rooms, course_remark_requirements, interpret_remarks
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
    """Over-limit parallel-track requests should be visible but non-blocking."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, remarks="Split into 3 parallel tracks at one go")
    rooms = [Room("R1", 40, "physical"), Room("R2", 40, "physical"), Room("R3", 40, "physical")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room is not None
    assert schedule[0].hard_violations == []
    assert course_remark_requirements(course).needs_manual_review is True


def test_hybrid_class_uses_recording_capable_physical_room(monkeypatch) -> None:
    """Hybrid remarks should select a physical recording-capable room."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Hybrid delivery required")
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
    course = make_course(remarks="Hybrid delivery required")
    rooms = [Room("NORMAL", 100, "physical", recording="No")]

    schedule = scheduler.generate_schedule([course], rooms, allow_weekly_fallback=False)

    assert schedule[0].room is None
    assert schedule[0].hard_violations
    assert schedule[0].base_unscheduled_reason
    assert schedule[0].remark_unscheduled_reason == "Explicit hybrid-capable room requirement could not be satisfied."


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


def test_unsupported_remark_does_not_prevent_scheduling(monkeypatch) -> None:
    """Unsupported remarks should remain visible without blocking structured scheduling."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Discuss with programme lead nearer to term")

    schedule = scheduler.generate_schedule([course], [Room("R1", 100, "physical")], allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "R1"
    assert schedule[0].hard_violations == []
    assert course_remark_requirements(course).needs_manual_review is True


def test_additional_rooms_for_quizzes_is_non_blocking(monkeypatch) -> None:
    """Incomplete extra-room requests should not unschedule the normal class."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Additional rooms for quizzes")

    schedule = scheduler.generate_schedule([course], [Room("R1", 100, "physical")], allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "R1"
    assert schedule[0].hard_violations == []
    assert course_remark_requirements(course).needs_manual_review is True


def test_room_preference_does_not_prevent_scheduling(monkeypatch) -> None:
    """Soft room preferences should not be hard filters."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Computer room preferred")

    schedule = scheduler.generate_schedule([course], [Room("SEM1", 100, "physical", resource_type="Seminar Room")], allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "SEM1"
    assert schedule[0].hard_violations == []


def test_may_need_hybrid_does_not_require_recording_room(monkeypatch) -> None:
    """Uncertain hybrid wording should schedule in a normal physical room."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="May need hybrid")

    schedule = scheduler.generate_schedule([course], [Room("NORMAL", 100, "physical", recording="No")], allow_weekly_fallback=False)

    assert schedule[0].room.room_id == "NORMAL"
    assert schedule[0].selected_delivery_mode != "hybrid"
    assert schedule[0].hard_violations == []


def test_explicit_two_room_failure_preserves_base_and_remark_reasons(monkeypatch) -> None:
    """Two-room failures should keep both normal and special-request reasons."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(class_size=30, remarks="Need 2 rooms")

    schedule = scheduler.generate_schedule([course], [Room("R1", 20, "physical")], allow_weekly_fallback=False)

    assert schedule[0].room is None
    assert schedule[0].base_unscheduled_reason == "Could not find feasible weekly room/day/start pattern"
    assert schedule[0].remark_unscheduled_reason == "Explicit two-room requirement could not be satisfied simultaneously."
    assert schedule[0].base_unscheduled_reason in schedule[0].hard_violations
    assert schedule[0].remark_unscheduled_reason in schedule[0].hard_violations


def test_fixed_day_time_filters_candidate_patterns_before_demo_cap(monkeypatch) -> None:
    """Fixed day/time remarks should not waste the candidate cap on impossible slots."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday", "Thursday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "14:00"])
    course = make_course(remarks="Must be Thursday at 2 pm")

    schedule = scheduler.generate_schedule(
        [course],
        [Room("SR1", 100, "physical", resource_type="Seminar Room")],
        allow_weekly_fallback=False,
        max_candidate_patterns=1,
    )

    assert schedule[0].room is not None
    assert schedule[0].timeslot.day == "Thursday"
    assert schedule[0].timeslot.start_time == "14:00"
    assert schedule[0].hard_violations == []


def test_clear_day_time_range_schedules_at_requested_start(monkeypatch) -> None:
    """Complete day/time ranges should constrain both day and start time."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday", "Tuesday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])
    course = make_course(duration_hrs=2, remarks="Monday 10am-12pm")

    schedule = scheduler.generate_schedule([course], [Room("R1", 100, "physical")], allow_weekly_fallback=False)

    assert schedule[0].timeslot.day == "Monday"
    assert schedule[0].timeslot.start_time == "10:00"
    assert schedule[0].hard_violations == []


def test_plural_weekday_time_range_does_not_move_to_monday(monkeypatch) -> None:
    """Plural weekday timing remarks should stay on the requested weekday."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday", "Tuesday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00", "10:00"])
    course = make_course(duration_hrs=2, remarks="Tuesdays, 9am-11am")

    schedule = scheduler.generate_schedule([course], [Room("R1", 100, "physical")], allow_weekly_fallback=False)

    assert schedule[0].timeslot.day == "Tuesday"
    assert schedule[0].timeslot.start_time == "09:00"
    assert schedule[0].hard_violations == []


def test_full_day_time_range_preserves_duration_evidence_without_hard_violation(monkeypatch) -> None:
    """A 9AM-6PM remark should remain visible even when structured duration is used."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(duration_hrs=2, remarks="9AM-6PM")

    schedule = scheduler.generate_schedule([course], [Room("R1", 100, "physical")], allow_weekly_fallback=False)

    assert course_remark_requirements(course).duration_override_hours == 9
    assert schedule[0].timeslot.start_time == "09:00"
    assert schedule[0].hard_violations == []


def test_disabled_remarks_do_not_filter_candidate_rooms() -> None:
    """Feature-flag-disabled runs should use the same room pool as plain structured data."""
    course = make_course(remarks="Hybrid delivery required")
    rooms = [
        Room("NORMAL", 100, "physical", recording="No"),
        Room("REC", 100, "physical", recording="Yes"),
        Room("ONLINE_ROOM", 9999, "virtual"),
    ]

    enabled = scheduler.get_candidate_rooms(course, rooms, enable_remark_interpretation=True)
    disabled = scheduler.get_candidate_rooms(course, rooms, enable_remark_interpretation=False)

    assert [room.room_id for room in enabled] == ["REC"]
    assert [room.room_id for room in disabled] == ["NORMAL", "REC"]


def test_disabled_remarks_do_not_create_hard_violations() -> None:
    """Remark-derived hard rules must disappear when the feature flag is disabled."""
    course = make_course(remarks="Must use computer lab")
    assignment = Assignment(
        course,
        Room("SEM1", 100, "physical", resource_type="Seminar Room"),
        TimeSlot("Monday", "09:00", 1),
    )

    enabled = check_hard_constraints(assignment, [], enable_remark_interpretation=True)
    disabled = check_hard_constraints(assignment, [], enable_remark_interpretation=False)

    assert any("room type" in issue.lower() for issue in enabled)
    assert disabled == []


def test_disabled_remarks_keep_course_ordering_neutral() -> None:
    """Source remark metadata must not change disabled baseline course difficulty."""
    remarked = make_course(remarks="Hybrid delivery required")
    plain = make_course(remarks="")
    rooms = [Room("NORMAL", 100, "physical", recording="No")]

    assert scheduler._course_difficulty(  # noqa: SLF001 - regression coverage for deterministic ordering.
        remarked,
        rooms,
        enable_remark_interpretation=False,
    ) == scheduler._course_difficulty(  # noqa: SLF001 - regression coverage for deterministic ordering.
        plain,
        rooms,
        enable_remark_interpretation=False,
    )


def test_disabled_remarks_can_schedule_otherwise_blocked_remark_course(monkeypatch) -> None:
    """A disabled baseline should schedule by structured fields even when remarks would block it."""
    monkeypatch.setattr(scheduler, "VALID_DAYS", ["Monday"])
    monkeypatch.setattr(scheduler, "VALID_START_TIMES", ["09:00"])
    course = make_course(remarks="Hybrid delivery required")
    rooms = [Room("NORMAL", 100, "physical", recording="No")]

    enabled = scheduler.generate_schedule(
        [course],
        rooms,
        allow_weekly_fallback=False,
        enable_remark_interpretation=True,
    )
    disabled = scheduler.generate_schedule(
        [course],
        rooms,
        allow_weekly_fallback=False,
        enable_remark_interpretation=False,
    )

    assert enabled[0].room is None
    assert disabled[0].room.room_id == "NORMAL"
    assert disabled[0].hard_violations == []
