"""Fixed-session integrity evidence for final Engineering validation."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from data.models import Assignment, FixedSession
from engine.remarks_interpreter import assignment_room_ids


def export_fixed_session_integrity_report(
    fixed_sessions: list[FixedSession],
    assignments: list[Assignment],
    output_path: Path,
    quarantined_requirements: list[object] | None = None,
) -> dict[str, object]:
    """Export fixed-session source-to-schedule integrity checks."""
    detail_rows = fixed_session_integrity_rows(fixed_sessions, assignments, quarantined_requirements)
    issue_rows = [row for row in detail_rows if row["Status"] == "FAIL"]
    quarantined_rows = [row for row in detail_rows if row["Status"] == "QUARANTINED"]
    fixed_hard = sum(1 for item in _unique_fixed_assignments(assignments) if item.hard_violations)
    represented_sources = {
        row["Fixed Source"]
        for row in detail_rows
        if row["Source Attached"] == "PASS"
    }
    summary = {
        "fixed source rows": len(fixed_sessions),
        "expected fixed teaching occurrences": len(detail_rows),
        "represented fixed source rows": len(represented_sources),
        "anchored fixed teaching occurrences": sum(1 for row in detail_rows if row["Status"] == "PASS"),
        "quarantined fixed teaching occurrences": len(quarantined_rows),
        "missing fixed teaching occurrences": sum(1 for row in detail_rows if row["Placement Present"] == "FAIL"),
        "placement mismatches": len(issue_rows),
        "scheduled hard violations on fixed assignments": fixed_hard,
        "fixed-session integrity status": "PASS" if not issue_rows and fixed_hard == 0 else "FAIL",
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame([{"Metric": key, "Value": value} for key, value in summary.items()]).to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )
        pd.DataFrame(detail_rows).to_excel(writer, sheet_name="Fixed Source Integrity", index=False)
        pd.DataFrame(issue_rows).to_excel(writer, sheet_name="Integrity Issues", index=False)
        pd.DataFrame(quarantined_rows).to_excel(writer, sheet_name="Quarantined Fixed Sources", index=False)
    return summary


def fixed_session_integrity_rows(
    fixed_sessions: list[FixedSession],
    assignments: list[Assignment],
    quarantined_requirements: list[object] | None = None,
) -> list[dict[str, object]]:
    """Return one integrity row for each fixed source teaching week."""
    assignment_index = _fixed_assignment_index(assignments)
    quarantined = _quarantined_source_refs(quarantined_requirements or [])
    rows: list[dict[str, object]] = []
    for session in fixed_sessions:
        source = _fixed_source(session)
        expected_codes = _exact_location_codes(session.locations)
        matches = assignment_index.get(source, [])
        for week in session.teaching_weeks:
            assignment = next((item for item in matches if item.timeslot and item.timeslot.week == week), None)
            rows.append(_integrity_row(session, source, week, expected_codes, assignment, source in quarantined))
    return rows


def _integrity_row(
    session: FixedSession,
    source: str,
    week: int,
    expected_codes: tuple[str, ...],
    assignment: Assignment | None,
    is_quarantined: bool,
) -> dict[str, object]:
    """Return one source-week integrity row."""
    if assignment is None or assignment.timeslot is None or assignment.room is None:
        status = "QUARANTINED" if is_quarantined else "FAIL"
        issue = (
            "Fixed source-week was quarantined by input readiness and intentionally not scheduled."
            if is_quarantined
            else "Fixed source-week was not represented by a scheduled fixed assignment."
        )
        return {
            **_base_row(session, source, week),
            "Scheduled Day": "",
            "Scheduled Start": "",
            "Scheduled Duration": "",
            "Scheduled Rooms": "",
            "Scheduled Staff": "",
            "Source Attached": "QUARANTINED" if is_quarantined else "FAIL",
            "Placement Present": "QUARANTINED" if is_quarantined else "FAIL",
            "Day Match": "QUARANTINED" if is_quarantined else "FAIL",
            "Start Match": "QUARANTINED" if is_quarantined else "FAIL",
            "Duration Match": "QUARANTINED" if is_quarantined else "FAIL",
            "Week Match": "QUARANTINED" if is_quarantined else "FAIL",
            "Location Match": "QUARANTINED" if is_quarantined else "FAIL",
            "Staff Evidence": "QUARANTINED" if is_quarantined else "FAIL",
            "Hard Violations": "",
            "Status": status,
            "Issue": issue,
        }

    scheduled_rooms = assignment_room_ids(assignment)
    checks = {
        "Source Attached": "PASS" if source in _assignment_source_refs(assignment) else "FAIL",
        "Placement Present": "PASS",
        "Day Match": "PASS" if assignment.timeslot.day == session.day else "FAIL",
        "Start Match": "PASS" if assignment.timeslot.start_time == session.start_time else "FAIL",
        "Duration Match": "PASS" if float(assignment.course.duration_hrs) == float(session.duration_hours) else "FAIL",
        "Week Match": "PASS" if assignment.timeslot.week == week else "FAIL",
        "Location Match": _location_status(expected_codes, scheduled_rooms),
        "Staff Evidence": _staff_status(session, assignment),
    }
    hard_text = "; ".join(assignment.hard_violations)
    issue_parts = [name for name, status in checks.items() if status == "FAIL"]
    if hard_text:
        issue_parts.append("Hard Violations")
    status = "PASS" if not issue_parts else "FAIL"
    return {
        **_base_row(session, source, week),
        "Scheduled Day": assignment.timeslot.day,
        "Scheduled Start": assignment.timeslot.start_time,
        "Scheduled Duration": assignment.course.duration_hrs,
        "Scheduled Rooms": scheduled_rooms,
        "Scheduled Staff": "; ".join(assignment.course.staff_names or assignment.course.staff_ids),
        **checks,
        "Hard Violations": hard_text,
        "Status": status,
        "Issue": "; ".join(issue_parts),
    }


def _base_row(session: FixedSession, source: str, week: int) -> dict[str, object]:
    """Return source-side evidence columns for one fixed row."""
    return {
        "Fixed Source": source,
        "Programme/Year": session.programme_year,
        "Module Code": session.module_code,
        "Group": session.group_id,
        "Expected Week": week,
        "Expected Day": session.day,
        "Expected Start": session.start_time,
        "Expected Duration": session.duration_hours,
        "Expected Locations": "; ".join(session.locations),
        "Expected Staff": "; ".join(session.staff_names or session.staff_ids),
    }


def _fixed_assignment_index(assignments: list[Assignment]) -> dict[str, list[Assignment]]:
    """Return fixed assignments keyed by each attached fixed source row."""
    index: dict[str, list[Assignment]] = {}
    for assignment in assignments:
        if not assignment.is_fixed:
            continue
        for source in _assignment_source_refs(assignment):
            index.setdefault(source, []).append(assignment)
    return index


def _assignment_source_refs(assignment: Assignment) -> tuple[str, ...]:
    """Return fixed source refs represented by one assignment."""
    return tuple(part.strip() for part in str(assignment.fixed_source or "").split("|") if part.strip())


def _fixed_source(session: FixedSession) -> str:
    """Return the fixed source-row reference used by anchored assignments."""
    return f"{session.source_file}:{session.source_sheet}:{session.source_row}"


def _exact_location_codes(locations: tuple[str, ...]) -> tuple[str, ...]:
    """Return explicit venue codes that must remain literal in output."""
    codes: list[str] = []
    for location in locations:
        codes.extend(re.findall(r"\b[A-Z]\d-[0-9A-Z]{2}-[0-9A-Z]{2}(?:-[A-Z0-9]+)?\b", str(location).upper()))
    return tuple(codes)


def _location_status(expected_codes: tuple[str, ...], scheduled_rooms: str) -> str:
    """Return PASS when exact source venue codes or resolved locations are present."""
    if not scheduled_rooms:
        return "FAIL"
    if not expected_codes:
        return "PASS"
    scheduled = scheduled_rooms.upper()
    return "PASS" if all(code in scheduled for code in expected_codes) else "FAIL"


def _staff_status(session: FixedSession, assignment: Assignment) -> str:
    """Return PASS when fixed staff evidence remains attached to the assignment."""
    expected = {_normalise_staff(value) for value in (*session.staff_names, *session.staff_ids) if value}
    scheduled = {_normalise_staff(value) for value in (*assignment.course.staff_names, *assignment.course.staff_ids) if value}
    if not expected:
        return "PASS" if scheduled else "FAIL"
    return "PASS" if expected & scheduled else "FAIL"


def _normalise_staff(value: object) -> str:
    """Return a conservative staff comparison key."""
    return re.sub(r"\s+", " ", str(value or "").upper()).strip()


def _unique_fixed_assignments(assignments: list[Assignment]) -> list[Assignment]:
    """Return fixed assignments once by source, week and placement."""
    seen: set[tuple[object, ...]] = set()
    unique: list[Assignment] = []
    for assignment in assignments:
        if not assignment.is_fixed:
            continue
        key = (
            assignment.fixed_source,
            assignment.timeslot.week if assignment.timeslot else None,
            assignment.timeslot.day if assignment.timeslot else None,
            assignment.timeslot.start_time if assignment.timeslot else None,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(assignment)
    return unique


def _quarantined_source_refs(quarantined_requirements: list[object]) -> set[str]:
    """Return source refs intentionally excluded before scheduling."""
    refs: set[str] = set()
    for item in quarantined_requirements:
        ref = getattr(item, "requirement_id", "")
        if ref:
            refs.add(str(ref))
    return refs
