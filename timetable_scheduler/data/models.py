"""Dataclasses used by the timetabling system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class Course:
    """A timetable activity that must be scheduled."""

    module_code: str
    activity: str
    prog_yr: str
    class_size: int
    delivery_mode: str
    teaching_weeks: list[int]
    week_pattern: str
    staff_ids: list[str]
    duration_hrs: float
    is_common_module: bool = False
    staff_names: list[str] = field(default_factory=list)
    remarks: str = ""
    source_file: str = ""
    group_ids: list[str] = field(default_factory=list)
    source_sheet: str = ""
    source_row: int | None = None
    remark_requirements: Any = None
    is_fixed_requirement: bool = False
    fixed_source: str | None = None


@dataclass(slots=True)
class Room:
    """A physical or virtual room resource."""

    room_id: str
    capacity: int
    room_type: str
    resource_type: str = ""
    recording: str = ""


@dataclass(slots=True, frozen=True)
class TimeSlot:
    """A weekly day/start combination."""

    day: str
    start_time: str
    week: int


@dataclass(slots=True)
class Assignment:
    """A scheduled course-room-timeslot decision."""

    course: Course
    room: Optional[Room]
    timeslot: Optional[TimeSlot]
    hard_violations: list[str] = field(default_factory=list)
    soft_violations: list[str] = field(default_factory=list)
    additional_rooms: tuple[Room, ...] = ()
    selected_delivery_mode: str = ""
    base_unscheduled_reason: str = ""
    remark_unscheduled_reason: str = ""
    is_fixed: bool = False
    fixed_source: str | None = None

    @property
    def status(self) -> str:
        """Return a simple status label for reporting."""
        if self.hard_violations:
            return "Invalid"
        if self.soft_violations:
            return "Valid with soft issues"
        return "Valid"

    @property
    def all_rooms(self) -> tuple[Room, ...]:
        """Return primary and additional rooms in output order."""
        if self.room is None:
            return ()
        return (self.room, *self.additional_rooms)


@dataclass(frozen=True, slots=True)
class FixedSession:
    """A structured fixed teaching session from the official lab workbook."""

    programme_year: str
    module_code: str
    group_id: str
    group_size: int | None
    day: str
    start_time: str
    duration_hours: float
    teaching_weeks: tuple[int, ...]
    locations: tuple[str, ...]
    staff_ids: tuple[str, ...]
    staff_names: tuple[str, ...]
    source_file: str
    source_sheet: str
    source_row: int
