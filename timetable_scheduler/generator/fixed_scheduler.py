"""Convert validated fixed sessions into anchored timetable assignments."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from data.models import Assignment, Course, FixedSession, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints, fixed_window_exception_violations
from engine.location_mapping import classify_location, room_from_location_evidence
from engine.remarks_interpreter import assignment_room_ids

FIXED_ISSUE_COLUMNS = ["severity", "source", "sheet", "row", "field", "problem", "recommendation"]
AUTHORITATIVE_FIXED_WINDOW_EXCEPTION = "AUTHORITATIVE_FIXED_WINDOW_EXCEPTION"
AUTHORITATIVE_FIXED_LUNCH_SPAN = "AUTHORITATIVE_FIXED_LUNCH_SPAN"
AUTHORITATIVE_FIXED_AFTER_1800 = "AUTHORITATIVE_FIXED_AFTER_1800"


def normalise_module_code(module_code: str) -> str:
    """Return the leading SIS-style module code where it is present."""
    text = str(module_code or "").strip().upper()
    match = re.match(r"([A-Z]{2,4}\d{4}[A-Z]?)", text)
    return match.group(1) if match else text


def normalise_staff_name(value: str) -> str:
    """Return a conservative staff identity key for fixed-session matching."""
    text = re.sub(r"\s+", " ", str(value or "").upper().replace("\xa0", " ")).strip()
    text = re.sub(r"\s+\.$", "", text)
    return text


def _normalise_programme_year(value: str) -> str:
    """Return a compact programme/year key without changing source text."""
    text = re.sub(r"\s+", " ", str(value or "").upper().replace("YEAR", "Y").replace("YR", "Y")).strip()
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return re.sub(r"\bY\s*([0-9])\b", r"Y\1", text)


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


def _find_room_by_code(code: str, rooms: list[Room]) -> Room | None:
    """Find an exact venue code, allowing official room-name suffixes."""
    key = code.casefold()
    for room in rooms:
        room_key = room.room_id.casefold()
        if room_key == key or room_key.startswith(f"{key}-"):
            return room
    return None


def _capacity_unverified_room(code: str) -> Room:
    """Return an exact fixed-location token without inventing usable capacity."""
    return Room(code, 0, "physical", "Recognised Venue (capacity unavailable)")


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
    if "graphics" in text:
        return "Laboratory"
    if "discovery hub" in text:
        return "Laboratory"
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
                room = lookup.get(code.casefold()) or _find_room_by_code(code, rooms)
                if room is None:
                    if code.upper().startswith("W3-"):
                        issues.append(
                            _issue(
                                session,
                                severity="warning",
                                field="location",
                                problem=f"Exact W3 fixed room '{code}' is retained with capacity unverified.",
                                recommendation="Retain the official fixed location token and confirm host-key/capacity before submission-ready export.",
                            )
                        )
                        resolved.append(_capacity_unverified_room(code))
                        continue
                    evidence = classify_location(code, rooms)
                    evidence_room = room_from_location_evidence(evidence)
                    if evidence_room is None:
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
                        issues.append(
                            _issue(
                                session,
                                severity="warning",
                                field="location",
                                problem=f"{code} is a recognised venue but capacity is not fully verified.",
                                recommendation="Keep fixed placement visible and confirm capacity with supervisor.",
                            )
                        )
                        resolved.append(evidence_room)
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
        evidence = classify_location(location, rooms)
        evidence_room = room_from_location_evidence(evidence)
        if evidence_room is not None:
            issues.append(
                _issue(
                    session,
                    severity="warning",
                    field="location",
                    problem=f"Location '{location}' is recognised as {evidence.treatment}.",
                    recommendation="Keep fixed placement visible and confirm non-standard venue details before final submission.",
                )
            )
            resolved.append(evidence_room)
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


def _fixed_source(session: FixedSession) -> str:
    """Return a traceable source reference for one fixed row."""
    return f"{session.source_file}:{session.source_sheet}:{session.source_row}"


def _shared_identity(session: FixedSession, room_group: tuple[Room, ...]) -> tuple[object, ...]:
    """Return the conservative identity used to group shared fixed sessions."""
    return (
        normalise_module_code(session.module_code),
        _normalise_programme_year(session.programme_year),
        session.day,
        session.start_time,
        session.duration_hours,
        tuple(session.teaching_weeks),
        tuple(room.room_id for room in room_group),
        tuple(normalise_staff_name(staff) for staff in session.staff_names),
    )


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


def _group_ids_for_session(session: FixedSession) -> list[str]:
    """Return student-group IDs represented by one fixed row."""
    groups = [
        part.strip()
        for part in re.split(r"[,/+&]+", session.group_id)
        if part and part.strip()
    ]
    if not groups or any(group.casefold() in {"all", "p1 to p3", "p1 to p4"} for group in groups):
        return [session.programme_year]
    return [f"{session.programme_year}/{group}" for group in groups]


def _unique_ordered(values: list[str]) -> list[str]:
    """Return unique non-empty values while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _course_from_fixed_sessions(sessions: list[FixedSession], rooms: tuple[Room, ...]) -> Course:
    """Create one scheduler Course wrapper for a fixed row or shared row group."""
    base = sessions[0]
    group_ids = _unique_ordered([group for session in sessions for group in _group_ids_for_session(session)])
    staff_names = _unique_ordered([staff for session in sessions for staff in session.staff_names])
    staff_ids = _unique_ordered([normalise_staff_name(staff) for staff in staff_names])
    source_refs = [_fixed_source(session) for session in sessions]
    source_files = _unique_ordered([session.source_file for session in sessions])
    source_sheets = _unique_ordered([session.source_sheet for session in sessions])
    return Course(
        module_code=normalise_module_code(base.module_code),
        activity=_fixed_activity(base, rooms),
        prog_yr=" / ".join(_unique_ordered([session.programme_year for session in sessions])),
        class_size=sum(session.group_size or 1 for session in sessions),
        delivery_mode=_fixed_delivery_mode(rooms),
        teaching_weeks=list(base.teaching_weeks),
        week_pattern="CUSTOM",
        staff_ids=staff_ids,
        duration_hrs=base.duration_hours,
        is_common_module=False,
        staff_names=staff_names,
        remarks="Structured fixed shared session" if len(sessions) > 1 else "Structured fixed session",
        source_file="; ".join(source_files),
        group_ids=group_ids,
        source_sheet="; ".join(source_sheets),
        source_row=base.source_row if len(sessions) == 1 else None,
        is_fixed_requirement=True,
        fixed_source=" | ".join(source_refs),
    )


