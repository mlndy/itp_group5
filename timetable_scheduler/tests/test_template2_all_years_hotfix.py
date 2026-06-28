"""Regression tests for Template 2 all-years validation evidence."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from config import DEFAULT_TEMPLATE2_FILE
from data.models import Assignment, Course, Room, TimeSlot
from output.exporter import export_schedule
from output.submission_validator import (
    build_template2_exclusion_audit_rows,
    export_all_valid_scheduled_schedule,
    export_template2_exclusion_audit,
    export_template2_programme_year_reconciliation,
    export_template2_validation_report,
    normalise_template2_programme_year,
    saved_row_programme_year,
    validate_template2_submission,
)


def make_course(index: int = 1, **overrides: object) -> Course:
    """Create one scheduled test requirement."""
    data = {
        "module_code": f"ENG{index:04d}",
        "activity": "Lecture",
        "prog_yr": f"P{index:02d}/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": [f"S{index:03d}"],
        "duration_hrs": 2,
        "group_ids": [f"P{index:02d}/YR 1"],
    }
    data.update(overrides)
    return Course(**data)


def make_assignment(index: int = 1, **course_overrides: object) -> Assignment:
    """Create one valid scheduled assignment."""
    return Assignment(
        make_course(index, **course_overrides),
        Room("R1", 100, "physical"),
        TimeSlot("Monday", "09:00", 1),
    )


def _summary(path: Path) -> dict[str, object]:
    """Read a Metric/Value summary sheet into a dictionary."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Summary"]
        return {row[0]: row[1] for row in sheet.iter_rows(min_row=2, values_only=True)}
    finally:
        workbook.close()


