"""Unit tests for loader robustness and diagnostics."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from data.loader import export_loader_report, load_courses_from_folder, load_courses_from_requirements


def _write_requirement_workbook(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    """Write a small workbook in the expected requirements format."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Module"
    sheet.append([None] * len(headers))
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_successful_workbook_parsing_supports_column_variations(tmp_path: Path) -> None:
    """The loader should parse safe header variations without failing."""
    path = tmp_path / "eng_workbook.xlsx"
    _write_requirement_workbook(
        path,
        ["Prog Yr", "Enrolment", "Module", "Activity", "Mode", "Tri Week", "Staff 1", "Staff ID 1"],
        [["EPE/YR 1", 42, "UCM1001", "Lecture", "Online - Synchronous", "1,3-4", "Tan", "A1001"]],
    )

    courses, diagnostic = load_courses_from_requirements(path, common_modules={"UCM1001"})

    assert len(courses) == 1
    assert courses[0].module_code == "UCM1001"
    assert courses[0].is_common_module is True
    assert diagnostic.status == "parsed"
    assert diagnostic.rows_parsed == 1
    assert diagnostic.rows_skipped == 0
    assert diagnostic.reason == "Workbook parsed successfully"


def test_missing_required_columns_are_reported(tmp_path: Path) -> None:
    """Missing required columns should be returned as an explicit diagnostic."""
    path = tmp_path / "missing_columns.xlsx"
    _write_requirement_workbook(path, ["Prog Yr", "Activity"], [["EPE/YR 1", "Lecture"]])

    courses, diagnostic = load_courses_from_requirements(path)

    assert courses == []
    assert diagnostic.status == "skipped"
    assert diagnostic.file_path == str(path)
    assert diagnostic.sheet_name == "Module"
    assert diagnostic.missing_columns
    assert any("Class Size" in item or "Enrolment" in item for item in diagnostic.missing_columns)
    assert diagnostic.reason == "Missing required columns"


def test_skipped_workbook_is_reported_and_exported(tmp_path: Path) -> None:
    """The folder loader should expose every skipped workbook in its report."""
    good_path = tmp_path / "good.xlsx"
    bad_path = tmp_path / "bad.xlsx"
    report_path = tmp_path / "loader_report.xlsx"

    _write_requirement_workbook(
        good_path,
        ["Prog Yr", "Enrolment", "Module", "Activity", "Mode", "Teaching Weeks", "Staff ID 1"],
        [["METS/YR 3", 30, "MET3001", "Tutorial", "f2f", "1,2", "A2001"]],
    )
    _write_requirement_workbook(bad_path, ["Prog Yr", "Activity"], [["METS/YR 3", "Tutorial"]])

    courses, report = load_courses_from_folder(tmp_path)

    assert len(courses) == 1
    assert report.skipped_workbooks == 1
    assert report.partial_workbooks == 0
    assert len(report.workbooks) == 2

    skipped = next(item for item in report.workbooks if item.status == "skipped")
    assert skipped.file_path == str(bad_path)
    assert skipped.reason
    assert skipped.missing_columns

    export_loader_report(report, report_path)
    assert report_path.exists()

    workbook = load_workbook(report_path, read_only=True)
    assert workbook.sheetnames == ["Summary", "Diagnostics"]
    summary = workbook["Summary"]
    diagnostics = workbook["Diagnostics"]
    assert summary["A2"].value == "Workbooks scanned"
    assert summary["B5"].value == 1
    assert diagnostics["A2"].value is not None
