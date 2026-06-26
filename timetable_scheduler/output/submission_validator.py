"""Create and validate the submission-ready Template 2 workbook."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from data.models import Assignment, Course, FixedSession, Room
from engine.demand_metrics import build_demand_metrics
from engine.fixed_reconciliation import normalise_programme_year
from output.exporter import export_schedule

REQUIRED_SUBMISSION_COLUMNS = [
    "Module",
    "Class Type",
    "Group",
    "Day",
    "Start",
    "End",
    "Class Size",
    "Room1",
    "Staff1",
    "Tri Week",
    "Activity Type",
    "Duration",
    "Location Hostkey",
]


@dataclass(slots=True)
class Template2ValidationResult:
    """Validation outcome for the saved submission-ready Template 2 workbook."""

    ready: bool
    summary: dict[str, object] = field(default_factory=dict)
    programme_rows: list[dict[str, object]] = field(default_factory=list)
    required_field_rows: list[dict[str, object]] = field(default_factory=list)
    fixed_accuracy_rows: list[dict[str, object]] = field(default_factory=list)
    source_reconciliation_rows: list[dict[str, object]] = field(default_factory=list)
    duplicate_rows: list[dict[str, object]] = field(default_factory=list)
    invalid_rows: list[dict[str, object]] = field(default_factory=list)


def _is_submission_assignment(assignment: Assignment) -> bool:
    """Return True for complete scheduled rows eligible for submission."""
    return assignment.room is not None and assignment.timeslot is not None and not assignment.hard_violations


def _has_required_submission_values(assignment: Assignment) -> bool:
    """Return True when required Template 2 values can be populated."""
    course = assignment.course
    return all(
        [
            course.module_code,
            course.activity,
            course.group_ids or course.prog_yr,
            course.class_size > 0,
            assignment.room is not None and assignment.room.room_id,
            course.staff_names or course.staff_ids,
            assignment.timeslot is not None,
            course.duration_hrs > 0,
        ]
    )


def submission_assignments(
    assignments: list[Assignment],
    complete_programmes: set[str] | None = None,
    rooms: list[Room] | None = None,
) -> list[Assignment]:
    """Return scheduled assignments only, excluding unresolved placeholders."""
    valid_room_ids = _valid_rooms(rooms or []) if rooms is not None else None
    rows: list[Assignment] = []
    for assignment in assignments:
        if not _is_submission_assignment(assignment):
            continue
        if not _has_required_submission_values(assignment):
            continue
        programme = normalise_programme_year(assignment.course.prog_yr)
        if complete_programmes is not None and programme not in complete_programmes:
            continue
        if valid_room_ids is not None and assignment.room is not None and assignment.room.room_id not in valid_room_ids:
            continue
        rows.append(assignment)
    return rows


def export_submission_ready_schedule(
    assignments: list[Assignment],
    output_path: Path,
    template2_path: Path,
    enable_remark_interpretation: bool = True,
    complete_programmes: set[str] | None = None,
    rooms: list[Room] | None = None,
) -> None:
    """Export a Template 2 workbook containing only complete scheduled rows."""
    export_schedule(
        submission_assignments(assignments, complete_programmes=complete_programmes, rooms=rooms),
        output_path,
        template2_path=template2_path,
        enable_remark_interpretation=enable_remark_interpretation,
    )


def _headers(workbook_path: Path) -> list[object]:
    """Return Timetable sheet headers."""
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if "Timetable" not in workbook.sheetnames:
            return []
        return [cell.value for cell in workbook["Timetable"][1]]
    finally:
        workbook.close()


def _row_dicts(workbook_path: Path) -> list[dict[str, object]]:
    """Return Timetable rows as dictionaries."""
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if "Timetable" not in workbook.sheetnames:
            return []
        sheet = workbook["Timetable"]
        headers = [cell.value for cell in sheet[1]]
        rows: list[dict[str, object]] = []
        for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(value not in (None, "") for value in row):
                continue
            values = {str(header): row[position] for position, header in enumerate(headers) if header is not None}
            values["_row"] = row_index
            rows.append(values)
        return rows
    finally:
        workbook.close()


def _duration_valid(row: dict[str, object]) -> bool:
    """Return True when Template 2 start/end/duration values agree."""
    try:
        start = str(row.get("Start") or "").zfill(4)
        end = str(row.get("End") or "").zfill(4)
        duration = float(row.get("Duration") or 0)
        start_minutes = int(start[:2]) * 60 + int(start[2:])
        end_minutes = int(end[:2]) * 60 + int(end[2:])
    except (TypeError, ValueError):
        return False
    return end_minutes > start_minutes and abs((end_minutes - start_minutes) / 60 - duration) < 0.01


def _valid_rooms(rooms: list[Room]) -> set[str]:
    """Return valid room IDs for submission validation."""
    return {room.room_id for room in rooms}


def _required_field_validation(rows: list[dict[str, object]], rooms: list[Room]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Validate required row fields and return field rows plus invalid rows."""
    valid_rooms = _valid_rooms(rooms)
    field_rows: list[dict[str, object]] = []
    invalid_rows: list[dict[str, object]] = []
    for row in rows:
        row_number = row["_row"]
        row_issues: list[str] = []
        for column in REQUIRED_SUBMISSION_COLUMNS:
            ok = row.get(column) not in (None, "")
            field_rows.append({"Row": row_number, "Field": column, "Status": "PASS" if ok else "FAIL", "Value": row.get(column)})
            if not ok:
                row_issues.append(f"Missing {column}")
        if not _duration_valid(row):
            row_issues.append("Duration does not match start/end")
        room = row.get("Room1")
        if room not in valid_rooms:
            row_issues.append(f"Room '{room}' is not in venue data")
        if row_issues:
            invalid_rows.append({"Row": row_number, "Module": row.get("Module"), "Issues": "; ".join(row_issues)})
    return field_rows, invalid_rows


