"""Input preflight validation for timetabling runs."""

from __future__ import annotations

from data.models import Course, Room
from engine.constraint_checker import is_online_course
from engine.remarks_interpreter import course_remark_requirements
from engine.resource_audit import audit_resources, resource_audit_issues

VALID_ROOM_TYPES = {"physical", "virtual"}


def _issue(
    severity: str,
    entity_type: str,
    entity_id: str,
    issue: str,
    recommendation: str,
) -> dict[str, str]:
    """Build one preflight issue row."""
    return {
        "severity": severity,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "issue": issue,
        "recommendation": recommendation,
    }


def _course_id(course: Course) -> str:
    """Return a readable course identifier."""
    return course.module_code.strip() or "<missing module_code>"


def _is_valid_delivery_mode(course: Course) -> bool:
    """Return True when delivery mode maps to online or face-to-face."""
    mode = course.delivery_mode.strip().lower()
    if not mode:
        return False
    online_markers = ["online", "virtual", "async", "e-learning"]
    f2f_markers = ["f2f", "face", "physical", "in-person", "campus"]
    return any(marker in mode for marker in online_markers + f2f_markers)


def _has_virtual_room(rooms: list[Room]) -> bool:
    """Return True when a virtual room is available."""
    return any(room.room_type == "virtual" for room in rooms)


def _has_suitable_physical_room(course: Course, rooms: list[Room]) -> bool:
    """Return True when at least one physical room can fit the course."""
    return any(room.room_type == "physical" and room.capacity >= course.class_size for room in rooms)


def validate_courses(courses: list[Course], rooms: list[Room]) -> list[dict[str, str]]:
    """Validate course fields and room availability before scheduling."""
    issues: list[dict[str, str]] = []
    for course in courses:
        entity_id = _course_id(course)
        if not course.module_code.strip():
            issues.append(_issue("error", "course", entity_id, "Missing module_code", "Enter a module code."))
        if not course.activity.strip():
            issues.append(_issue("error", "course", entity_id, "Missing activity", "Enter an activity or class type."))
        if course.class_size <= 0:
            issues.append(_issue("error", "course", entity_id, "Class size is not positive", "Enter a class size greater than 0."))
        if course.duration_hrs <= 0:
            issues.append(_issue("error", "course", entity_id, "Duration is not positive", "Enter a duration greater than 0."))
        if not course.teaching_weeks:
            issues.append(_issue("error", "course", entity_id, "Teaching weeks are empty", "Enter at least one teaching week."))
        if not _is_valid_delivery_mode(course):
            issues.append(_issue("warning", "course", entity_id, "Invalid delivery_mode", "Use a recognised online or face-to-face mode."))
            continue
        if is_online_course(course):
            if not _has_virtual_room(rooms):
                issues.append(_issue("error", "course", entity_id, "Online course has no virtual room", "Add a virtual room."))
        elif course.class_size > 0 and not _has_suitable_physical_room(course, rooms):
            issues.append(
                _issue(
                    "error",
                    "course",
                    entity_id,
                    "Face-to-face course has no physical room with enough capacity",
                    "Add a larger physical room or reduce the class size.",
                )
            )
        remark_requirements = course_remark_requirements(course)
        if remark_requirements.needs_manual_review:
            issues.append(
                _issue(
                    "warning",
                    "course",
                    entity_id,
                    "Remark requires manual review",
                    remark_requirements.review_reason or "Review the free-text scheduling remark.",
                )
            )
    return issues


def validate_rooms(rooms: list[Room]) -> list[dict[str, str]]:
    """Validate room fields before scheduling."""
    issues: list[dict[str, str]] = []
    for room in rooms:
        entity_id = room.room_id.strip() or "<missing room_id>"
        if room.capacity <= 0:
            issues.append(_issue("error", "room", entity_id, "Room capacity is not positive", "Enter a room capacity greater than 0."))
        if room.room_type not in VALID_ROOM_TYPES:
            issues.append(_issue("error", "room", entity_id, "Invalid room_type", "Use room_type 'physical' or 'virtual'."))
    return issues


def run_preflight_checks(courses: list[Course], rooms: list[Room]) -> list[dict[str, str]]:
    """Run all preflight checks and return issue rows."""
    audit = audit_resources(courses, rooms)
    return validate_courses(courses, rooms) + validate_rooms(rooms) + resource_audit_issues(audit, courses, rooms)
