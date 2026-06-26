"""Convert validated fixed sessions into anchored timetable assignments."""

from __future__ import annotations

import re
from pathlib import Path

from data.models import Assignment, Course, FixedSession, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints
from engine.remarks_interpreter import assignment_room_ids

FIXED_ISSUE_COLUMNS = ["severity", "source", "sheet", "row", "field", "problem", "recommendation"]


def normalise_module_code(module_code: str) -> str:
    """Return the leading SIS-style module code where it is present."""
    text = str(module_code or "").strip().upper()
    match = re.match(r"([A-Z]{2,4}\d{4}[A-Z]?)", text)
    return match.group(1) if match else text


def _issue(
    session: FixedSession,
    *,
    severity: str,
    field: str,
    problem: str,
    recommendation: str,
) -> dict[str, object]:
    """Return one fixed-assignment validation issue."""
    return {
        "severity": severity,
        "source": session.source_file,
        "sheet": session.source_sheet,
        "row": session.source_row,
        "field": field,
        "problem": problem,
        "recommendation": recommendation,
    }


def _room_lookup(rooms: list[Room]) -> dict[str, Room]:
    """Return rooms keyed by normalised room ID."""
    return {room.room_id.casefold(): room for room in rooms}


def _codes_from_location(location: str) -> list[str]:
    """Extract exact venue codes such as E6-07-10 from a location string."""
    text = str(location or "").upper()
    return re.findall(r"\b[A-Z]\d-[0-9A-Z]{2}-[0-9A-Z]{2}(?:-[A-Z0-9]+)?\b", text)


def _is_online_location(location: str) -> bool:
    """Return True when the fixed row explicitly uses online delivery."""
    return "online" in str(location or "").casefold()


def _generic_room_type(location: str) -> str:
    """Return a venue resource-type hint from a generic location description."""
    text = str(location or "").casefold()
    if "computer" in text:
        return "Computer Room"
    if "seminar" in text or "ace" in text:
        return "Seminar Room"
    if "lt" in text or "lecture" in text or "lectorial" in text:
        return "Lectorial"
    if "lab" in text or "laboratory" in text:
        return "Laboratory"
    return ""


def _choose_generic_room(session: FixedSession, rooms: list[Room], room_type: str) -> Room | None:
    """Pick the smallest compatible room for a generic fixed-session request."""
    size = session.group_size or 1
    candidates = [
        room
        for room in rooms
        if room.room_type == "physical"
        and room_type.casefold() in room.resource_type.casefold()
        and room.capacity >= size
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda room: (room.capacity - size, room.room_id))[0]


def _resolve_fixed_rooms(session: FixedSession, rooms: list[Room]) -> tuple[tuple[Room, ...], list[dict[str, object]]]:
    """Resolve exact or generic fixed-session locations to room objects."""
    lookup = _room_lookup(rooms)
    resolved: list[Room] = []
    issues: list[dict[str, object]] = []
    for location in session.locations:
        if _is_online_location(location):
            room = lookup.get("online_room")
            if room is not None:
                resolved.append(room)
                continue
        codes = _codes_from_location(location)
        if not codes and location.casefold() in lookup:
            codes = [location]
        if codes:
            for code in codes:
                room = lookup.get(code.casefold())
                if room is None:
                    issues.append(
                        _issue(
                            session,
                            severity="critical",
                            field="location",
                            problem=f"Exact fixed room '{code}' was not found in the venue data.",
                            recommendation="Correct the room code or add the venue record before generation.",
                        )
                    )
                else:
                    resolved.append(room)
            continue
        room_type = _generic_room_type(location)
        if room_type:
            room = _choose_generic_room(session, rooms, room_type)
            if room is None:
                issues.append(
                    _issue(
                        session,
                        severity="critical",
                        field="location",
                        problem=f"No compatible room was found for generic request '{location}'.",
                        recommendation="Clarify the fixed-session location or add a compatible venue.",
                    )
                )
            else:
                resolved.append(room)
            continue
        issues.append(
            _issue(
                session,
                severity="critical",
                field="location",
                problem=f"Location '{location}' is neither an exact room nor a supported generic room type.",
                recommendation="Use an exact venue code or a supported generic type such as Any Seminar Room.",
            )
        )
    unique: list[Room] = []
    seen: set[str] = set()
    for room in resolved:
        if room.room_id not in seen:
            seen.add(room.room_id)
            unique.append(room)
    return tuple(unique), issues