def _duplicate_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return duplicate output occurrence rows."""
    keys = [
        (
            row.get("Module"),
            row.get("Class Type"),
            row.get("Group"),
            row.get("Day"),
            row.get("Start"),
            row.get("Tri Week"),
            row.get("Room1"),
        )
        for row in rows
    ]
    counts = Counter(keys)
    return [
        {"Module": key[0], "Class Type": key[1], "Group": key[2], "Day": key[3], "Start": key[4], "Tri Week": key[5], "Room1": key[6], "Count": count}
        for key, count in counts.items()
        if count > 1
    ]


def _programme_coverage(
    source_requirements: list[Course],
    assignments: list[Assignment],
    submission_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build programme-year schedule coverage rows."""
    required: dict[str, set[tuple[str, str, int]]] = defaultdict(set)
    scheduled: dict[str, set[tuple[str, str, int]]] = defaultdict(set)
    fixed_counts: Counter[str] = Counter()
    for course in source_requirements:
        programme = normalise_programme_year(course.prog_yr)
        weeks = course.teaching_weeks
        for week in weeks:
            required[programme].add((course.module_code, course.activity, week))
    for assignment in assignments:
        programme = normalise_programme_year(assignment.course.prog_yr)
        if assignment.is_fixed:
            fixed_counts[programme] += 1
        if _is_submission_assignment(assignment) and assignment.timeslot is not None:
            scheduled[programme].add((assignment.course.module_code, assignment.course.activity, assignment.timeslot.week))
    submission_count: Counter[str] = Counter()
    for row in submission_rows:
        programme = normalise_programme_year(str(row.get("Programme/Year") or row.get("Group") or ""))
        submission_count[programme] += 1

    rows: list[dict[str, object]] = []
    for programme in sorted(required):
        required_count = len(required[programme])
        scheduled_count = len(scheduled.get(programme, set()))
        complete = required_count > 0 and required_count == scheduled_count
        rows.append(
            {
                "Normalised Programme/Year": programme,
                "Required Assignments": required_count,
                "Required Teaching Occurrences": required_count,
                "Fixed Assignments": fixed_counts[programme],
                "Scheduled Assignments": scheduled_count,
                "Unscheduled Assignments": max(required_count - scheduled_count, 0),
                "Submission Rows": submission_count[programme],
                "Completion Percentage": (scheduled_count / required_count * 100) if required_count else 0,
                "Complete Schedule Status": "PASS" if complete else "FAIL",
                "Included In Submission": "Yes" if submission_count[programme] else "No",
                "Exclusion Reason": "" if submission_count[programme] else "No complete scheduled rows in submission workbook",
            }
        )
    return rows


def _fixed_accuracy(assignments: list[Assignment]) -> list[dict[str, object]]:
    """Return fixed placement accuracy rows from the exported assignments."""
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        if not assignment.is_fixed:
            continue
        rows.append(
            {
                "Fixed Source": assignment.fixed_source,
                "Module": assignment.course.module_code,
                "Week": assignment.timeslot.week if assignment.timeslot else "",
                "Day": assignment.timeslot.day if assignment.timeslot else "",
                "Start": assignment.timeslot.start_time if assignment.timeslot else "",
                "Duration": assignment.course.duration_hrs,
                "Room": assignment.room.room_id if assignment.room else "",
                "Status": "PASS" if _is_submission_assignment(assignment) else "FAIL",
            }
        )
    return rows


