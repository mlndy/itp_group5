"""Export timetable and violation reports to Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import ACTIVITY_TYPE_CODES, DAY_ABBREVIATIONS
from data.models import Assignment
from engine.constraint_checker import annotate_schedule_violations, assignment_end_hour, hour_to_time, time_to_hour


def _activity_type_code(activity: str) -> str:
    """Map activity text to Template 2 activity code."""
    activity_lower = activity.lower()
    for keyword, code in ACTIVITY_TYPE_CODES.items():
        if keyword in activity_lower:
            return code
    return activity[:3].upper() if activity else "ACT"


def _format_template_time(time_text: str | None) -> str | None:
    """Convert HH:MM to Template 2 HHMM text."""
    if not time_text:
        return None
    return time_text.replace(":", "")


def _staff_value(assignment: Assignment, index: int) -> str | None:
    """Return staff name when available, otherwise staff ID."""
    if index < len(assignment.course.staff_names):
        return assignment.course.staff_names[index]
    if index < len(assignment.course.staff_ids):
        return assignment.course.staff_ids[index]
    return None


def assignment_to_row(assignment: Assignment) -> dict[str, object]:
    """Convert one assignment to a Template 2-compatible row."""
    course = assignment.course
    timeslot = assignment.timeslot
    room = assignment.room
    end_time = None
    if timeslot is not None:
        end_time = hour_to_time(time_to_hour(timeslot.start_time) + course.duration_hrs)

    return {
        "Module": course.module_code,
        "Class Type": course.activity,
        "Template": 1,
        "Group": " / ".join(course.group_ids or [course.prog_yr]),
        "Day": DAY_ABBREVIATIONS.get(timeslot.day, timeslot.day) if timeslot else None,
        "Start": _format_template_time(timeslot.start_time) if timeslot else None,
        "End": _format_template_time(end_time) if end_time else None,
        "Class Size": course.class_size,
        "Sector": "PUNGGOL",
        "RoomGrouping": None,
        "Room1": room.room_id if room else None,
        "Room2": None,
        "StaffGrouping": None,
        "Staff1": _staff_value(assignment, 0),
        "Staff2": _staff_value(assignment, 1),
        "Tri Week": str(timeslot.week) if timeslot else None,
        "Recording Mode": "A0",
        "Remark": course.remarks,
        "FMTS Tri Start Week": 1,
        "Activity Hostkey": f"{course.module_code}-2510-ENG-UGRD-PU-{_activity_type_code(course.activity)}/{course.prog_yr}",
        "SIS Module Code": f"{course.module_code}-2510-ENG-UGRD-PU",
        "Term": 2510,
        "Activity Type": _activity_type_code(course.activity),
        "Duration": course.duration_hrs,
        "Staff Suitability ID": "#N/A",
        "SIS Staff ID": course.staff_ids[0] if len(course.staff_ids) >= 1 else "#N/A",
        "SIS Staff ID.1": course.staff_ids[1] if len(course.staff_ids) >= 2 else "#N/A",
        "Zone Hostkey": "PUNGGOL",
        "Location Suitability ID": "#N/A",
        "Location Hostkey": room.room_id if room else "#N/A",
        "Location Hostkey.1": "#N/A",
        "Programme/Year": course.prog_yr,
        "Delivery Mode": course.delivery_mode,
        "Status": assignment.status,
    }


def assignments_to_dataframe(assignments: list[Assignment]) -> pd.DataFrame:
    """Convert assignments to a timetable DataFrame."""
    annotate_schedule_violations(assignments)
    rows = [assignment_to_row(assignment) for assignment in assignments]
    return pd.DataFrame(rows)


def violations_to_dataframe(assignments: list[Assignment], violation_type: str) -> pd.DataFrame:
    """Convert hard or soft violations to a DataFrame."""
    annotate_schedule_violations(assignments)
    columns = [
        "Type",
        "Module",
        "Activity",
        "Programme/Year",
        "Week",
        "Day",
        "Start",
        "Room",
        "Violation",
    ]
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        violations = assignment.hard_violations if violation_type == "hard" else assignment.soft_violations
        for violation in violations:
            rows.append(
                {
                    "Type": violation_type.upper(),
                    "Module": assignment.course.module_code,
                    "Activity": assignment.course.activity,
                    "Programme/Year": assignment.course.prog_yr,
                    "Week": assignment.timeslot.week if assignment.timeslot else None,
                    "Day": assignment.timeslot.day if assignment.timeslot else None,
                    "Start": assignment.timeslot.start_time if assignment.timeslot else None,
                    "Room": assignment.room.room_id if assignment.room else None,
                    "Violation": violation,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def summary_to_dataframe(assignments: list[Assignment]) -> pd.DataFrame:
    """Create summary metrics for stakeholder reporting."""
    annotate_schedule_violations(assignments)
    total = len(assignments)
    hard = sum(len(item.hard_violations) for item in assignments)
    soft = sum(len(item.soft_violations) for item in assignments)
    scheduled = sum(1 for item in assignments if item.room is not None and item.timeslot is not None)
    return pd.DataFrame(
        [
            {"Metric": "Assignments", "Value": total},
            {"Metric": "Scheduled assignments", "Value": scheduled},
            {"Metric": "Unscheduled assignments", "Value": total - scheduled},
            {"Metric": "Hard violations", "Value": hard},
            {"Metric": "Soft violations", "Value": soft},
            {"Metric": "Feasibility rate", "Value": f"{scheduled / total:.1%}" if total else "0.0%"},
        ]
    )


def _autosize_and_style(path: Path) -> None:
    """Apply simple readable styling to an exported workbook."""
    workbook = load_workbook(path)
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for column_cells in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            width = min(max(max_length + 2, 10), 38)
            sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    workbook.save(path)


def export_schedule(assignments: list[Assignment], output_path: str | Path) -> None:
    """Export timetable, summary, and violation sheets."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timetable_df = assignments_to_dataframe(assignments)
    hard_df = violations_to_dataframe(assignments, "hard")
    soft_df = violations_to_dataframe(assignments, "soft")
    summary_df = summary_to_dataframe(assignments)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        timetable_df.to_excel(writer, sheet_name="Timetable", index=False)
        hard_df.to_excel(writer, sheet_name="Hard Violations", index=False)
        soft_df.to_excel(writer, sheet_name="Soft Violations", index=False)
    _autosize_and_style(output_path)


def export_violations(assignments: list[Assignment], output_path: str | Path) -> None:
    """Export only hard and soft violation reports."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        violations_to_dataframe(assignments, "hard").to_excel(writer, sheet_name="Hard Violations", index=False)
        violations_to_dataframe(assignments, "soft").to_excel(writer, sheet_name="Soft Violations", index=False)
    _autosize_and_style(output_path)
