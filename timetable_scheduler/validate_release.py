"""Validate existing v1.1 release Excel artefacts without regenerating them."""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from config import (
    BASE_DIR,
    DEFAULT_GUARDED_GENERATION_REPORT_FILE,
    DEFAULT_PROGRAMME_VISUALS_FILE,
    DEFAULT_ROOM_VISUALS_FILE,
    DEFAULT_RUN_MANIFEST_FILE,
    DEFAULT_RUN_SUMMARY_FILE,
    DEFAULT_STAKEHOLDER_VIEWS_FILE,
    DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE,
    DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE,
    DEFAULT_TUTOR_VISUALS_FILE,
    OUTPUT_DIR,
)

DEFAULT_TIMETABLE_FILE = OUTPUT_DIR / "final_timetable_engineering_cluster.xlsx"

EXPECTED_MIN_TESTS = 257
EXPECTED_TOTAL_TEACHING_OCCURRENCES = 3562
EXPECTED_SCHEDULABLE_OCCURRENCES = 3160
EXPECTED_QUARANTINED_OCCURRENCES = 402
EXPECTED_SCHEDULED_OCCURRENCES = 3070
EXPECTED_SEARCH_FAILURE_OCCURRENCES = 90
EXPECTED_SCHEDULED_HARD_VIOLATIONS = 0
EXPECTED_PROPOSED_TIMETABLE_ROWS = 2868
EXPECTED_TEMPLATE2_SUBMISSION_ROWS = 1183
EXPECTED_TEMPLATE2_COMPLETE_PROGRAMME_YEARS = 30
EXPECTED_SUBMISSION_READY_PROGRAMME_YEARS = 23
MIN_SUBMISSION_READY_PROGRAMME_YEARS = 20
EXPECTED_PROGRAMME_VISUAL_SHEETS = 81
EXPECTED_TUTOR_VISUAL_SHEETS = 225
EXPECTED_ROOM_VISUAL_SHEETS = 43
EXPECTED_PROGRAMME_VISUAL_ENTRIES = 3454
EXPECTED_TUTOR_VISUAL_ENTRIES = 4255
EXPECTED_ROOM_VISUAL_ENTRIES = 2367

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
REQUIRED_GUARDED_SHEETS = [
    "Summary",
    "Quarantined Requirements",
    "Unscheduled Search Failures",
    "Programme Completeness",
    "Submission Exclusions",
]
REQUIRED_TEMPLATE2_VALIDATION_SHEETS = [
    "Summary",
    "Programme Schedule Coverage",
    "Required Field Validation",
    "Source-to-Output Reconciliation",
    "Invalid Rows",
    "Submission Readiness",
]
REQUIRED_VISUAL_VALIDATION_SHEETS = [
    "Summary",
    "Programme Reconciliation",
    "Tutor Reconciliation",
    "Room Reconciliation",
    "Missing Visual Entries",
    "Unexpected Visual Entries",
    "Overlap Validation",
    "Export Status",
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


@dataclass(frozen=True, slots=True)
class ReleaseEvidencePaths:
    """Locations of generated evidence files used by release validation."""

    run_summary: Path = DEFAULT_RUN_SUMMARY_FILE
    timetable: Path = DEFAULT_TIMETABLE_FILE
    stakeholder_views: Path = DEFAULT_STAKEHOLDER_VIEWS_FILE
    run_manifest: Path = DEFAULT_RUN_MANIFEST_FILE
    guarded_report: Path = DEFAULT_GUARDED_GENERATION_REPORT_FILE
    template2_validation: Path = DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE
    visual_validation: Path = DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE
    programme_visuals: Path = DEFAULT_PROGRAMME_VISUALS_FILE
    tutor_visuals: Path = DEFAULT_TUTOR_VISUALS_FILE
    room_visuals: Path = DEFAULT_ROOM_VISUALS_FILE
    test_root: Path = BASE_DIR / "tests"


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


def _check_test_suite_size(test_root: Path, failures: list[str]) -> None:
    """Check the normal test suite still contains the v1.1 minimum test count."""
    if not test_root.exists():
        failures.append(f"Missing test folder: {test_root}")
        return
    test_count = 0
    for path in sorted(test_root.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append(f"Could not parse test file {path}: {exc}")
            continue
        test_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
            for node in tree.body
        )
    if test_count < EXPECTED_MIN_TESTS:
        failures.append(f"Normal test suite contains {test_count} tests, expected at least {EXPECTED_MIN_TESTS}")


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
    """Check final all-demand and hard-safety metrics."""
    summary = _sheet_dict(workbook, "Summary")
    required = summary.get("Required teaching occurrences")
    scheduled = summary.get("Scheduled teaching occurrences")
    unscheduled = summary.get("Unscheduled teaching occurrences")
    scheduled_hard = summary.get("Hard violations on scheduled assignments")

    if required != EXPECTED_TOTAL_TEACHING_OCCURRENCES:
        failures.append(
            f"Required teaching occurrences is {required}, expected {EXPECTED_TOTAL_TEACHING_OCCURRENCES}"
        )
    if not isinstance(required, int) or not isinstance(scheduled, int) or not isinstance(unscheduled, int):
        failures.append("Teaching occurrence metrics must be numeric")
        return
    if required != scheduled + unscheduled:
        failures.append(f"Demand inconsistency: {required} != {scheduled} + {unscheduled}")
    if scheduled != EXPECTED_SCHEDULED_OCCURRENCES:
        failures.append(f"Scheduled teaching occurrences is {scheduled}, expected {EXPECTED_SCHEDULED_OCCURRENCES}")
    if scheduled_hard != EXPECTED_SCHEDULED_HARD_VIOLATIONS:
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


def _check_guarded_report(workbook: Workbook, failures: list[str]) -> None:
    """Check guarded-generation summary metrics for v1.1 evidence."""
    summary = _sheet_dict(workbook, "Summary")
    total = summary.get("Total teaching occurrences")
    schedulable = summary.get("Schedulable occurrences")
    quarantined = summary.get("Quarantined occurrences")
    scheduled = summary.get("Scheduled occurrences")
    search_failures = summary.get("Unscheduled search failures")
    scheduled_hard = summary.get("Scheduled hard violations")
    template_complete = summary.get("Template 2 complete programme-years")
    submission_ready = summary.get("Submission-ready programme-years")

    expected_values = {
        "Total teaching occurrences": (total, EXPECTED_TOTAL_TEACHING_OCCURRENCES),
        "Schedulable occurrences": (schedulable, EXPECTED_SCHEDULABLE_OCCURRENCES),
        "Quarantined occurrences": (quarantined, EXPECTED_QUARANTINED_OCCURRENCES),
        "Scheduled occurrences": (scheduled, EXPECTED_SCHEDULED_OCCURRENCES),
        "Unscheduled search failures": (search_failures, EXPECTED_SEARCH_FAILURE_OCCURRENCES),
        "Scheduled hard violations": (scheduled_hard, EXPECTED_SCHEDULED_HARD_VIOLATIONS),
        "Template 2 complete programme-years": (template_complete, EXPECTED_TEMPLATE2_COMPLETE_PROGRAMME_YEARS),
        "Submission-ready programme-years": (submission_ready, EXPECTED_SUBMISSION_READY_PROGRAMME_YEARS),
    }
    for label, (actual, expected) in expected_values.items():
        if actual != expected:
            failures.append(f"{label} is {actual}, expected {expected}")
    if isinstance(total, int) and isinstance(schedulable, int) and isinstance(quarantined, int):
        if total != schedulable + quarantined:
            failures.append(f"Recorded demand split is inconsistent: {total} != {schedulable} + {quarantined}")
    if isinstance(schedulable, int) and isinstance(scheduled, int) and isinstance(search_failures, int):
        if schedulable != scheduled + search_failures:
            failures.append(f"Schedulable split is inconsistent: {schedulable} != {scheduled} + {search_failures}")
    if not isinstance(submission_ready, int) or submission_ready < MIN_SUBMISSION_READY_PROGRAMME_YEARS:
        failures.append(
            f"Submission-ready programme-years is {submission_ready}, expected at least {MIN_SUBMISSION_READY_PROGRAMME_YEARS}"
        )


def _check_template2_validation(workbook: Workbook, failures: list[str]) -> None:
    """Check submission-ready Template 2 validation metrics."""
    summary = _sheet_dict(workbook, "Summary")
    rows = summary.get("Template 2 output rows")
    missing = summary.get("rows with missing required fields")
    mapping_errors = summary.get("rows with mapping errors")
    complete = summary.get("complete programme-year schedules")
    submission_ready = summary.get("submission-ready programme-year schedules")
    status = summary.get("Template 2 readiness status")
    expected_values = {
        "Template 2 output rows": (rows, EXPECTED_TEMPLATE2_SUBMISSION_ROWS),
        "rows with missing required fields": (missing, 0),
        "rows with mapping errors": (mapping_errors, 0),
        "complete programme-year schedules": (complete, EXPECTED_TEMPLATE2_COMPLETE_PROGRAMME_YEARS),
        "submission-ready programme-year schedules": (submission_ready, EXPECTED_SUBMISSION_READY_PROGRAMME_YEARS),
        "Template 2 readiness status": (status, "PASS"),
    }
    for label, (actual, expected) in expected_values.items():
        if actual != expected:
            failures.append(f"{label} is {actual}, expected {expected}")
    readiness = workbook["Submission Readiness"]
    statuses = [row[1] for row in readiness.iter_rows(min_row=2, values_only=True) if row and row[0]]
    if not statuses or any(status != "PASS" for status in statuses):
        failures.append("Submission Readiness sheet does not show PASS")


def _check_visual_validation(workbook: Workbook, failures: list[str]) -> None:
    """Check visual timetable reconciliation metrics."""
    summary = _sheet_dict(workbook, "Summary")
    expected_values = {
        "scheduled assignments received": (summary.get("scheduled assignments received"), EXPECTED_SCHEDULED_OCCURRENCES),
        "programme visual entries": (summary.get("programme visual entries"), EXPECTED_PROGRAMME_VISUAL_ENTRIES),
        "tutor visual entries": (summary.get("tutor visual entries"), EXPECTED_TUTOR_VISUAL_ENTRIES),
        "room visual entries": (summary.get("room visual entries"), EXPECTED_ROOM_VISUAL_ENTRIES),
        "programme sheets": (summary.get("programme sheets"), EXPECTED_PROGRAMME_VISUAL_SHEETS),
        "tutor sheets": (summary.get("tutor sheets"), EXPECTED_TUTOR_VISUAL_SHEETS),
        "room sheets": (summary.get("room sheets"), EXPECTED_ROOM_VISUAL_SHEETS),
        "missing entries": (summary.get("missing entries"), 0),
        "unexpected entries": (summary.get("unexpected entries"), 0),
        "invalid overlaps": (summary.get("invalid overlaps"), 0),
        "visual export status": (summary.get("visual export status"), "PASS"),
    }
    for label, (actual, expected) in expected_values.items():
        if actual != expected:
            failures.append(f"{label} is {actual}, expected {expected}")


def _check_timetable_workbook(workbook: Workbook, failures: list[str]) -> None:
    """Check proposed timetable workbook structure and row count."""
    _check_required_sheets(workbook, REQUIRED_TIMETABLE_SHEETS, "Timetable workbook", failures)
    if "Timetable" not in workbook.sheetnames:
        return
    sheet = workbook["Timetable"]
    headers = [cell.value for cell in sheet[1]]
    for column in REQUIRED_TIMETABLE_COLUMNS:
        if column not in headers:
            failures.append(f"Timetable sheet missing required column: {column}")
    row_count = max(sheet.max_row - 1, 0)
    if row_count != EXPECTED_PROPOSED_TIMETABLE_ROWS:
        failures.append(f"Proposed timetable rows is {row_count}, expected {EXPECTED_PROPOSED_TIMETABLE_ROWS}")


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
        if manifest.get("required_teaching_occurrences") != EXPECTED_TOTAL_TEACHING_OCCURRENCES:
            failures.append("Run Manifest required teaching occurrences do not match v1.1 evidence")
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
    guarded_report_path: Path = DEFAULT_GUARDED_GENERATION_REPORT_FILE,
    template2_validation_path: Path = DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE,
    visual_validation_path: Path = DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE,
    programme_visuals_path: Path = DEFAULT_PROGRAMME_VISUALS_FILE,
    tutor_visuals_path: Path = DEFAULT_TUTOR_VISUALS_FILE,
    room_visuals_path: Path = DEFAULT_ROOM_VISUALS_FILE,
    test_root: Path = BASE_DIR / "tests",
) -> ReleaseValidationResult:
    """Validate existing release artefacts and return the result."""
    failures: list[str] = []
    _check_test_suite_size(test_root, failures)
    run_summary = _load_workbook(run_summary_path, failures)
    timetable = _load_workbook(timetable_path, failures)
    stakeholder_views = _load_workbook(stakeholder_views_path, failures)
    run_manifest = _load_workbook(run_manifest_path, failures)
    guarded_report = _load_workbook(guarded_report_path, failures)
    template2_validation = _load_workbook(template2_validation_path, failures)
    visual_validation = _load_workbook(visual_validation_path, failures)
    _load_workbook(programme_visuals_path, failures)
    _load_workbook(tutor_visuals_path, failures)
    _load_workbook(room_visuals_path, failures)

    if run_summary is not None:
        _check_required_sheets(run_summary, REQUIRED_RUN_SUMMARY_SHEETS, "run_summary.xlsx", failures)
        if all(sheet in run_summary.sheetnames for sheet in REQUIRED_RUN_SUMMARY_SHEETS):
            _check_validation_statuses(run_summary, failures)
            _check_summary_metrics(run_summary, failures)
            _check_programme_breakdown(run_summary, failures)

    if guarded_report is not None:
        _check_required_sheets(guarded_report, REQUIRED_GUARDED_SHEETS, "guarded_generation_report.xlsx", failures)
        if "Summary" in guarded_report.sheetnames:
            _check_guarded_report(guarded_report, failures)

    if template2_validation is not None:
        _check_required_sheets(
            template2_validation,
            REQUIRED_TEMPLATE2_VALIDATION_SHEETS,
            "template2_submission_validation.xlsx",
            failures,
        )
        if "Summary" in template2_validation.sheetnames and "Submission Readiness" in template2_validation.sheetnames:
            _check_template2_validation(template2_validation, failures)

    if visual_validation is not None:
        _check_required_sheets(
            visual_validation,
            REQUIRED_VISUAL_VALIDATION_SHEETS,
            "timetable_visualisation_validation.xlsx",
            failures,
        )
        if "Summary" in visual_validation.sheetnames:
            _check_visual_validation(visual_validation, failures)

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
    parser.add_argument("--guarded-report", type=Path, default=DEFAULT_GUARDED_GENERATION_REPORT_FILE)
    parser.add_argument("--template2-validation", type=Path, default=DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE)
    parser.add_argument("--visual-validation", type=Path, default=DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE)
    parser.add_argument("--programme-visuals", type=Path, default=DEFAULT_PROGRAMME_VISUALS_FILE)
    parser.add_argument("--tutor-visuals", type=Path, default=DEFAULT_TUTOR_VISUALS_FILE)
    parser.add_argument("--room-visuals", type=Path, default=DEFAULT_ROOM_VISUALS_FILE)
    parser.add_argument("--test-root", type=Path, default=BASE_DIR / "tests")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run release validation and print a short result."""
    args = parse_args(argv)
    result = validate_release(
        args.run_summary,
        args.timetable,
        args.stakeholder_views,
        args.run_manifest,
        args.guarded_report,
        args.template2_validation,
        args.visual_validation,
        args.programme_visuals,
        args.tutor_visuals,
        args.room_visuals,
        args.test_root,
    )
    if result.passed:
        print("FINAL RELEASE VALIDATION: PASS")
        return 0

    print("FINAL RELEASE VALIDATION: FAIL")
    for failure in result.failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
