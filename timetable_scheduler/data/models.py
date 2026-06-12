"""Dataclasses used by the timetabling system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
    duration_hrs: int
    is_common_module: bool = False
    staff_names: list[str] = field(default_factory=list)
    remarks: str = ""
    source_file: str = ""
    group_ids: list[str] = field(default_factory=list)


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

    @property
    def status(self) -> str:
        """Return a simple status label for reporting."""
        if self.hard_violations:
            return "Invalid"
        if self.soft_violations:
            return "Valid with soft issues"
        return "Valid"
