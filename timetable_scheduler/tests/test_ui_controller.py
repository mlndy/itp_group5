"""Headless tests for the desktop UI controller."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from openpyxl import Workbook

from pipeline import PipelineOptions, PipelineResult
from ui.controller import TimetableUIController, ValidationResult, build_default_ui_options


def write_schedule_workbook(path: Path, rows: list[list[object]] | None = None) -> None:
    """Create a minimal consolidated schedule workbook for loader-backed tests."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Module"
    worksheet.append(["Prog/Yr", "Class Size", "Module Code", "Activity", "Delivery Mode", "Teaching Weeks"])
    data_rows = [["ENG1", 30, "ENG1001", "Lecture", "F2F", "1-2"]] if rows is None else rows
    for row in data_rows:
        worksheet.append(row)
    workbook.save(path)


def write_template2_output_workbook(path: Path) -> None:
    """Create a small proposed-timetable output workbook."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Timetable"
    worksheet.append(["Module", "Class Type", "Template", "Group", "Day", "Start", "End", "Room1", "Staff1", "Tri Week", "Activity Hostkey"])
    worksheet.append(["ENG1001", "Lecture", 1, "All", "Mon", "0900", "1100", "R1", "Tutor", "1,2", "ENG1001-LEC"])
    workbook.save(path)


def make_result(tmp_path: Path) -> PipelineResult:
    """Create a small pipeline result for controller tests."""
    output_paths: dict[str, Path] = {}
    for key, filename in {
        "proposed_template2": "Template2.xlsx",
        "stakeholder_views": "stakeholder_views.xlsx",
        "run_summary": "run_summary.xlsx",
        "output_folder": "outputs",
    }.items():
        path = tmp_path / filename
        if key == "output_folder":
            path.mkdir()
        else:
            path.write_text("placeholder", encoding="utf-8")
        output_paths[key] = path
    return PipelineResult(
        required_occurrences=2777,
        scheduled_occurrences=2747,
        unscheduled_occurrences=30,
        coverage_percent=98.919,
        scheduled_hard_violations=0,
        online_required=813,
        online_scheduled=813,
        dsc_included=True,
        validation_passed=True,
        optimisation_status="Skipped",
        output_paths=output_paths,
    )


def test_validate_consolidated_schedule_loads_workbook(monkeypatch, tmp_path: Path) -> None:
    """A real workbook with scheduling rows should validate successfully."""
    input_file = tmp_path / "schedule.xlsx"
    write_schedule_workbook(input_file)
    monkeypatch.setattr(
        TimetableUIController,
        "_validate_fixed_readiness",
        lambda self, courses: ValidationResult(True, "Input ready"),
    )
    controller = TimetableUIController(file_opener=lambda path: None)

    result = controller.validate_consolidated_schedule(input_file)

    assert result.valid
    assert result.message == "Schedule selected"


def test_validate_consolidated_schedule_rejects_directory(tmp_path: Path) -> None:
    """The UI should accept one Excel workbook, not a directory."""
    controller = TimetableUIController(file_opener=lambda path: None)

    result = controller.validate_consolidated_schedule(tmp_path)

    assert not result.valid
    assert result.message == "Select a valid Excel workbook"


def test_validate_consolidated_schedule_rejects_empty_workbook(tmp_path: Path) -> None:
    """A workbook with no parsed course rows should produce a concise error."""
    input_file = tmp_path / "empty.xlsx"
    write_schedule_workbook(input_file, rows=[])
    controller = TimetableUIController(file_opener=lambda path: None)

    result = controller.validate_consolidated_schedule(input_file)

    assert not result.valid
    assert result.message == "The selected workbook contains no scheduling records"


def test_validate_consolidated_schedule_rejects_non_excel_file(tmp_path: Path) -> None:
    """Only xlsx and xlsm workbooks should pass UI path validation."""
    input_file = tmp_path / "schedule.csv"
    input_file.write_text("not excel", encoding="utf-8")
    controller = TimetableUIController(file_opener=lambda path: None)

    result = controller.validate_consolidated_schedule(input_file)

    assert not result.valid
    assert result.message == "Select a valid Excel workbook"


def test_build_default_ui_options_uses_validated_engineering_defaults(tmp_path: Path) -> None:
    """The simplified UI should centralise its fixed Engineering options."""
    input_file = tmp_path / "schedule.xlsx"

    options = build_default_ui_options(input_file)

    assert options.scope == "eng"
    assert options.consolidated_schedule_path == input_file
    assert options.input_path is None
    assert options.room_path is None
    assert options.run_optimisation is True
    assert options.max_iterations == 5
    assert options.optimisation_time_limit == 120
    assert options.optimisation_patience == 2
    assert options.max_candidate_patterns == 300
    assert options.max_retry_assignments == 50
    assert options.progress_interval == 25
    assert options.skip_unscheduled_diagnostics is True
    assert options.audit_demand_metrics is True


def test_controller_rejects_template2_output_as_input(tmp_path: Path) -> None:
    """The UI should not accept a generated timetable as input."""
    input_file = tmp_path / "maybe_schedule.xlsx"
    write_template2_output_workbook(input_file)
    controller = TimetableUIController(file_opener=lambda path: None)

    result = controller.validate_consolidated_schedule(input_file)

    assert not result.valid
    assert result.message == "This workbook appears to be a generated timetable.\nPlease select the consolidated schedule."


def test_controller_calls_pipeline_service_with_valid_workbook(monkeypatch, tmp_path: Path) -> None:
    """The controller should call the injected pipeline runner after validation."""
    input_file = tmp_path / "schedule.xlsx"
    write_schedule_workbook(input_file)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        TimetableUIController,
        "_validate_fixed_readiness",
        lambda self, courses: ValidationResult(True, "Input ready"),
    )

    def runner(options: PipelineOptions, progress_callback, cancel_event: Event | None) -> PipelineResult:
        captured["options"] = options
        if progress_callback:
            progress_callback("Loading input")
        return make_result(tmp_path)

    controller = TimetableUIController(pipeline_runner=runner, file_opener=lambda path: None)
    messages: list[str] = []

    result = controller.run_pipeline(build_default_ui_options(input_file), progress_callback=messages.append)

    assert result.success
    assert result.result is not None
    assert captured["options"].consolidated_schedule_path == input_file
    assert messages == ["Loading input"]


def test_pipeline_result_maps_to_simple_display_values(tmp_path: Path) -> None:
    """Display labels should be concise and exclude technical report details."""
    controller = TimetableUIController(file_opener=lambda path: None)

    values = controller.display_values(make_result(tmp_path))

    assert values["Coverage"] == "98.92%"
    assert values["Scheduled classes"] == "2747"
    assert values["Classes needing review"] == "30 teaching occurrences require review"
    assert values["Hard conflicts"] == "No hard-constraint conflicts"
    assert "DSC inclusion" not in values


def test_friendly_output_keys_map_to_expected_files(tmp_path: Path) -> None:
    """Plain-language output actions should open the correct pipeline outputs."""
    opened: list[str] = []
    result = make_result(tmp_path)
    controller = TimetableUIController(file_opener=opened.append)

    actions = controller.output_actions()
    assert actions["proposed_timetable"].description == "View the generated timetable ready for review."
    assert actions["special_requests"].label == "Review Special Requests"
    status = controller.open_output(result, "unscheduled_review")

    assert status.valid
    assert status.message == "Open the Exception Queue sheet to review unresolved classes."
    assert opened == [str(result.output_paths["stakeholder_views"])]


def test_missing_output_file_is_handled_safely(tmp_path: Path) -> None:
    """Missing output paths should return a safe warning result."""
    result = make_result(tmp_path)
    result.output_paths["run_summary"] = tmp_path / "missing.xlsx"
    controller = TimetableUIController(file_opener=lambda path: None)

    opened = controller.open_output(result, "scheduling_summary")

    assert not opened.valid
    assert "missing" in opened.message.lower()
