"""Tests for fixed-session compliance and submission-readiness helpers."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from data.fixed_sessions import FixedSessionLoaderReport, load_fixed_sessions
from data.models import Assignment, Course, FixedSession, Room, TimeSlot
from engine.fixed_issue_analysis import export_fixed_issue_workbooks
from engine.fixed_reconciliation import FixedReconciliationReport, normalise_programme_year, reconcile_fixed_sessions
from engine.input_readiness import build_input_readiness_result
from generator.fixed_scheduler import create_fixed_assignments, normalise_staff_name, validate_fixed_assignments
from generator.scheduler import generate_schedule
from optimiser.local_search import optimise_schedule_with_stats
from output.submission_validator import (
    Template2ValidationResult,
    export_template2_validation_report,
    submission_assignments,
)


def make_course(**overrides: object) -> Course:
    """Create a compact course for fixed-session tests."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/Y1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 1,
        "group_ids": ["ENG/Y1"],
    }
    data.update(overrides)
    return Course(**data)


def make_fixed_session(**overrides: object) -> FixedSession:
    """Create one fixed source row."""
    data = {
        "programme_year": "ENG/Y1",
        "module_code": "ENG1001",
        "group_id": "P1",
        "group_size": 30,
        "day": "Monday",
        "start_time": "09:00",
        "duration_hours": 1.0,
        "teaching_weeks": (1,),
        "locations": ("E2-07-01",),
        "staff_ids": ("Tutor A",),
        "staff_names": ("Tutor A",),
        "source_file": "fixed.xlsx",
        "source_sheet": "ENG",
        "source_row": 2,
    }
    data.update(overrides)
    return FixedSession(**data)