def create_fixed_assignments(
    fixed_sessions: list[FixedSession],
    rooms: list[Room],
) -> tuple[list[Assignment], list[dict[str, object]]]:
    """Create anchored assignments for all valid fixed sessions."""
    assignments: list[Assignment] = []
    issues: list[dict[str, object]] = []
    grouped: dict[tuple[object, ...], tuple[list[FixedSession], tuple[Room, ...]]] = {}
    for session in fixed_sessions:
        room_group, room_issues = _resolve_fixed_rooms(session, rooms)
        issues.extend(room_issues)
        if any(issue.get("severity") == "critical" for issue in room_issues) or not room_group:
            continue
        key = _shared_identity(session, room_group)
        if key not in grouped:
            grouped[key] = ([], room_group)
        grouped[key][0].append(session)

    for sessions, room_group in grouped.values():
        base = sessions[0]
        course = _course_from_fixed_sessions(sessions, room_group)
        primary = room_group[0]
        additional = tuple(room_group[1:])
        for week in base.teaching_weeks:
            assignments.append(
                Assignment(
                    course=course,
                    room=primary,
                    timeslot=TimeSlot(base.day, base.start_time, week),
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
        violations = check_hard_constraints(assignment, accepted, enable_remark_interpretation=False)
        exceptions = _authoritative_fixed_exceptions(
            fixed_window_exception_violations(assignment, accepted)
        )
        assignment.hard_violations = violations
        if exceptions:
            source = assignment.fixed_source or ""
            source_file, sheet, row = _split_fixed_source(source)
            issues.append(
                {
                    "severity": "warning",
                    "source": source_file,
                    "source refs": source,
                    "related source refs": "",
                    "conflict group id": "",
                    "sheet": sheet,
                    "row": row,
                    "field": "fixed placement",
                    "problem": "; ".join(f"{code}: {violation}" for code, violation in exceptions),
                    "recommendation": "Accepted as an authoritative fixed-session placement exception; verify source approval is retained.",
                }
            )
        if violations:
            source = assignment.fixed_source or ""
            related = _related_conflict_sources(assignment, accepted)
            source_file, sheet, row = _split_fixed_source(source)
            issues.append(
                {
                    "severity": "critical",
                    "source": source_file,
                    "source refs": source,
                    "related source refs": " | ".join(related),
                    "conflict group id": _conflict_group_id((source, *related), violations),
                    "sheet": sheet,
                    "row": row,
                    "field": "fixed placement",
                    "problem": "; ".join(violations),
                    "recommendation": "Resolve the fixed-session source conflict before generation.",
                }
            )
        accepted.append(assignment)
    return issues


def _authoritative_fixed_exceptions(violations: list[str]) -> list[tuple[str, str]]:
    """Return auditable source-authoritative window exceptions."""
    exceptions: list[tuple[str, str]] = []
    for violation in violations:
        code = _authoritative_fixed_exception_code(violation)
        if code:
            exceptions.append((code, violation))
    return exceptions


def _authoritative_fixed_exception_code(violation: str) -> str:
    """Return the audit code for a generic rule that official fixed sessions may override."""
    text = violation.casefold()
    if "no free lunch block" in text:
        return AUTHORITATIVE_FIXED_LUNCH_SPAN
    if "class ends after 18:00" in text:
        return AUTHORITATIVE_FIXED_AFTER_1800
    if "class starts before 09:00" in text or "blocked time used" in text:
        return AUTHORITATIVE_FIXED_WINDOW_EXCEPTION
    return ""


def _related_conflict_sources(assignment: Assignment, accepted: list[Assignment]) -> list[str]:
    """Return accepted fixed sources that clash with this assignment."""
    related: list[str] = []
    for existing in accepted:
        violations = check_hard_constraints(assignment, [existing], enable_remark_interpretation=False)
        if any("clash" in violation.casefold() for violation in violations):
            if existing.fixed_source:
                related.append(existing.fixed_source)
    return related


def _conflict_group_id(sources: tuple[str, ...], violations: list[str]) -> str:
    """Return a stable conflict-group label for unresolved fixed conflicts."""
    import hashlib

    values = [source for source in sources if source]
    if len(values) < 2:
        return ""
    raw = "|".join(sorted(values)) + "|" + "; ".join(sorted(violations))
    return "CFG-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10].upper()


def _split_fixed_source(source: str) -> tuple[str, str, int | str]:
    """Split a fixed source marker into report fields."""
    primary_source = source.split("|", 1)[0].strip()
    parts = primary_source.split(":")
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
