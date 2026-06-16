"""Tests for stakeholder report exports."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from data.models import Assignment, Course, Room, TimeSlot
from output.report_exporter import export_preflight_report, export_run_summary


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
    }
    data.update(overrides)
    return Course(**data)


def test_export_preflight_report_creates_workbook(tmp_path: Path) -> None:
    """The preflight report should export issue rows."""
    output = tmp_path / "preflight_report.xlsx"
    issues = [
        {
            "severity": "error",
            "entity_type": "course",
            "entity_id": "ENG1001",
            "issue": "Class size is not positive",
            "recommendation": "Enter a class size greater than 0.",
        }
    ]

    export_preflight_report(issues, output)

    workbook = load_workbook(output)
    assert workbook.sheetnames == ["Preflight Issues"]
    assert workbook["Preflight Issues"]["A1"].value == "severity"
    assert workbook["Preflight Issues"]["D2"].value == "Class size is not positive"


def test_export_run_summary_creates_expected_sheets(tmp_path: Path) -> None:
    """The run summary should include all stakeholder report sheets."""
    output = tmp_path / "run_summary.xlsx"
    assignments = [
        Assignment(
            course=make_course(),
            room=Room("R1", 100, "physical"),
            timeslot=TimeSlot("Monday", "09:00", 1),
        ),
        Assignment(
            course=make_course(module_code="ENG1002"),
            room=None,
            timeslot=None,
            hard_violations=["Could not find feasible weekly room/day/start pattern"],
        ),
    ]

    export_run_summary(assignments, output)

    workbook = load_workbook(output)
    assert workbook.sheetnames == [
        "Summary",
        "Hard Violations",
        "Soft Violations",
        "Unscheduled Reasons",
        "Room Utilisation",
    ]
    assert workbook["Summary"]["A1"].value == "Metric"
