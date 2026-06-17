"""Resource supply audit for rooms and online teaching demand."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import config
from data.models import Assignment, Course, Room
from engine.constraint_checker import is_online_course
from engine.demand_metrics import consolidated_requirements
from generator.scheduler import schedulable_weeks

SHARED_VIRTUAL_ROOM_NOTE = "Shared virtual-room policy does not remove tutor or student-group clash checks."
EXCLUSIVE_VIRTUAL_ROOM_NOTE = "Virtual rooms are treated as exclusive room resources."


@dataclass(slots=True)
class VirtualRoomDetail:
    """One virtual-room detail row."""

    room_id: str
    capacity: int
    resource_type: str = ""
    recording: str = ""


@dataclass(slots=True)
class ResourceAudit:
    """Summary of loaded room supply and online teaching demand."""

    total_raw_room_rows: int | None
    total_loaded_rooms: int
    physical_room_count: int
    virtual_room_count: int
    duplicate_room_ids: list[str] = field(default_factory=list)
    skipped_or_invalid_room_rows: int = 0
    virtual_rooms: list[VirtualRoomDetail] = field(default_factory=list)
    online_course_requirements: int = 0
    required_online_teaching_occurrences: int = 0
    scheduled_online_teaching_occurrences: int = 0
    unscheduled_online_teaching_occurrences: int = 0
    peak_online_demand_by_week: list[dict[str, object]] = field(default_factory=list)
    virtual_room_policy: str = ""
    exclusivity_note: str = ""

    @property
    def duplicate_room_id_count(self) -> int:
        """Return the number of duplicated loaded room IDs."""
        return len(self.duplicate_room_ids)

    @property
    def online_coverage_rate_percent(self) -> float:
        """Return scheduled online-occurrence coverage as a percentage."""
        if self.required_online_teaching_occurrences == 0:
            return 0.0
        return self.scheduled_online_teaching_occurrences / self.required_online_teaching_occurrences * 100


def normalise_room_type(value: str) -> str:
    """Normalise common room-type text for audit purposes."""
    text = " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
    if text in {"virtual", "online", "e learning", "elearning", "remote"}:
        return "virtual"
    if text in {"physical", "f2f", "face to face", "in person", "campus"}:
        return "physical"
    return text


def virtual_room_policy_label() -> str:
    """Return the configured virtual-room resource policy label."""
    return "Exclusive virtual resource" if config.VIRTUAL_ROOM_IS_EXCLUSIVE else "Shared delivery-mode placeholder"


def virtual_room_policy_note() -> str:
    """Return a stakeholder-facing note for the virtual-room policy."""
    return EXCLUSIVE_VIRTUAL_ROOM_NOTE if config.VIRTUAL_ROOM_IS_EXCLUSIVE else SHARED_VIRTUAL_ROOM_NOTE


def _room_id_key(room_id: str) -> str:
    """Return a normalised room identifier for duplicate checks."""
    return str(room_id or "").strip().upper()


def _raw_room_rows(path: Path | None) -> tuple[int | None, int]:
    """Return raw room-row and skipped/invalid counts from the source CSV."""
    if path is None or not path.exists():
        return None, 0
    total = 0
    skipped = 0
    with path.open(newline="", encoding="cp1252") as file:
        reader = csv.DictReader(file)
        for row in reader:
            total += 1
            if not str(row.get("Location Name") or "").strip():
                skipped += 1
    return total, skipped


def _duplicate_room_ids(rooms: list[Room]) -> list[str]:
    """Return duplicate loaded room IDs using case-insensitive comparison."""
    counts = Counter(_room_id_key(room.room_id) for room in rooms if _room_id_key(room.room_id))
    return sorted(room_id for room_id, count in counts.items() if count > 1)


def _virtual_room_details(rooms: list[Room]) -> list[VirtualRoomDetail]:
    """Return detail rows for loaded virtual rooms."""
    return [
        VirtualRoomDetail(room.room_id, room.capacity, room.resource_type, room.recording)
        for room in rooms
        if normalise_room_type(room.room_type) == "virtual"
    ]


def _scheduled_online_keys(assignments: list[Assignment]) -> set[tuple[str, str, str, int]]:
    """Return scheduled online course-week occurrence keys."""
    return {
        (
            assignment.course.module_code.strip().upper(),
            assignment.course.activity.strip().lower(),
            assignment.course.prog_yr.strip(),
            assignment.timeslot.week,
        )
        for assignment in assignments
        if assignment.room is not None
        and assignment.timeslot is not None
        and is_online_course(assignment.course)
    }


def _peak_online_demand(courses: list[Course]) -> list[dict[str, object]]:
    """Return programme/week counts for online required occurrences."""
    counts: dict[tuple[str, int], int] = defaultdict(int)
    for course in courses:
        if not is_online_course(course):
            continue
        for week in schedulable_weeks(course.teaching_weeks):
            counts[(course.prog_yr, week)] += 1
    rows = [
        {"Programme/Year": programme, "Week": week, "Required Online Occurrences": count}
        for (programme, week), count in counts.items()
    ]
    return sorted(rows, key=lambda row: int(row["Required Online Occurrences"]), reverse=True)


def audit_resources(
    courses: list[Course],
    rooms: list[Room],
    assignments: list[Assignment] | None = None,
    room_source_path: Path | None = None,
) -> ResourceAudit:
    """Audit loaded room supply against online teaching demand."""
    raw_rows, skipped_rows = _raw_room_rows(room_source_path)
    requirements = consolidated_requirements(courses)
    online_requirements = [course for course in requirements if is_online_course(course)]
    scheduled_online = _scheduled_online_keys(assignments or [])
    required_online = sum(len(schedulable_weeks(course.teaching_weeks)) for course in online_requirements)
    scheduled_count = 0
    for course in online_requirements:
        for week in schedulable_weeks(course.teaching_weeks):
            key = (
                course.module_code.strip().upper(),
                course.activity.strip().lower(),
                course.prog_yr.strip(),
                week,
            )
            if key in scheduled_online:
                scheduled_count += 1

    physical_count = sum(1 for room in rooms if normalise_room_type(room.room_type) == "physical")
    virtual_rooms = _virtual_room_details(rooms)
    return ResourceAudit(
        total_raw_room_rows=raw_rows,
        total_loaded_rooms=len(rooms),
        physical_room_count=physical_count,
        virtual_room_count=len(virtual_rooms),
        duplicate_room_ids=_duplicate_room_ids(rooms),
        skipped_or_invalid_room_rows=skipped_rows,
        virtual_rooms=virtual_rooms,
        online_course_requirements=len(online_requirements),
        required_online_teaching_occurrences=required_online,
        scheduled_online_teaching_occurrences=scheduled_count,
        unscheduled_online_teaching_occurrences=required_online - scheduled_count,
        peak_online_demand_by_week=_peak_online_demand(online_requirements),
        virtual_room_policy=virtual_room_policy_label(),
        exclusivity_note=virtual_room_policy_note(),
    )


def resource_audit_issues(audit: ResourceAudit, courses: list[Course], rooms: list[Room]) -> list[dict[str, str]]:
    """Return advisory validation issues from the resource audit."""
    issues: list[dict[str, str]] = []
    online_courses = [course for course in courses if is_online_course(course)]
    if online_courses and audit.virtual_room_count == 0:
        issues.append(
            {
                "severity": "warning",
                "entity_type": "resource_audit",
                "entity_id": "virtual_rooms",
                "issue": "No virtual rooms loaded while online courses exist",
                "recommendation": "Verify the room source data includes virtual-room resources for online delivery.",
            }
        )
    if (
        config.VIRTUAL_ROOM_IS_EXCLUSIVE
        and online_courses
        and audit.virtual_room_count == 1
        and audit.required_online_teaching_occurrences > 50
    ):
        issues.append(
            {
                "severity": "warning",
                "entity_type": "resource_audit",
                "entity_id": "virtual_rooms",
                "issue": "Only one virtual room loaded with high online demand",
                "recommendation": "Confirm whether the single virtual room is an exclusive resource or a generic online placeholder.",
            }
        )
    if audit.duplicate_room_ids:
        issues.append(
            {
                "severity": "warning",
                "entity_type": "resource_audit",
                "entity_id": "duplicate_room_ids",
                "issue": "Duplicate room IDs loaded",
                "recommendation": f"Review duplicate room IDs: {', '.join(audit.duplicate_room_ids)}.",
            }
        )
    max_online_size = max((course.class_size for course in online_courses), default=0)
    for room in audit.virtual_rooms:
        if room.capacity < max_online_size:
            issues.append(
                {
                    "severity": "warning",
                    "entity_type": "resource_audit",
                    "entity_id": room.room_id,
                    "issue": "Virtual room capacity below online class enrolment",
                    "recommendation": "Increase virtual room capacity or correct online enrolment/resource data.",
                }
            )
    for room in rooms:
        if normalise_room_type(room.room_type) not in {"physical", "virtual"}:
            issues.append(
                {
                    "severity": "warning",
                    "entity_type": "resource_audit",
                    "entity_id": room.room_id or "<missing room_id>",
                    "issue": "Room type has inconsistent spelling or casing",
                    "recommendation": "Use a room type that normalises to physical or virtual.",
                }
            )
    return issues