def write_fixed_workbook(path: Path, rows: list[list[object]]) -> None:
    """Write a minimal fixed-session workbook."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ENG"
    worksheet.append(
        [
            "Prog/Yr",
            "Module code",
            "Group",
            "Group Size",
            "Day",
            "Start Time",
            "Duration (Hr)",
            "Weeks",
            "Location",
            "Staff 1",
        ]
    )
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def test_fixed_loader_separates_warning_and_critical_rows(tmp_path: Path) -> None:
    """Incomplete placements should warn, while invalid fixed placements remain critical."""
    workbook_path = tmp_path / "fixed.xlsx"
    write_fixed_workbook(
        workbook_path,
        [
            ["ENG/Y1", "ENG1001", "P1", 30, "", "", 1, "1", "Seminar Room", "Tutor A"],
            ["ENG/Y1", "ENG1002", "P1", 30, "Mon", "9am", 1, "", "Seminar Room", "Tutor A"],
        ],
    )

    sessions, report = load_fixed_sessions(workbook_path)

    assert sessions == []
    assert report.source_rows == 2
    assert report.warnings == 1
    assert report.critical_errors == 1
    assert [row["loader status"] for row in report.audit_rows] == ["not loaded", "invalid"]


def test_input_readiness_preserves_warning_only_incomplete_rows(tmp_path: Path) -> None:
    """Warning-only incomplete rows should not be promoted into critical blockers."""
    workbook_path = tmp_path / "fixed.xlsx"
    write_fixed_workbook(
        workbook_path,
        [["ENG/Y1", "ENG1001", "P1", 30, "", "", 1, "1", "Seminar Room", "Tutor A"]],
    )
    fixed_sessions, loader_report = load_fixed_sessions(workbook_path)
    reconciliation = reconcile_fixed_sessions(fixed_sessions, [], loader_report)

    readiness = build_input_readiness_result(
        fixed_loader_report=loader_report,
        reconciliation_report=reconciliation,
        fixed_assignment_issues=[],
    )

    assert readiness.ready
    assert not readiness.critical_errors
    assert readiness.warnings
    assert all(issue["severity"] == "warning" for issue in readiness.warnings)


def test_fixed_assignments_resolve_exact_room_alias_and_remain_anchored() -> None:
    """Exact fixed room codes should map to official venue IDs without moving the slot."""
    rooms = [Room("E2-07-01-SR259", 40, "physical", "Seminar Room")]
    assignments, issues = create_fixed_assignments([make_fixed_session()], rooms)

    assert issues == []
    assert len(assignments) == 1
    assert assignments[0].is_fixed
    assert assignments[0].room is not None
    assert assignments[0].room.room_id == "E2-07-01-SR259"
    assert assignments[0].timeslot == TimeSlot("Monday", "09:00", 1)


def test_programme_and_staff_alias_normalisation_is_conservative() -> None:
    """Safe aliases should normalise without changing source display values."""
    assert normalise_programme_year("DSC / Year 1") == "DSC/Y1"
    assert normalise_programme_year("DSC/Yr 1") == "DSC/Y1"
    assert normalise_staff_name("KHOO TECK PING .") == "KHOO TECK PING"


def test_shared_fixed_sessions_group_without_self_conflict() -> None:
    """Rows describing the same shared class should reserve resources once."""
    rooms = [Room("R1", 100, "physical", "Laboratory")]
    sessions = [
        make_fixed_session(group_id="P1", group_size=30, locations=("R1",), source_row=2),
        make_fixed_session(group_id="P2", group_size=25, locations=("R1",), source_row=3),
    ]

    assignments, issues = create_fixed_assignments(sessions, rooms)
    conflicts = validate_fixed_assignments(assignments)

    assert issues == []
    assert conflicts == []
    assert len(assignments) == 1
    assert assignments[0].course.class_size == 55
    assert assignments[0].course.group_ids == ["ENG/Y1/P1", "ENG/Y1/P2"]
    assert "fixed.xlsx:ENG:2" in (assignments[0].fixed_source or "")
    assert "fixed.xlsx:ENG:3" in (assignments[0].fixed_source or "")


def test_genuine_fixed_overlap_still_conflicts() -> None:
    """Different fixed classes sharing one physical room/time should remain blocked."""
    rooms = [Room("R1", 100, "physical", "Laboratory")]
    sessions = [
        make_fixed_session(module_code="ENG1001", locations=("R1",), staff_names=("Tutor A",), staff_ids=("Tutor A",), source_row=2),
        make_fixed_session(module_code="ENG1002", locations=("R1",), staff_names=("Tutor B",), staff_ids=("Tutor B",), source_row=3),
    ]

    assignments, issues = create_fixed_assignments(sessions, rooms)
    conflicts = validate_fixed_assignments(assignments)

    assert issues == []
    assert len(assignments) == 2
    assert any("Room clash" in issue["problem"] for issue in conflicts)


def test_generate_schedule_reserves_initial_fixed_assignments() -> None:
    """Non-fixed scheduling should avoid room/time occupied by anchored sessions."""
    room = Room("R1", 100, "physical", "Lectorial")
    fixed = Assignment(
        make_course(module_code="ENG0001", staff_ids=["F001"], group_ids=["ENG/Y9"], prog_yr="ENG/Y9"),
        room,
        TimeSlot("Monday", "09:00", 1),
        is_fixed=True,
        fixed_source="fixed.xlsx:ENG:2",
    )

    result = generate_schedule(
        [make_course(module_code="ENG1001", staff_ids=["S002"], group_ids=["ENG/Y1"])],
        [room],
        initial_assignments=[fixed],
        allow_weekly_fallback=False,
        max_retry_assignments=0,
    )

    movable = [assignment for assignment in result if not assignment.is_fixed][0]
    assert result[0].is_fixed
    assert movable.room == room
    assert movable.timeslot != TimeSlot("Monday", "09:00", 1)


def test_optimiser_preserves_fixed_assignment_on_early_return() -> None:
    """Early optimiser exits should still preserve fixed placements exactly."""
    room = Room("R1", 100, "physical", "Lectorial")
    fixed = Assignment(
        make_course(),
        room,
        TimeSlot("Monday", "09:00", 1),
        is_fixed=True,
        fixed_source="fixed.xlsx:ENG:2",
    )

    result = optimise_schedule_with_stats([fixed], [room], time_limit_seconds=0)

    assert result.status == "Time limit reached"
    assert result.assignments[0].is_fixed
    assert result.assignments[0].timeslot == TimeSlot("Monday", "09:00", 1)
    assert result.assignments[0].room == room


def test_submission_assignments_excludes_unresolved_or_invalid_rows() -> None:
    """Submission-ready exports should include only complete hard-valid rows."""
    scheduled = Assignment(make_course(), Room("R1", 100, "physical"), TimeSlot("Monday", "09:00", 1))
    unscheduled = Assignment(make_course(module_code="ENG1002"), None, None, hard_violations=["No room"])
    invalid = Assignment(
        make_course(module_code="ENG1003"),
        Room("R1", 100, "physical"),
        TimeSlot("Monday", "10:00", 1),
        hard_violations=["Room clash"],
    )

    assert submission_assignments([scheduled, unscheduled, invalid]) == [scheduled]


def test_template2_validation_report_exports_required_sheets(tmp_path: Path) -> None:
    """The submission validation evidence workbook should expose all review sheets."""
    output_path = tmp_path / "template2_validation.xlsx"
    export_template2_validation_report(Template2ValidationResult(ready=False), output_path)

    workbook = load_workbook(output_path, read_only=True)
    try:
        assert {
            "Summary",
            "Programme Schedule Coverage",
            "Fixed Session Accuracy",
            "Required Field Validation",
            "Source-to-Output Reconciliation",
            "Duplicate Check",
            "Invalid Rows",
            "Submission Readiness",
        } <= set(workbook.sheetnames)
    finally:
        workbook.close()


def test_fixed_issue_workbooks_include_supervisor_queries(tmp_path: Path) -> None:
    """Root-cause exports should distinguish issue instances from affected rows."""
    session = make_fixed_session(locations=("UNKNOWN",))
    loader_report = FixedSessionLoaderReport(workbook_path="fixed.xlsx")
    reconciliation = FixedReconciliationReport()
    mapping_issue = {
        "severity": "critical",
        "source": "fixed.xlsx",
        "sheet": "ENG",
        "row": 2,
        "field": "location",
        "problem": "Location 'UNKNOWN' is neither an exact room nor a supported generic room type.",
        "recommendation": "Clarify the room.",
    }
    second_issue_same_row = {**mapping_issue, "problem": "Exact fixed room 'UNKNOWN' was not found in the venue data."}

    stats = export_fixed_issue_workbooks(
        fixed_sessions=[session],
        courses=[],
        assignments=[],
        rooms=[],
        loader_report=loader_report,
        reconciliation_report=reconciliation,
        mapping_issues=[mapping_issue, second_issue_same_row],
        conflict_issues=[],
        root_cause_path=tmp_path / "root.xlsx",
        conflict_triage_path=tmp_path / "conflicts.xlsx",
        supervisor_queries_path=tmp_path / "queries.xlsx",
    )

    assert stats["critical_issue_instances"] == 2
    assert stats["unique_affected_rows"] == 1
    workbook = load_workbook(tmp_path / "queries.xlsx", read_only=True)
    try:
        assert "Supervisor Queries" in workbook.sheetnames
    finally:
        workbook.close()