def validate_template2_submission(
    workbook_path: Path,
    source_requirements: list[Course],
    fixed_sessions: list[FixedSession],
    assignments: list[Assignment],
    rooms: list[Room],
    template2_path: Path,
) -> Template2ValidationResult:
    """Validate the actual saved submission-ready Template 2 workbook."""
    headers = _headers(workbook_path)
    template_headers = _headers(template2_path)
    rows = _row_dicts(workbook_path)
    field_rows, invalid_rows = _required_field_validation(rows, rooms)
    duplicates = _duplicate_rows(rows)
    programme_rows = _programme_coverage(source_requirements, assignments, rows)
    demand = build_demand_metrics(source_requirements, assignments, input_course_records=len(source_requirements))
    complete_programmes = sum(1 for row in programme_rows if row["Complete Schedule Status"] == "PASS")
    submission_ready_programmes = sum(
        1 for row in programme_rows if row["Complete Schedule Status"] == "PASS" and row["Included In Submission"] == "Yes"
    )
    missing_columns = [column for column in REQUIRED_SUBMISSION_COLUMNS if column not in headers]
    extra_columns = [column for column in headers if column not in template_headers]
    ready = not missing_columns and not extra_columns and not invalid_rows and not duplicates and submission_ready_programmes >= 20
    summary = {
        "fixed source rows": len(fixed_sessions),
        "valid fixed assignments": sum(1 for item in assignments if item.is_fixed),
        "fixed teaching occurrences": sum(1 for item in assignments if item.is_fixed and item.timeslot is not None),
        "fixed assignments anchored": sum(1 for item in assignments if item.is_fixed and _is_submission_assignment(item)),
        "fixed-source conflicts": sum(1 for item in assignments if item.is_fixed and item.hard_violations),
        "non-fixed assignments": sum(1 for item in assignments if not item.is_fixed),
        "total required assignments": len(source_requirements),
        "total required teaching occurrences": demand.required_teaching_occurrences,
        "total scheduled occurrences": demand.scheduled_teaching_occurrences,
        "total unscheduled occurrences": demand.unscheduled_teaching_occurrences,
        "Template 2 output rows": len(rows),
        "rows with missing required fields": sum(1 for row in invalid_rows if "Missing" in row["Issues"]),
        "rows with mapping errors": len(invalid_rows),
        "distinct programme-year schedules": len(programme_rows),
        "complete programme-year schedules": complete_programmes,
        "submission-ready programme-year schedules": submission_ready_programmes,
        "Template 2 readiness status": "PASS" if ready else "FAIL",
        "missing columns": ", ".join(missing_columns),
        "extra accidental columns": ", ".join(str(column) for column in extra_columns),
    }
    reconciliation = [
        {
            "Row": row.get("_row"),
            "Module": row.get("Module"),
            "Class Type": row.get("Class Type"),
            "Group": row.get("Group"),
            "Tri Week": row.get("Tri Week"),
            "Status": "Mapped to scheduled assignment",
        }
        for row in rows
    ]
    return Template2ValidationResult(
        ready=ready,
        summary=summary,
        programme_rows=programme_rows,
        required_field_rows=field_rows,
        fixed_accuracy_rows=_fixed_accuracy(assignments),
        source_reconciliation_rows=reconciliation,
        duplicate_rows=duplicates,
        invalid_rows=invalid_rows,
    )


def export_template2_validation_report(result: Template2ValidationResult, output_path: Path) -> None:
    """Export the Template 2 submission validation workbook."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame([{"Metric": key, "Value": value} for key, value in result.summary.items()]).to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )
        pd.DataFrame(result.programme_rows).to_excel(writer, sheet_name="Programme Schedule Coverage", index=False)
        pd.DataFrame(result.fixed_accuracy_rows).to_excel(writer, sheet_name="Fixed Session Accuracy", index=False)
        pd.DataFrame(result.required_field_rows).to_excel(writer, sheet_name="Required Field Validation", index=False)
        pd.DataFrame(result.source_reconciliation_rows).to_excel(writer, sheet_name="Source-to-Output Reconciliation", index=False)
        pd.DataFrame(result.duplicate_rows).to_excel(writer, sheet_name="Duplicate Check", index=False)
        pd.DataFrame(result.invalid_rows).to_excel(writer, sheet_name="Invalid Rows", index=False)
        pd.DataFrame(
            [
                {
                    "Check": "Submission readiness",
                    "Status": "PASS" if result.ready else "FAIL",
                    "Notes": "Requires complete rows, valid mappings, no duplicates, and at least 20 complete programme-year schedules.",
                }
            ]
        ).to_excel(writer, sheet_name="Submission Readiness", index=False)
