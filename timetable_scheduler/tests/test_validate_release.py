"""Tests for the read-only v1.1 release validator."""

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


def _add_validation_checks(
    workbook: Workbook,
    demand_status: str = "PASS",
    hard_status: str = "PASS",
    dsc_status: str = "PASS",
) -> None:
    """Add Validation Checks sheet."""
    sheet = workbook.create_sheet("Validation Checks")
    sheet.append(["Check", "Value", "Status", "Notes"])
    sheet.append(["Demand occurrence consistency", validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES, demand_status, ""])
    sheet.append(["Hard-constraint safety status", "0 scheduled hard violations", hard_status, ""])
    sheet.append(["DSC inclusion status", "DSC rows found", dsc_status, ""])


def _add_programme_breakdown(workbook: Workbook, has_dsc: bool = True) -> None:
    """Add Programme Breakdown sheet."""
    sheet = workbook.create_sheet("Programme Breakdown")
    sheet.append(["Programme/Year", "Source File", "DSC Indicator"])
    sheet.append(["DSC/Y1" if has_dsc else "ENG/Y1", "2510_DSC.xlsx" if has_dsc else "ENG.xlsx", "Yes" if has_dsc else "No"])


def _create_run_summary(
    path: Path,
    *,
    required: int = validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES,
    scheduled: int = validate_release.EXPECTED_SCHEDULED_OCCURRENCES,
    unscheduled: int = validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES - validate_release.EXPECTED_SCHEDULED_OCCURRENCES,
    scheduled_hard: int = 0,
    has_dsc: bool = True,
) -> None:
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
    _add_metric_sheet(workbook, "Resource Audit", [("Loaded physical room count", 169)])
    _add_metric_sheet(workbook, "Virtual Room Detail", [("Room ID", "ONLINE_ROOM")])
    _add_metric_sheet(workbook, "Unscheduled Analysis", [("Original Reason", "Could not find feasible slot")])
    _add_metric_sheet(workbook, "Unscheduled Breakdown", [("Reason Category", "Physical room scarcity")])
    _add_metric_sheet(workbook, "Residual F2F Analysis", [("Module Code", "ENG1001")])
    _add_metric_sheet(workbook, "Optimisation Summary", [("Optimisation enabled", "No")])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_guarded_report(
    path: Path,
    *,
    scheduled: int = validate_release.EXPECTED_SCHEDULED_OCCURRENCES,
    search_failures: int = validate_release.EXPECTED_SEARCH_FAILURE_OCCURRENCES,
) -> None:
    """Create a minimal guarded-generation report."""
    workbook = Workbook()
    _add_metric_sheet(
        workbook,
        "Summary",
        [
            ("Total teaching occurrences", validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES),
            ("Schedulable occurrences", validate_release.EXPECTED_SCHEDULABLE_OCCURRENCES),
            ("Quarantined occurrences", validate_release.EXPECTED_QUARANTINED_OCCURRENCES),
            ("Scheduled occurrences", scheduled),
            ("Unscheduled search failures", search_failures),
            ("Scheduled hard violations", validate_release.EXPECTED_SCHEDULED_HARD_VIOLATIONS),
            ("Template 2 complete programme-years", validate_release.EXPECTED_TEMPLATE2_COMPLETE_PROGRAMME_YEARS),
            ("Submission-ready programme-years", validate_release.EXPECTED_SUBMISSION_READY_PROGRAMME_YEARS),
        ],
    )
    for sheet in validate_release.REQUIRED_GUARDED_SHEETS:
        if sheet not in workbook.sheetnames:
            workbook.create_sheet(sheet).append(["Value"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_template2_validation(path: Path, *, readiness: str = "PASS", invalid_rows: int = 0) -> None:
    """Create a minimal Template 2 validation workbook."""
    workbook = Workbook()
    _add_metric_sheet(
        workbook,
        "Summary",
        [
            ("Template 2 output rows", validate_release.EXPECTED_TEMPLATE2_SUBMISSION_ROWS),
            ("rows with missing required fields", invalid_rows),
            ("rows with mapping errors", invalid_rows),
            ("complete programme-year schedules", validate_release.EXPECTED_TEMPLATE2_COMPLETE_PROGRAMME_YEARS),
            ("submission-ready programme-year schedules", validate_release.EXPECTED_SUBMISSION_READY_PROGRAMME_YEARS),
            ("Template 2 readiness status", readiness),
        ],
    )
    for sheet in validate_release.REQUIRED_TEMPLATE2_VALIDATION_SHEETS:
        if sheet not in workbook.sheetnames:
            created = workbook.create_sheet(sheet)
            if sheet == "Submission Readiness":
                created.append(["Check", "Status", "Notes"])
                created.append(["Submission readiness", readiness, ""])
            else:
                created.append(["Value"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_visual_validation(path: Path, *, status: str = "PASS", missing: int = 0) -> None:
    """Create a minimal visualisation validation workbook."""
    workbook = Workbook()
    _add_metric_sheet(
        workbook,
        "Summary",
        [
            ("scheduled assignments received", validate_release.EXPECTED_SCHEDULED_OCCURRENCES),
            ("programme visual entries", validate_release.EXPECTED_PROGRAMME_VISUAL_ENTRIES),
            ("tutor visual entries", validate_release.EXPECTED_TUTOR_VISUAL_ENTRIES),
            ("room visual entries", validate_release.EXPECTED_ROOM_VISUAL_ENTRIES),
            ("programme sheets", validate_release.EXPECTED_PROGRAMME_VISUAL_SHEETS),
            ("tutor sheets", validate_release.EXPECTED_TUTOR_VISUAL_SHEETS),
            ("room sheets", validate_release.EXPECTED_ROOM_VISUAL_SHEETS),
            ("missing entries", missing),
            ("unexpected entries", 0),
            ("invalid overlaps", 0),
            ("visual export status", status),
        ],
    )
    for sheet in validate_release.REQUIRED_VISUAL_VALIDATION_SHEETS:
        if sheet not in workbook.sheetnames:
            created = workbook.create_sheet(sheet)
            if sheet == "Export Status":
                created.append(["Workbook", "Status", "Issue"])
                created.append(["Programme_Timetable_Visuals.xlsx", status, ""])
            else:
                created.append(["Value"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_fixed_integrity(path: Path, *, status: str = "PASS", mismatches: int = 0) -> None:
    """Create a minimal fixed-session integrity workbook."""
    workbook = Workbook()
    _add_metric_sheet(
        workbook,
        "Summary",
        [
            ("fixed source rows", validate_release.EXPECTED_FIXED_SOURCE_ROWS),
            ("expected fixed teaching occurrences", validate_release.EXPECTED_FIXED_SOURCE_OCCURRENCES),
            ("anchored fixed teaching occurrences", validate_release.EXPECTED_ANCHORED_FIXED_SOURCE_OCCURRENCES),
            ("quarantined fixed teaching occurrences", validate_release.EXPECTED_QUARANTINED_FIXED_SOURCE_OCCURRENCES),
            ("missing fixed teaching occurrences", 0),
            ("placement mismatches", mismatches),
            ("scheduled hard violations on fixed assignments", 0),
            ("fixed-session integrity status", status),
        ],
    )
    for sheet in validate_release.REQUIRED_FIXED_INTEGRITY_SHEETS:
        if sheet not in workbook.sheetnames:
            created = workbook.create_sheet(sheet)
            created.append(["Value"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_timetable(path: Path) -> None:
    """Create a minimal Template 2-style proposed timetable workbook."""
    workbook = Workbook()
    sheet = _replace_default_sheet(workbook, "Timetable")
    sheet.append(validate_release.REQUIRED_TIMETABLE_COLUMNS)
    row = ["ENG1001"] + [""] * (len(validate_release.REQUIRED_TIMETABLE_COLUMNS) - 1)
    for _ in range(validate_release.EXPECTED_PROPOSED_TIMETABLE_ROWS):
        sheet.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_workbook(path: Path, sheet_name: str = "Sheet1") -> None:
    """Create a readable placeholder workbook."""
    workbook = Workbook()
    workbook.active.title = sheet_name
    workbook.active.append(["Value"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_stakeholder_views(path: Path) -> None:
    """Create a minimal stakeholder views workbook."""
    workbook = Workbook()
    programme = _replace_default_sheet(workbook, "Programme Timetable")
    programme.append(["Programme/Year", "Week", "Day"])
    tutor = workbook.create_sheet("Tutor Timetable")
    tutor.append(["Tutor", "Week", "Day"])
    room = workbook.create_sheet("Room Timetable")
    room.append(["Room", "Week", "Day"])
    queue = workbook.create_sheet("Exception Queue")
    queue.append(["Original Reason", "Classification", "Recommended Operational Action", "Review Status"])
    queue.append(["Could not find feasible slot", "Physical room scarcity", "Review large-room availability", "Open"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_run_manifest(path: Path, validation_status: str = "PASS", template_status: str = "PASS") -> None:
    """Create a minimal run manifest workbook."""
    workbook = Workbook()
    manifest = _replace_default_sheet(workbook, "Run Manifest")
    manifest.append(["Setting", "Value"])
    manifest.append(["validation_status", validation_status])
    manifest.append(["required_teaching_occurrences", validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES])
    weights = workbook.create_sheet("Soft Constraint Weights")
    weights.append(["Soft Rule", "Weight"])
    baseline = workbook.create_sheet("Soft Rule Baseline")
    baseline.append(["Soft Rule", "Count"])
    template = workbook.create_sheet("Template Validation")
    template.append(["Check", "Status", "Notes"])
    template.append(["Template 2 output structure retained", template_status, ""])
    trace = workbook.create_sheet("Traceability")
    trace.append(["Status", "Source File", "Module Code"])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _create_release_workbooks(tmp_path: Path) -> dict[str, Path]:
    """Create all workbook paths needed by the release validator."""
    paths = {
        "run_summary": tmp_path / "run_summary.xlsx",
        "timetable": tmp_path / "final_timetable_engineering_cluster.xlsx",
        "stakeholder_views": tmp_path / "stakeholder_views.xlsx",
        "run_manifest": tmp_path / "run_manifest.xlsx",
        "guarded_report": tmp_path / "guarded_generation_report.xlsx",
        "template2_validation": tmp_path / "template2_submission_validation.xlsx",
        "visual_validation": tmp_path / "timetable_visualisation_validation.xlsx",
        "fixed_integrity": tmp_path / "fixed_session_integrity_validation.xlsx",
        "programme_visuals": tmp_path / "Programme_Timetable_Visuals.xlsx",
        "tutor_visuals": tmp_path / "Tutor_Timetable_Visuals.xlsx",
        "room_visuals": tmp_path / "Room_Timetable_Visuals.xlsx",
    }
    _create_run_summary(paths["run_summary"])
    _create_timetable(paths["timetable"])
    _create_stakeholder_views(paths["stakeholder_views"])
    _create_run_manifest(paths["run_manifest"])
    _create_guarded_report(paths["guarded_report"])
    _create_template2_validation(paths["template2_validation"])
    _create_visual_validation(paths["visual_validation"])
    _create_fixed_integrity(paths["fixed_integrity"])
    _create_workbook(paths["programme_visuals"])
    _create_workbook(paths["tutor_visuals"])
    _create_workbook(paths["room_visuals"])
    return paths


def _validate(paths: dict[str, Path], *, test_root: Path | None = None) -> validate_release.ReleaseValidationResult:
    """Run validation with explicit temporary paths."""
    return validate_release.validate_release(
        paths["run_summary"],
        paths["timetable"],
        paths["stakeholder_views"],
        paths["run_manifest"],
        paths["guarded_report"],
        paths["template2_validation"],
        paths["visual_validation"],
        paths["fixed_integrity"],
        paths["programme_visuals"],
        paths["tutor_visuals"],
        paths["room_visuals"],
        test_root or Path(__file__).resolve().parent,
    )


def test_release_validator_passes_with_valid_temporary_workbooks(tmp_path: Path) -> None:
    """A minimal valid v1.1 release package should pass."""
    paths = _create_release_workbooks(tmp_path)

    result = _validate(paths)

    assert result.passed
    assert result.failures == []


def test_missing_workbook_produces_fail(tmp_path: Path) -> None:
    """A missing workbook should fail validation."""
    paths = _create_release_workbooks(tmp_path)
    paths["stakeholder_views"] = tmp_path / "missing.xlsx"

    result = _validate(paths)

    assert not result.passed
    assert any("Missing workbook" in failure for failure in result.failures)


def test_missing_required_sheet_produces_fail(tmp_path: Path) -> None:
    """Missing run-summary sheets should fail validation."""
    paths = _create_release_workbooks(tmp_path)
    workbook = Workbook()
    _add_metric_sheet(workbook, "Summary", [("Required teaching occurrences", validate_release.EXPECTED_TOTAL_TEACHING_OCCURRENCES)])
    workbook.save(paths["run_summary"])

    result = _validate(paths)

    assert not result.passed
    assert any("missing required sheet" in failure for failure in result.failures)


def test_demand_inconsistency_produces_fail(tmp_path: Path) -> None:
    """Required occurrences must equal scheduled plus unscheduled occurrences."""
    paths = _create_release_workbooks(tmp_path)
    _create_run_summary(paths["run_summary"], scheduled=3000, unscheduled=10)

    result = _validate(paths)

    assert not result.passed
    assert any("Demand inconsistency" in failure for failure in result.failures)


def test_non_zero_scheduled_hard_violations_produces_fail(tmp_path: Path) -> None:
    """Scheduled hard violations must be zero."""
    paths = _create_release_workbooks(tmp_path)
    _create_run_summary(paths["run_summary"], scheduled_hard=1)

    result = _validate(paths)

    assert not result.passed
    assert any("Scheduled hard violations" in failure for failure in result.failures)


def test_missing_dsc_produces_fail(tmp_path: Path) -> None:
    """Programme Breakdown must contain DSC evidence."""
    paths = _create_release_workbooks(tmp_path)
    _create_run_summary(paths["run_summary"], has_dsc=False)

    result = _validate(paths)

    assert not result.passed
    assert any("does not contain DSC" in failure for failure in result.failures)


def test_guarded_schedulable_split_must_match_v1_1_metrics(tmp_path: Path) -> None:
    """Schedulable demand must equal scheduled occurrences plus search failures."""
    paths = _create_release_workbooks(tmp_path)
    _create_guarded_report(paths["guarded_report"], search_failures=89)

    result = _validate(paths)

    assert not result.passed
    assert any("Unscheduled search failures" in failure for failure in result.failures)


def test_template2_readiness_failure_produces_fail(tmp_path: Path) -> None:
    """Template 2 readiness must pass."""
    paths = _create_release_workbooks(tmp_path)
    _create_template2_validation(paths["template2_validation"], readiness="FAIL")

    result = _validate(paths)

    assert not result.passed
    assert any("Template 2 readiness status" in failure for failure in result.failures)


def test_visual_validation_failure_produces_fail(tmp_path: Path) -> None:
    """Visual export validation must pass with no missing entries."""
    paths = _create_release_workbooks(tmp_path)
    _create_visual_validation(paths["visual_validation"], status="FAIL", missing=1)

    result = _validate(paths)

    assert not result.passed
    assert any("visual export status" in failure or "missing entries" in failure for failure in result.failures)


def test_fixed_integrity_failure_produces_fail(tmp_path: Path) -> None:
    """Fixed-session integrity evidence must pass."""
    paths = _create_release_workbooks(tmp_path)
    _create_fixed_integrity(paths["fixed_integrity"], status="FAIL", mismatches=1)

    result = _validate(paths)

    assert not result.passed
    assert any("fixed-session integrity status" in failure or "placement mismatches" in failure for failure in result.failures)


def test_normal_test_suite_size_is_checked(tmp_path: Path) -> None:
    """The validator should flag a too-small test folder."""
    paths = _create_release_workbooks(tmp_path)
    small_tests = tmp_path / "tests"
    small_tests.mkdir()
    (small_tests / "test_one.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")

    result = _validate(paths, test_root=small_tests)

    assert not result.passed
    assert any("expected at least" in failure for failure in result.failures)


def test_manifest_template_validation_failure_produces_fail(tmp_path: Path) -> None:
    """Template Validation rows must pass in the run manifest."""
    paths = _create_release_workbooks(tmp_path)
    _create_run_manifest(paths["run_manifest"], template_status="FAIL")

    result = _validate(paths)

    assert not result.passed
    assert any("Template Validation" in failure for failure in result.failures)


def test_importing_validate_release_does_not_execute_validation(capsys) -> None:
    """Importing the module should not print release validation output."""
    importlib.reload(validate_release)

    captured = capsys.readouterr()
    assert "FINAL RELEASE VALIDATION" not in captured.out
