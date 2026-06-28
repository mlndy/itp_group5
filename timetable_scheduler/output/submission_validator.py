"""Create and validate the submission-ready Template 2 workbook."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re

import pandas as pd
from openpyxl import load_workbook

from data.models import Assignment, Course, FixedSession, Room
from engine.demand_metrics import build_demand_metrics
from engine.fixed_reconciliation import normalise_programme_year
from output.exporter import assignment_to_row, export_schedule

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
REQUIRED_MIN_PROGRAMME_YEARS = 20
UNKNOWN_YEAR_MARKERS = {"", "ALL YEARS", "ALL YEAR", "COMMON", "MIXED", "TBC", "TBD", "N/A", "NA"}


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
    missing_programme_year_rows: list[dict[str, object]] = field(default_factory=list)


def normalise_template2_year(value: object) -> str:
    """Return canonical Y<number> text, or blank for unknown/mixed years."""
    text = _clean_text(value)
    if text in UNKNOWN_YEAR_MARKERS:
        return ""
    if re.search(r"(?:YR|YEAR|Y)?\s*[1-9]\s*/\s*[1-9]", text):
        return ""
    if re.fullmatch(r"[1-9]", text):
        return f"Y{text}"
    match = re.search(r"\b(?:YEAR|YR|Y)\s*([1-9])\b", text)
    return f"Y{match.group(1)}" if match else ""


def normalise_template2_programme_year(value: object, fallback_programme: object = "") -> str:
    """Return <PROGRAMME>/Y<number>, or blank when the year is unknown."""
    text = _clean_text(value)
    slash_digit = re.fullmatch(r"(.+)/\s*([1-9])", text)
    if slash_digit:
        programme = _clean_programme(slash_digit.group(1))
        return f"{programme}/Y{slash_digit.group(2)}" if programme else ""
    year = normalise_template2_year(text)
    if not year:
        return ""
    programme = _programme_before_year(text) or _clean_programme(fallback_programme)
    return f"{programme}/{year}" if programme else ""


def saved_row_programme_year(row: dict[str, object]) -> str:
    """Return canonical programme-year from one saved Template 2 row."""
    for field in ("Programme/Year", "Group", "Activity Hostkey"):
        programme_year = normalise_template2_programme_year(row.get(field))
        if programme_year:
            return programme_year
    return ""


def _clean_text(value: object) -> str:
    """Return normalised uppercase text for conservative Template 2 parsing."""
    return re.sub(r"\s+", " ", str(value or "").strip().upper())


def _clean_programme(value: object) -> str:
    """Return a compact programme code without guessing a missing year."""
    text = _clean_text(value)
    text = re.sub(r"\b(?:YEAR|YR|Y)\s*[1-9]\b", "", text)
    text = text.strip(" /-_")
    if "/" in text:
        parts = [part.strip(" /-_") for part in text.split("/") if part.strip(" /-_")]
        for part in reversed(parts):
            if not normalise_template2_year(part):
                text = part
                break
    matches = re.findall(r"[A-Z][A-Z0-9]*(?:\s*\+\s*[A-Z][A-Z0-9]*)*", text)
    return matches[-1].replace(" ", "") if matches else ""


def _programme_before_year(value: object) -> str:
    """Return the programme text immediately before an explicit year token."""
    text = _clean_text(value)
    match = re.search(r"\b(?:YEAR|YR|Y)\s*[1-9]\b", text)
    if not match:
        return ""
    return _clean_programme(text[: match.start()])


def export_all_valid_scheduled_schedule(
    assignments: list[Assignment],
    output_path: Path,
    template2_path: Path,
    enable_remark_interpretation: bool = True,
    rooms: list[Room] | None = None,
) -> None:
    """Export every row-level valid scheduled assignment to Template 2."""
    export_schedule(
        submission_assignments(assignments, rooms=rooms),
        output_path,
        template2_path=template2_path,
        enable_remark_interpretation=enable_remark_interpretation,
        aggregate_teaching_weeks=False,
    )


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
        aggregate_teaching_weeks=True,
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


def _invalid_row_numbers(invalid_rows: list[dict[str, object]]) -> set[int]:
    """Return row numbers already rejected by row-level validation."""
    numbers: set[int] = set()
    for row in invalid_rows:
        try:
            numbers.add(int(row.get("Row") or 0))
        except (TypeError, ValueError):
            continue
    return numbers


def _saved_programme_year_counts(
    rows: list[dict[str, object]],
    invalid_rows: list[dict[str, object]],
) -> Counter[str]:
    """Count programme-years from actual saved Template 2 rows only."""
    invalid_numbers = _invalid_row_numbers(invalid_rows)
    counts: Counter[str] = Counter()
    for row in rows:
        try:
            row_number = int(row.get("_row") or 0)
        except (TypeError, ValueError):
            row_number = 0
        if row_number in invalid_numbers:
            continue
        programme_year = saved_row_programme_year(row)
        if programme_year:
            counts[programme_year] += 1
    return counts


def _template2_assignment_id(assignment: Assignment) -> tuple[object, ...]:
    """Return a row identity matching the Template 2 saved row fields."""
    row = assignment_to_row(assignment)
    return (
        row.get("Module"),
        row.get("Class Type"),
        row.get("Group"),
        row.get("Day"),
        row.get("Start"),
        row.get("Tri Week"),
        row.get("Room1"),
    )


def _template2_row_id(row: dict[str, object]) -> tuple[object, ...]:
    """Return a saved-row identity for source-to-output reconciliation."""
    return (
        row.get("Module"),
        row.get("Class Type"),
        row.get("Group"),
        row.get("Day"),
        row.get("Start"),
        str(row.get("Tri Week") or ""),
        row.get("Room1"),
    )


def _source_reference(course: Course) -> dict[str, object]:
    """Return source workbook references for an audit row."""
    return {
        "Source Workbook": course.source_file,
        "Source Sheet": course.source_sheet,
        "Source Row": course.source_row,
    }


def _assignment_exclusion_row(
    assignment: Assignment,
    rule: str,
    reason: str,
    missing_field: str = "",
) -> dict[str, object]:
    """Return one Template 2 exclusion audit row."""
    course = assignment.course
    return {
        "Programme-Year": normalise_programme_year(course.prog_yr),
        "Module": course.module_code,
        "Activity": course.activity,
        "Scheduled Row ID": "/".join(str(part or "") for part in _template2_assignment_id(assignment)),
        "Exclusion Rule": rule,
        "Exclusion Reason": reason,
        "Missing Field": missing_field,
        **_source_reference(course),
    }


def _missing_required_fields(assignment: Assignment) -> list[str]:
    """Return Template 2 required values missing from a scheduled assignment."""
    course = assignment.course
    missing: list[str] = []
    if not course.module_code:
        missing.append("Module")
    if not course.activity:
        missing.append("Class Type")
    if not (course.group_ids or course.prog_yr):
        missing.append("Group")
    if course.class_size <= 0:
        missing.append("Class Size")
    if assignment.room is None or not assignment.room.room_id:
        missing.append("Room1")
    if not (course.staff_names or course.staff_ids):
        missing.append("Staff1")
    if assignment.timeslot is None:
        missing.extend(["Day", "Start", "End", "Tri Week"])
    if course.duration_hrs <= 0:
        missing.append("Duration")
    return missing


def build_template2_exclusion_audit_rows(
    assignments: list[Assignment],
    complete_programmes: set[str] | None = None,
    rooms: list[Room] | None = None,
) -> list[dict[str, object]]:
    """Return row-level reasons assignments are absent from strict Template 2."""
    valid_room_ids = _valid_rooms(rooms or []) if rooms is not None else None
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        programme = normalise_programme_year(assignment.course.prog_yr)
        if not _is_submission_assignment(assignment):
            reason = "; ".join(assignment.hard_violations) if assignment.hard_violations else "Assignment is unscheduled."
            rows.append(_assignment_exclusion_row(assignment, "unscheduled-or-hard-invalid", reason))
            continue
        missing = _missing_required_fields(assignment)
        if missing:
            rows.append(
                _assignment_exclusion_row(
                    assignment,
                    "missing-required-template2-value",
                    "One or more required Template 2 fields cannot be populated.",
                    ", ".join(missing),
                )
            )
            continue
        if valid_room_ids is not None and assignment.room is not None and assignment.room.room_id not in valid_room_ids:
            rows.append(
                _assignment_exclusion_row(
                    assignment,
                    "invalid-room-mapping",
                    f"Room '{assignment.room.room_id}' is not in the venue data.",
                    "Room1",
                )
            )
            continue
        if complete_programmes is not None and programme not in complete_programmes:
            rows.append(
                _assignment_exclusion_row(
                    assignment,
                    "incomplete-programme-year-filter",
                    "Valid scheduled row retained in all-valid output but excluded from strict submission-ready workbook.",
                )
            )
    return rows


def export_template2_exclusion_audit(
    assignments: list[Assignment],
    output_path: Path,
    complete_programmes: set[str] | None = None,
    rooms: list[Room] | None = None,
) -> None:
    """Export row-level Template 2 exclusion reasons."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_template2_exclusion_audit_rows(assignments, complete_programmes=complete_programmes, rooms=rooms)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Exclusion Audit", index=False)


