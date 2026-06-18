"""Validate existing final-release Excel artefacts without regenerating them."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from config import DEFAULT_RUN_MANIFEST_FILE, DEFAULT_RUN_SUMMARY_FILE, DEFAULT_STAKEHOLDER_VIEWS_FILE, OUTPUT_DIR

DEFAULT_TIMETABLE_FILE = OUTPUT_DIR / "final_timetable_engineering_cluster.xlsx"
EXPECTED_REQUIRED_TEACHING_OCCURRENCES = 2777
REQUIRED_RUN_SUMMARY_SHEETS = [
    "Summary",
    "Validation Checks",
    "Run Metadata",
    "Programme Breakdown",
    "Resource Audit",
    "Virtual Room Detail",
    "Unscheduled Analysis",
    "Unscheduled Breakdown",
    "Residual F2F Analysis",
    "Optimisation Summary",
]
REQUIRED_TIMETABLE_SHEETS = ["Timetable"]
REQUIRED_TIMETABLE_COLUMNS = [
    "Module",
    "Class Type",
    "Group",
    "Day",
    "Start",
    "End",
    "Class Size",
    "Room1",
    "Staff1",
    "Staff2",
    "Tri Week",
    "Activity Type",
    "Duration",
    "Location Hostkey",
    "Remark",
]
REQUIRED_STAKEHOLDER_SHEETS = ["Programme Timetable", "Tutor Timetable", "Room Timetable", "Exception Queue"]
REQUIRED_MANIFEST_SHEETS = [
    "Run Manifest",
    "Soft Constraint Weights",
    "Soft Rule Baseline",
    "Template Validation",
    "Traceability",
]


@dataclass(slots=True)
class ReleaseValidationResult:
    """Release validation outcome and failure details."""

    passed: bool
    failures: list[str] = field(default_factory=list)


def _load_workbook(path: Path, failures: list[str]) -> Workbook | None:
    """Open one workbook and record a failure if it cannot be read."""
    if not path.exists():
        failures.append(f"Missing workbook: {path}")
        return None
    try:
        return load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # pragma: no cover - exact openpyxl errors vary
        failures.append(f"Could not open workbook {path}: {exc}")
        return None


def _sheet_dict(workbook: Workbook, sheet_name: str) -> dict[object, object]:
    """Return first-column/second-column rows as a dictionary."""
    worksheet = workbook[sheet_name]
    return {
        row[0]: row[1]
        for row in worksheet.iter_rows(min_row=2, values_only=True)
        if row and row[0] is not None
    }


def _validation_statuses(workbook: Workbook) -> dict[object, object]:
    """Return Validation Checks statuses keyed by check name."""
    worksheet = workbook["Validation Checks"]
    return {
        row[0]: row[2]
        for row in worksheet.iter_rows(min_row=2, values_only=True)
        if row and row[0] is not None
    }


def _check_required_sheets(workbook: Workbook, required: list[str], workbook_name: str, failures: list[str]) -> None:
    """Check required sheets exist."""
    for sheet_name in required:
        if sheet_name not in workbook.sheetnames:
            failures.append(f"{workbook_name} missing required sheet: {sheet_name}")


def _check_validation_statuses(workbook: Workbook, failures: list[str]) -> None:
    """Check key Validation Checks rows are PASS."""
    statuses = _validation_statuses(workbook)
    required_passes = {
        "Demand occurrence consistency": "demand consistency",
        "Hard-constraint safety status": "hard-constraint safety",
        "DSC inclusion status": "DSC inclusion",
    }
    for check, label in required_passes.items():
        if statuses.get(check) != "PASS":
            failures.append(f"Validation Checks does not show PASS for {label}")


def _check_summary_metrics(workbook: Workbook, failures: list[str]) -> None:
    """Check final demand and hard-safety metrics."""
    summary = _sheet_dict(workbook, "Summary")
    required = summary.get("Required teaching occurrences")
    scheduled = summary.get("Scheduled teaching occurrences")
    unscheduled = summary.get("Unscheduled teaching occurrences")
    scheduled_hard = summary.get("Hard violations on scheduled assignments")

    if required != EXPECTED_REQUIRED_TEACHING_OCCURRENCES:
        failures.append(f"Required teaching occurrences is {required}, expected {EXPECTED_REQUIRED_TEACHING_OCCURRENCES}")
    if not isinstance(required, int) or not isinstance(scheduled, int) or not isinstance(unscheduled, int):
        failures.append("Teaching occurrence metrics must be numeric")
        return
    if required != scheduled + unscheduled:
        failures.append(f"Demand inconsistency: {required} != {scheduled} + {unscheduled}")
    if scheduled_hard != 0:
        failures.append(f"Scheduled hard violations is {scheduled_hard}, expected 0")


def _check_programme_breakdown(workbook: Workbook, failures: list[str]) -> None:
    """Check Programme Breakdown contains DSC evidence."""
    worksheet = workbook["Programme Breakdown"]
    headers = [cell.value for cell in worksheet[1]]
    try:
        dsc_index = headers.index("DSC Indicator")
    except ValueError:
        failures.append("Programme Breakdown missing DSC Indicator column")
        return
    has_dsc = any(row[dsc_index] == "Yes" for row in worksheet.iter_rows(min_row=2, values_only=True))
    if not has_dsc:
        failures.append("Programme Breakdown does not contain DSC rows")


def _check_online_coverage(workbook: Workbook, failures: list[str]) -> None:
    """Check Resource Audit shows full online coverage."""
    audit = _sheet_dict(workbook, "Resource Audit")
    required = audit.get("Required online teaching occurrences")
    scheduled = audit.get("Scheduled online teaching occurrences")
    if required != scheduled:
        failures.append(f"Online scheduled occurrences {scheduled} does not equal required {required}")


def _check_residual_f2f_visibility(workbook: Workbook, failures: list[str]) -> None:
    """Check residual F2F exceptions remain visible."""
    worksheet = workbook["Residual F2F Analysis"]
    if worksheet.max_row < 2:
        failures.append("Residual F2F Analysis has no residual rows")


def _check_timetable_workbook(workbook: Workbook, failures: list[str]) -> None:
    """Check Template 2 workbook structure and required timetable columns."""
    _check_required_sheets(workbook, REQUIRED_TIMETABLE_SHEETS, "Timetable workbook", failures)
    if "Timetable" not in workbook.sheetnames:
        return
    headers = [cell.value for cell in workbook["Timetable"][1]]
    for column in REQUIRED_TIMETABLE_COLUMNS:
        if column not in headers:
            failures.append(f"Timetable sheet missing required column: {column}")


def _check_stakeholder_views(workbook: Workbook, failures: list[str]) -> None:
    """Check stakeholder workbook contains the required operational views."""
    _check_required_sheets(workbook, REQUIRED_STAKEHOLDER_SHEETS, "stakeholder_views.xlsx", failures)
    if "Exception Queue" in workbook.sheetnames:
        headers = [cell.value for cell in workbook["Exception Queue"][1]]
        for column in ["Original Reason", "Classification", "Recommended Operational Action", "Review Status"]:
            if column not in headers:
                failures.append(f"Exception Queue missing required column: {column}")


def _check_run_manifest(workbook: Workbook, failures: list[str]) -> None:
    """Check run manifest contains acceptance validation evidence."""
    _check_required_sheets(workbook, REQUIRED_MANIFEST_SHEETS, "run_manifest.xlsx", failures)
    if "Run Manifest" in workbook.sheetnames:
        manifest = _sheet_dict(workbook, "Run Manifest")
        if manifest.get("validation_status") != "PASS":
            failures.append("Run Manifest validation_status is not PASS")
    if "Template Validation" in workbook.sheetnames:
        worksheet = workbook["Template Validation"]
        statuses = [row[1] for row in worksheet.iter_rows(min_row=2, values_only=True) if row and row[0]]
        if any(status != "PASS" for status in statuses):
            failures.append("Template Validation contains non-PASS status")


def validate_release(
    run_summary_path: Path = DEFAULT_RUN_SUMMARY_FILE,
    timetable_path: Path = DEFAULT_TIMETABLE_FILE,
    stakeholder_views_path: Path = DEFAULT_STAKEHOLDER_VIEWS_FILE,
    run_manifest_path: Path = DEFAULT_RUN_MANIFEST_FILE,
) -> ReleaseValidationResult:
    """Validate existing release artefacts and return the result."""
    failures: list[str] = []
    run_summary = _load_workbook(run_summary_path, failures)
    timetable = _load_workbook(timetable_path, failures)
    stakeholder_views = _load_workbook(stakeholder_views_path, failures)
    run_manifest = _load_workbook(run_manifest_path, failures)

    if run_summary is not None:
        _check_required_sheets(run_summary, REQUIRED_RUN_SUMMARY_SHEETS, "run_summary.xlsx", failures)
        if all(sheet in run_summary.sheetnames for sheet in REQUIRED_RUN_SUMMARY_SHEETS):
            _check_validation_statuses(run_summary, failures)
            _check_summary_metrics(run_summary, failures)
            _check_programme_breakdown(run_summary, failures)
            _check_online_coverage(run_summary, failures)
            _check_residual_f2f_visibility(run_summary, failures)

    if timetable is not None:
        _check_timetable_workbook(timetable, failures)
    if stakeholder_views is not None:
        _check_stakeholder_views(stakeholder_views, failures)
    if run_manifest is not None:
        _check_run_manifest(run_manifest, failures)

    return ReleaseValidationResult(passed=not failures, failures=failures)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse release-validator command-line arguments."""
    parser = argparse.ArgumentParser(description="Validate generated final-release Excel artefacts")
    parser.add_argument("--run-summary", type=Path, default=DEFAULT_RUN_SUMMARY_FILE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE_FILE)
    parser.add_argument("--stakeholder-views", type=Path, default=DEFAULT_STAKEHOLDER_VIEWS_FILE)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST_FILE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run release validation and print a short result."""
    args = parse_args(argv)
    result = validate_release(args.run_summary, args.timetable, args.stakeholder_views, args.run_manifest)
    if result.passed:
        print("FINAL RELEASE VALIDATION: PASS")
        return 0

    print("FINAL RELEASE VALIDATION: FAIL")
    for failure in result.failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