def _fixed_activity(session: FixedSession, rooms: tuple[Room, ...]) -> str:
    """Infer a stable activity label for fixed-session output."""
    location_text = " ".join(session.locations).casefold()
    resource_text = " ".join(room.resource_type for room in rooms).casefold()
    if "lecture" in location_text or "lectorial" in resource_text:
        return "Lecture"
    if "seminar" in location_text or "seminar" in resource_text:
        return "Seminar"
    return "Laboratory"


def _fixed_delivery_mode(rooms: tuple[Room, ...]) -> str:
    """Return delivery mode for a fixed session based on resolved rooms."""
    if rooms and rooms[0].room_type == "virtual":
        return "Online - Synchronous"
    return "f2f"


def _course_from_fixed_session(session: FixedSession, rooms: tuple[Room, ...]) -> Course:
    """Create a scheduler Course wrapper for one fixed session."""
    group_ids = [session.programme_year]
    if session.group_id:
        group_ids.append(f"{session.programme_year}/{session.group_id}")
    return Course(
        module_code=normalise_module_code(session.module_code),
        activity=_fixed_activity(session, rooms),
        prog_yr=session.programme_year,
        class_size=session.group_size or 1,
        delivery_mode=_fixed_delivery_mode(rooms),
        teaching_weeks=list(session.teaching_weeks),
        week_pattern="CUSTOM",
        staff_ids=list(session.staff_ids),
        duration_hrs=session.duration_hours,
        is_common_module=False,
        staff_names=list(session.staff_names),
        remarks="Fixed session from structured lab workbook",
        source_file=session.source_file,
        group_ids=group_ids,
        source_sheet=session.source_sheet,
        source_row=session.source_row,
        is_fixed_requirement=True,
        fixed_source=f"{session.source_file}:{session.source_sheet}:{session.source_row}",
    )


def create_fixed_assignments(
    fixed_sessions: list[FixedSession],
    rooms: list[Room],
) -> tuple[list[Assignment], list[dict[str, object]]]:
    """Create anchored assignments for all valid fixed sessions."""
    assignments: list[Assignment] = []
    issues: list[dict[str, object]] = []
    for session in fixed_sessions:
        room_group, room_issues = _resolve_fixed_rooms(session, rooms)
        issues.extend(room_issues)
        if room_issues or not room_group:
            continue
        course = _course_from_fixed_session(session, room_group)
        primary = room_group[0]
        additional = tuple(room_group[1:])
        for week in session.teaching_weeks:
            assignments.append(
                Assignment(
                    course=course,
                    room=primary,
                    timeslot=TimeSlot(session.day, session.start_time, week),
                    additional_rooms=additional,
                    selected_delivery_mode=course.delivery_mode,
                    is_fixed=True,
                    fixed_source=course.fixed_source,
                )
            )
    return assignments, issues


def validate_fixed_assignments(assignments: list[Assignment]) -> list[dict[str, object]]:
    """Detect fixed-to-fixed clashes and invalid fixed placements."""
    issues: list[dict[str, object]] = []
    accepted: list[Assignment] = []
    for assignment in assignments:
        violations = check_hard_constraints(assignment, accepted)
        if violations:
            assignment.hard_violations = violations
            source = assignment.fixed_source or ""
            source_file, sheet, row = _split_fixed_source(source)
            issues.append(
                {
                    "severity": "critical",
                    "source": source_file,
                    "sheet": sheet,
                    "row": row,
                    "field": "fixed placement",
                    "problem": "; ".join(violations),
                    "recommendation": "Resolve the fixed-session source conflict before generation.",
                }
            )
        accepted.append(assignment)
    return issues


def _split_fixed_source(source: str) -> tuple[str, str, int | str]:
    """Split a fixed source marker into report fields."""
    parts = source.split(":")
    if len(parts) < 3:
        return source, "", ""
    try:
        row: int | str = int(parts[-1])
    except ValueError:
        row = parts[-1]
    return parts[0], parts[1], row


def export_fixed_assignment_issues(issues: list[dict[str, object]], output_path: Path) -> None:
    """Export fixed-assignment validation issues."""
    import pandas as pd

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(issues, columns=FIXED_ISSUE_COLUMNS).to_excel(output_path, sheet_name="Fixed Assignment Issues", index=False)