def _programme_coverage(
    source_requirements: list[Course],
    assignments: list[Assignment],
    submission_rows: list[dict[str, object]],
    invalid_rows: list[dict[str, object]] | None = None,
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
    submission_count = _saved_programme_year_counts(submission_rows, invalid_rows or [])

    rows: list[dict[str, object]] = []
    for programme in sorted(set(required) | set(submission_count)):
        required_count = len(required[programme])
        scheduled_count = len(scheduled.get(programme, set()))
        complete = required_count > 0 and required_count == scheduled_count
        saved_rows = submission_count[programme]
        rows.append(
            {
                "Normalised Programme/Year": programme,
                "Required Assignments": required_count,
                "Required Teaching Occurrences": required_count,
                "Fixed Assignments": fixed_counts[programme],
                "Scheduled Assignments": scheduled_count,
                "Unscheduled Assignments": max(required_count - scheduled_count, 0),
                "Submission Rows": saved_rows,
                "Actual Saved Submission Rows": saved_rows,
                "Completion Percentage": (scheduled_count / required_count * 100) if required_count else 0,
                "Complete Schedule Status": "PASS" if complete else "FAIL",
                "Included In Submission": "Yes" if saved_rows else "No",
                "Submission-Ready Status": "PASS" if saved_rows else "FAIL",
                "Exclusion Reason": "" if saved_rows else "No valid saved rows in submission workbook",
            }
        )
    return rows


def _row_level_reconciliation(
    assignments: list[Assignment],
    submission_rows: list[dict[str, object]],
    invalid_rows: list[dict[str, object]],
    complete_programmes: set[str] | None = None,
) -> list[dict[str, object]]:
    """Map scheduled assignment rows to actual saved Template 2 rows."""
    saved_row_numbers = _invalid_row_numbers(invalid_rows)
    saved_index: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in submission_rows:
        if int(row.get("_row") or 0) not in saved_row_numbers:
            saved_index[_template2_row_id(row)].append(row)

    rows: list[dict[str, object]] = []
    for assignment in assignments:
        course = assignment.course
        row_id = _template2_assignment_id(assignment)
        saved_matches = saved_index.get(row_id, [])
        programme = normalise_programme_year(course.prog_yr)
        if saved_matches:
            status = "Saved in submission workbook"
            reason = ""
            saved_row = saved_matches[0].get("_row")
        elif not _is_submission_assignment(assignment):
            status = "Excluded"
            reason = "; ".join(assignment.hard_violations) if assignment.hard_violations else "Assignment is unscheduled."
            saved_row = ""
        elif complete_programmes is not None and programme not in complete_programmes:
            status = "Excluded"
            reason = "Programme-year is incomplete; row remains available in all-valid output."
            saved_row = ""
        else:
            status = "Missing from saved workbook"
            reason = "No matching saved Template 2 row found."
            saved_row = ""
        rows.append(
            {
                "Programme-Year": programme,
                "Module": course.module_code,
                "Activity": course.activity,
                "Scheduled Row ID": "/".join(str(part or "") for part in row_id),
                "Saved Timetable Row": saved_row,
                "Status": status,
                "Reason": reason,
                **_source_reference(course),
            }
        )
    return rows


def _missing_programme_year_rows(programme_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return scheduled programme-years absent from the saved submission workbook."""
    rows: list[dict[str, object]] = []
    for row in programme_rows:
        if int(row.get("Scheduled Assignments") or 0) <= 0:
            continue
        if int(row.get("Submission Rows") or 0) > 0:
            continue
        rows.append(
            {
                "Programme-Year": row.get("Normalised Programme/Year"),
                "Scheduled Assignments": row.get("Scheduled Assignments"),
                "Unscheduled Assignments": row.get("Unscheduled Assignments"),
                "Exclusion Reason": row.get("Exclusion Reason"),
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
    programme_rows = _programme_coverage(source_requirements, assignments, rows, invalid_rows)
    demand = build_demand_metrics(source_requirements, assignments, input_course_records=len(source_requirements))
    complete_programmes = sum(1 for row in programme_rows if row["Complete Schedule Status"] == "PASS")
    saved_programme_year_counts = _saved_programme_year_counts(rows, invalid_rows)
    actual_saved_programmes = len(saved_programme_year_counts)
    minimum_status = "PASS" if actual_saved_programmes >= REQUIRED_MIN_PROGRAMME_YEARS else "FAIL"
    missing_columns = [column for column in REQUIRED_SUBMISSION_COLUMNS if column not in headers]
    extra_columns = [column for column in headers if column not in template_headers]
    ready = not missing_columns and not extra_columns and not invalid_rows and not duplicates and minimum_status == "PASS"
    complete_programme_set = {
        str(row.get("Normalised Programme/Year"))
        for row in programme_rows
        if row.get("Complete Schedule Status") == "PASS"
    }
    reconciliation = _row_level_reconciliation(assignments, rows, invalid_rows, complete_programme_set)
    missing_programmes = _missing_programme_year_rows(programme_rows)
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
        "Actual saved Template 2 rows": len(rows),
        "rows with missing required fields": sum(1 for row in invalid_rows if "Missing" in row["Issues"]),
        "rows with mapping errors": len(invalid_rows),
        "distinct programme-year schedules": actual_saved_programmes,
        "actual saved programme-year schedules": actual_saved_programmes,
        "complete programme-year schedules": complete_programmes,
        "submission-ready programme-year schedules": actual_saved_programmes,
        "required minimum programme-year schedules": REQUIRED_MIN_PROGRAMME_YEARS,
        "minimum programme-year status": minimum_status,
        "Template 2 readiness status": "PASS" if ready else "FAIL",
        "missing columns": ", ".join(missing_columns),
        "extra accidental columns": ", ".join(str(column) for column in extra_columns),
    }
    return Template2ValidationResult(
        ready=ready,
        summary=summary,
        programme_rows=programme_rows,
        required_field_rows=field_rows,
        fixed_accuracy_rows=_fixed_accuracy(assignments),
        source_reconciliation_rows=reconciliation,
        duplicate_rows=duplicates,
        invalid_rows=invalid_rows,
        missing_programme_year_rows=missing_programmes,
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
        pd.DataFrame(result.missing_programme_year_rows).to_excel(writer, sheet_name="Missing Programme-Years", index=False)
        pd.DataFrame(
            [
                {
                    "Check": "Submission readiness",
                    "Status": "PASS" if result.ready else "FAIL",
                    "Notes": "Requires valid saved rows, valid mappings, no duplicates, and at least 20 actual saved programme-year schedules.",
                }
            ]
        ).to_excel(writer, sheet_name="Submission Readiness", index=False)


def export_template2_programme_year_reconciliation(result: Template2ValidationResult, output_path: Path) -> None:
    """Export programme-year and row-level Template 2 reconciliation evidence."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_keys = [
        "total required teaching occurrences",
        "total scheduled occurrences",
        "total unscheduled occurrences",
        "Template 2 output rows",
        "actual saved programme-year schedules",
        "complete programme-year schedules",
        "submission-ready programme-year schedules",
        "required minimum programme-year schedules",
        "minimum programme-year status",
        "Template 2 readiness status",
    ]
    summary_values = getattr(result, "summary", {})
    summary = [{"Metric": key, "Value": summary_values.get(key, "")} for key in summary_keys]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(getattr(result, "programme_rows", [])).to_excel(writer, sheet_name="Programme-Year Reconciliation", index=False)
        pd.DataFrame(getattr(result, "missing_programme_year_rows", [])).to_excel(writer, sheet_name="Missing Programme-Years", index=False)
        pd.DataFrame(getattr(result, "source_reconciliation_rows", [])).to_excel(writer, sheet_name="Row-Level Reconciliation", index=False)