def _timetable_rows(path: Path) -> list[dict[str, object]]:
    """Return populated Timetable rows from a workbook."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Timetable"]
        headers = [cell.value for cell in sheet[1]]
        rows: list[dict[str, object]] = []
        for values in sheet.iter_rows(min_row=2, values_only=True):
            if not any(value not in (None, "") for value in values):
                continue
            rows.append(dict(zip(headers, values, strict=False)))
        return rows
    finally:
        workbook.close()


def test_template2_year_normalisation_preserves_later_years() -> None:
    """Year 2 and Year 3 labels should not collapse to Year 1."""
    assert normalise_template2_programme_year("DSC/YR 2") == "DSC/Y2"
    assert normalise_template2_programme_year("MEC / Year 3") == "MEC/Y3"
    assert normalise_template2_programme_year("ESE/Y4") == "ESE/Y4"
    assert normalise_template2_programme_year("EPE/2") == "EPE/Y2"
    assert normalise_template2_programme_year("METS/2022") == ""
    assert normalise_template2_programme_year("EDE, EPE, ESE, SBE") == ""


def test_saved_row_programme_year_uses_actual_template2_fields() -> None:
    """Programme-year evidence should come from the saved row, not source-only data."""
    assert saved_row_programme_year({"Group": "CVE/YR 2"}) == "CVE/Y2"
    assert saved_row_programme_year({"Activity Hostkey": "ENG1001-2510-ENG-UGRD-PU-LEC/RSE/YR 3"}) == "RSE/Y3"
    assert saved_row_programme_year({"Group": "EEE + ISE/P1"}) == ""


def test_validator_counts_programme_years_from_saved_workbook(tmp_path: Path) -> None:
    """Readiness should use actual saved Timetable rows as the source of truth."""
    assignments = [make_assignment(index) for index in range(1, 21)]
    workbook_path = tmp_path / "submission_ready.xlsx"
    export_schedule(assignments, workbook_path, template2_path=DEFAULT_TEMPLATE2_FILE)

    result = validate_template2_submission(
        workbook_path,
        [assignment.course for assignment in assignments],
        [],
        assignments,
        [Room("R1", 100, "physical")],
        DEFAULT_TEMPLATE2_FILE,
    )

    assert result.ready
    assert result.summary["actual saved programme-year schedules"] == 20
    assert result.summary["submission-ready programme-year schedules"] == 20
    assert result.summary["minimum programme-year status"] == "PASS"


def test_validator_fails_when_saved_workbook_has_fewer_than_twenty_programme_years(tmp_path: Path) -> None:
    """Source coverage cannot pass readiness when saved rows are missing."""
    assignments = [make_assignment(index) for index in range(1, 21)]
    workbook_path = tmp_path / "submission_ready.xlsx"
    export_schedule(assignments[:19], workbook_path, template2_path=DEFAULT_TEMPLATE2_FILE)

    result = validate_template2_submission(
        workbook_path,
        [assignment.course for assignment in assignments],
        [],
        assignments,
        [Room("R1", 100, "physical")],
        DEFAULT_TEMPLATE2_FILE,
    )

    assert not result.ready
    assert result.summary["actual saved programme-year schedules"] == 19
    assert result.summary["minimum programme-year status"] == "FAIL"


def test_all_valid_export_keeps_valid_rows_from_incomplete_programme_year(tmp_path: Path) -> None:
    """One unresolved requirement should not erase other valid rows from all-valid output."""
    scheduled = make_assignment(1, prog_yr="ENG/YR 2", group_ids=["ENG/YR 2"])
    unscheduled = Assignment(
        make_course(2, prog_yr="ENG/YR 2", group_ids=["ENG/YR 2"]),
        None,
        None,
        hard_violations=["No feasible placement"],
    )
    output = tmp_path / "all_valid.xlsx"

    export_all_valid_scheduled_schedule(
        [scheduled, unscheduled],
        output,
        template2_path=DEFAULT_TEMPLATE2_FILE,
        rooms=[Room("R1", 100, "physical")],
    )

    rows = _timetable_rows(output)
    assert len(rows) == 1
    assert rows[0]["Module"] == "ENG0001"
    assert rows[0]["Group"] == "ENG/YR 2"


def test_exclusion_audit_reports_incomplete_programme_year_filter(tmp_path: Path) -> None:
    """Strict submission exclusions should explain dropped valid scheduled rows."""
    assignment = make_assignment(1, prog_yr="ENG/YR 2", group_ids=["ENG/YR 2"])
    rows = build_template2_exclusion_audit_rows(
        [assignment],
        complete_programmes={"ENG/Y1"},
        rooms=[Room("R1", 100, "physical")],
    )

    assert len(rows) == 1
    assert rows[0]["Exclusion Rule"] == "incomplete-programme-year-filter"
    assert rows[0]["Programme-Year"] == "ENG/Y2"

    output = tmp_path / "template2_exclusion_audit.xlsx"
    export_template2_exclusion_audit(
        [assignment],
        output,
        complete_programmes={"ENG/Y1"},
        rooms=[Room("R1", 100, "physical")],
    )
    workbook = load_workbook(output, read_only=True)
    try:
        assert "Exclusion Audit" in workbook.sheetnames
    finally:
        workbook.close()


def test_template2_reconciliation_workbook_exports_evidence_sheets(tmp_path: Path) -> None:
    """The new reconciliation workbook should expose summary and row-level evidence."""
    assignments = [make_assignment(index) for index in range(1, 21)]
    workbook_path = tmp_path / "submission_ready.xlsx"
    export_schedule(assignments, workbook_path, template2_path=DEFAULT_TEMPLATE2_FILE)
    result = validate_template2_submission(
        workbook_path,
        [assignment.course for assignment in assignments],
        [],
        assignments,
        [Room("R1", 100, "physical")],
        DEFAULT_TEMPLATE2_FILE,
    )

    validation_path = tmp_path / "template2_submission_validation.xlsx"
    reconciliation_path = tmp_path / "template2_programme_year_reconciliation.xlsx"
    export_template2_validation_report(result, validation_path)
    export_template2_programme_year_reconciliation(result, reconciliation_path)

    validation_summary = _summary(validation_path)
    assert validation_summary["actual saved programme-year schedules"] == 20

    workbook = load_workbook(reconciliation_path, read_only=True)
    try:
        assert {
            "Summary",
            "Programme-Year Reconciliation",
            "Missing Programme-Years",
            "Row-Level Reconciliation",
        } <= set(workbook.sheetnames)
    finally:
        workbook.close()


def test_all_valid_export_preserves_template2_sheet_structure(tmp_path: Path) -> None:
    """Hotfix workbooks must not alter the official Template 2 sheet structure."""
    output = tmp_path / "all_valid.xlsx"
    export_all_valid_scheduled_schedule(
        [make_assignment(1)],
        output,
        template2_path=DEFAULT_TEMPLATE2_FILE,
        rooms=[Room("R1", 100, "physical")],
    )

    source = load_workbook(DEFAULT_TEMPLATE2_FILE, read_only=True)
    exported = load_workbook(output, read_only=True)
    try:
        assert exported.sheetnames == source.sheetnames
    finally:
        source.close()
        exported.close()
