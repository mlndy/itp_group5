"""Tests for the read-only release validator."""

from __future__ import annotations

import importlib
from pathlib import Path

from openpyxl import Workbook

import validate_release


def _replace_default_sheet(workbook: Workbook, title: str):
    """Rename the default worksheet and return it."""
    sheet = workbook.active
    sheet.title = title
    return sheet


def _add_metric_sheet(workbook: Workbook, title: str, rows: list[tuple[object, object]]) -> None:
    """Add a two-column metric sheet."""
    sheet = _replace_default_sheet(workbook, title) if workbook.sheetnames == ["Sheet"] else workbook.create_sheet(title)
    sheet.append(["Metric", "Value"])
    for row in rows:
        sheet.append(list(row))


def _add_validation_checks(workbook: Workbook, demand_status: str = "PASS", hard_status: str = "PASS", dsc_status: str = "PASS") -> None:
    """Add Validation Checks sheet."""
    sheet = workbook.create_sheet("Validation Checks")
    sheet.append(["Check", "Value", "Status", "Notes"])
    sheet.append(["Demand occurrence consistency", 2777, demand_status, ""])
    sheet.append(["Hard-constraint safety status", "0 scheduled hard violations", hard_status, ""])
    sheet.append(["DSC inclusion status", "DSC rows found", dsc_status, ""])


def _add_programme_breakdown(workbook: Workbook, has_dsc: bool = True) -> None:
    """Add Programme Breakdown sheet."""
    sheet = workbook.create_sheet("Programme Breakdown")
    sheet.append(["Programme/Year", "Source File", "DSC Indicator"])
    sheet.append(["DSC/YR 1" if has_dsc else "ENG/YR 1", "2510_DSC.xlsx" if has_dsc else "ENG.xlsx", "Yes" if has_dsc else "No"])


def _create_run_summary(path: Path, *, required: int = 2777, scheduled: int = 2747, unscheduled: int = 30, scheduled_hard: int = 0, has_dsc: bool = True) -> None:
    """Create a minimal valid run_summary workbook."""
    workbook = Workbook()
    _add_metric_sheet(
        workbook,
        "Summary",
        [
            ("Required teaching occurrences", required),
            ("Scheduled teaching occurrences", scheduled),
            ("Unscheduled teaching occurrences", unscheduled),
            ("Hard violations on scheduled assignments", scheduled_hard),
        ],
    )
    _add_validation_checks(workbook)
    _add_metric_sheet(workbook, "Run Metadata", [("scope", "eng")])
    _add_programme_breakdown(workbook, has_dsc=has_dsc)
    _add_metric_sheet(
        workbook,
        "Resource Audit",
        [
            ("Required online teaching occurrences", 813),
            ("Scheduled online teaching occurrences", 813),
        ],
    )
    _add_metric_sheet(workbook, "Virtual Room Detail", [("Room ID", "ONLINE_ROOM")])
    _add_metric_sheet(workbook, "Unscheduled Analysis", [("Original Reason", "Could not find feasible slot")])
    _add_metric_sheet(workbook, "Unscheduled Breakdown", [("Reason Category", "Physical room scarcity")])
    _add_metric_sheet(workbook, "Residual F2F Analysis", [("Module Code", "ENG1001")])
    _add_metric_sheet(workbook, "Optimisation Summary", [("Optimisation enabled", "No")])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_timetable(path: Path) -> None:
    """Create a minimal Template 2-style timetable workbook."""
    workbook = Workbook()
    sheet = _replace_default_sheet(workbook, "Timetable")
    sheet.append(validate_release.REQUIRED_TIMETABLE_COLUMNS)
    sheet.append(["ENG1001"] + [""] * (len(validate_release.REQUIRED_TIMETABLE_COLUMNS) - 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def test_release_validator_passes_with_valid_temporary_workbooks(tmp_path: Path) -> None:
    """A minimal valid release package should pass."""
    run_summary = tmp_path / "run_summary.xlsx"
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_run_summary(run_summary)
    _create_timetable(timetable)

    result = validate_release.validate_release(run_summary, timetable)

    assert result.passed
    assert result.failures == []


def test_missing_workbook_produces_fail(tmp_path: Path) -> None:
    """A missing workbook should fail validation."""
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_timetable(timetable)

    result = validate_release.validate_release(tmp_path / "missing" / "run_summary.xlsx", timetable)

    assert not result.passed
    assert any("Missing workbook" in failure for failure in result.failures)


def test_missing_required_sheet_produces_fail(tmp_path: Path) -> None:
    """Missing run-summary sheets should fail validation."""
    run_summary = tmp_path / "run_summary.xlsx"
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_run_summary(run_summary)
    _create_timetable(timetable)
    workbook = Workbook()
    _add_metric_sheet(workbook, "Summary", [("Required teaching occurrences", 2777)])
    workbook.save(run_summary)

    result = validate_release.validate_release(run_summary, timetable)

    assert not result.passed
    assert any("missing required sheet" in failure for failure in result.failures)


def test_demand_inconsistency_produces_fail(tmp_path: Path) -> None:
    """Required occurrences must equal scheduled plus unscheduled occurrences."""
    run_summary = tmp_path / "run_summary.xlsx"
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_run_summary(run_summary, scheduled=2700, unscheduled=10)
    _create_timetable(timetable)

    result = validate_release.validate_release(run_summary, timetable)

    assert not result.passed
    assert any("Demand inconsistency" in failure for failure in result.failures)


def test_non_zero_scheduled_hard_violations_produces_fail(tmp_path: Path) -> None:
    """Scheduled hard violations must be zero."""
    run_summary = tmp_path / "run_summary.xlsx"
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_run_summary(run_summary, scheduled_hard=1)
    _create_timetable(timetable)

    result = validate_release.validate_release(run_summary, timetable)

    assert not result.passed
    assert any("Scheduled hard violations" in failure for failure in result.failures)


def test_missing_dsc_produces_fail(tmp_path: Path) -> None:
    """Programme Breakdown must contain DSC evidence."""
    run_summary = tmp_path / "run_summary.xlsx"
    timetable = tmp_path / "final_timetable_engineering_cluster.xlsx"
    _create_run_summary(run_summary, has_dsc=False)
    _create_timetable(timetable)

    result = validate_release.validate_release(run_summary, timetable)

    assert not result.passed
    assert any("does not contain DSC" in failure for failure in result.failures)


def test_workbooks_validate_without_generated_folders_existing(tmp_path: Path) -> None:
    """Validator should work with explicit paths outside generated folders."""
    run_summary = tmp_path / "release" / "summary.xlsx"
    timetable = tmp_path / "release" / "timetable.xlsx"
    _create_run_summary(run_summary)
    _create_timetable(timetable)

    result = validate_release.validate_release(run_summary, timetable)

    assert result.passed


def test_importing_validate_release_does_not_execute_validation(capsys) -> None:
    """Importing the module should not print release validation output."""
    importlib.reload(validate_release)

    captured = capsys.readouterr()
    assert "FINAL RELEASE VALIDATION" not in captured.out
