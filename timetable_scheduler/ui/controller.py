"""Headless-friendly controller logic for the desktop UI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_FIXED_CONFLICT_TRIAGE_FILE,
    DEFAULT_FIXED_RECONCILIATION_FILE,
    DEFAULT_FIXED_RESOLUTION_AUDIT_FILE,
    DEFAULT_FIXED_RESOLUTION_TEMPLATE_FILE,
    DEFAULT_FIXED_ROOT_CAUSE_FILE,
    DEFAULT_FIXED_SESSION_FILE,
    DEFAULT_FIXED_SESSIONS_AUDIT_FILE,
    DEFAULT_INPUT_READINESS_REPORT_FILE,
    DEFAULT_LOCATION_MAPPING_EVIDENCE_FILE,
    DEFAULT_ROOM_FILE,
    DEFAULT_SUPERVISOR_CLARIFICATION_PACK_FILE,
    DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE,
)
from data.fixed_sessions import export_fixed_sessions_audit, load_fixed_sessions
from data.loader import (
    ConsolidatedScheduleValidationError,
    LoaderReport,
    load_rooms_from_csv,
    load_common_modules,
    load_consolidated_schedule,
)
from engine.fixed_reconciliation import export_fixed_reconciliation_report, reconcile_fixed_sessions
from engine.fixed_issue_analysis import export_fixed_issue_workbooks
from engine.fixed_scope import filter_fixed_sessions_to_selected_scope
from engine.guarded_generation import build_guarded_generation_state
from engine.input_readiness import build_input_readiness_result, export_input_readiness_report
from generator.fixed_scheduler import create_fixed_assignments, validate_fixed_assignments
from pipeline import PipelineCancelled, PipelineOptions, PipelineResult, run_timetable_pipeline


@dataclass(slots=True)
class ValidationResult:
    """Result of validating a selected UI path or action."""

    valid: bool
    message: str


@dataclass(slots=True)
class ControllerRunResult:
    """Pipeline invocation result mapped for UI handling."""

    success: bool
    message: str
    result: PipelineResult | None = None


@dataclass(frozen=True, slots=True)
class OutputAction:
    """Plain-language output action shown in the UI."""

    label: str
    description: str
    output_key: str
    success_message: str | None = None


PipelineRunner = Callable[[PipelineOptions, Callable[[str], None] | None, Event | None], PipelineResult]
FileOpener = Callable[[str], object]

EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}

OUTPUT_ACTIONS: dict[str, OutputAction] = {
    "proposed_timetable": OutputAction(
        label="Open Proposed Timetable",
        description="View the generated timetable ready for review.",
        output_key="proposed_timetable",
    ),
    "submission_ready_timetable": OutputAction(
        label="Open Submission-Ready Timetable",
        description="Open the validated Template 2 upload workbook for complete schedules.",
        output_key="submission_ready_timetable",
    ),
    "timetable_views": OutputAction(
        label="View Timetable Views",
        description="Review programme, tutor and room schedules.",
        output_key="stakeholder_views",
    ),
    "programme_visuals": OutputAction(
        label="Open Programme Timetables",
        description="Open calendar-style programme and year timetable views.",
        output_key="programme_visuals",
        success_message="Visual timetable files created. Opened Programme Timetables.",
    ),
    "tutor_visuals": OutputAction(
        label="Open Tutor Timetables",
        description="Open calendar-style tutor timetable views.",
        output_key="tutor_visuals",
        success_message="Visual timetable files created. Opened Tutor Timetables.",
    ),
    "room_visuals": OutputAction(
        label="Open Room Timetables",
        description="Open calendar-style room timetable views.",
        output_key="room_visuals",
        success_message="Visual timetable files created. Opened Room Timetables.",
    ),
    "unscheduled_review": OutputAction(
        label="Review Unscheduled Classes",
        description="See classes that still require manual scheduling.",
        output_key="stakeholder_views",
        success_message="Open the Exception Queue sheet to review unresolved classes.",
    ),
    "special_requests": OutputAction(
        label="Review Special Requests",
        description="See how scheduling remarks were interpreted and handled.",
        output_key="stakeholder_views",
        success_message="Open the Special Requests Review sheet to review interpreted remarks.",
    ),
    "scheduling_summary": OutputAction(
        label="View Scheduling Summary",
        description="Review coverage, validation checks and scheduling findings.",
        output_key="run_summary",
    ),
    "input_issues": OutputAction(
        label="Review Input Issues",
        description="Open the input readiness report.",
        output_key="input_readiness_report",
    ),
    "all_files": OutputAction(
        label="Open All Files",
        description="Open the folder containing all generated outputs.",
        output_key="output_folder",
    ),
}


def build_default_ui_options(consolidated_schedule_path: Path) -> PipelineOptions:
    """Return the fixed validated Engineering options for the desktop UI."""
    return PipelineOptions(
        scope="eng",
        consolidated_schedule_path=consolidated_schedule_path,
        input_mode="selected_workbook",
        room_path=None,
        run_optimisation=True,
        max_iterations=5,
        optimisation_time_limit=120,
        optimisation_patience=2,
        max_candidate_patterns=300,
        max_retry_assignments=50,
        progress_interval=25,
        skip_unscheduled_diagnostics=True,
        audit_demand_metrics=True,
    )


class TimetableUIController:
    """Coordinate UI validation, pipeline execution, and output opening."""

    def __init__(
        self,
        pipeline_runner: PipelineRunner = run_timetable_pipeline,
        file_opener: FileOpener | None = None,
    ) -> None:
        self.pipeline_runner = pipeline_runner
        self.file_opener = file_opener or os.startfile  # type: ignore[attr-defined]

    def validate_consolidated_schedule(self, consolidated_schedule_path: Path | None) -> ValidationResult:
        """Validate one selected consolidated schedule workbook."""
        if consolidated_schedule_path is None:
            return ValidationResult(False, "Select a valid Excel workbook")
        if not consolidated_schedule_path.exists() or not consolidated_schedule_path.is_file():
            return ValidationResult(False, "Select a valid Excel workbook")
        if consolidated_schedule_path.suffix.lower() not in EXCEL_EXTENSIONS:
            return ValidationResult(False, "Select a valid Excel workbook")

        try:
            common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
            courses = load_consolidated_schedule(
                consolidated_schedule_path,
                common_modules=common_modules,
                strict_teaching_week_dates=True,
            )
        except ConsolidatedScheduleValidationError as exc:
            return ValidationResult(False, str(exc))
        except Exception:
            return ValidationResult(False, "This workbook does not match the consolidated schedule format.")
        if not courses:
            return ValidationResult(False, "The selected workbook contains no scheduling records")
        if DEFAULT_FIXED_SESSION_FILE.exists():
            fixed_status = self._validate_fixed_readiness(courses)
            if not fixed_status.valid:
                return fixed_status
        return ValidationResult(True, "Schedule selected")

    def _validate_fixed_readiness(self, courses) -> ValidationResult:
        """Validate bundled fixed-session data for UI readiness."""
        try:
            rooms = load_rooms_from_csv(DEFAULT_ROOM_FILE)
            fixed_sessions, fixed_loader_report = load_fixed_sessions(DEFAULT_FIXED_SESSION_FILE)
            fixed_sessions, fixed_loader_report, _scope_rows = filter_fixed_sessions_to_selected_scope(
                fixed_sessions,
                fixed_loader_report,
                courses,
            )
            export_fixed_sessions_audit(fixed_loader_report, DEFAULT_FIXED_SESSIONS_AUDIT_FILE)
            reconciliation_report = reconcile_fixed_sessions(fixed_sessions, courses, fixed_loader_report)
            export_fixed_reconciliation_report(reconciliation_report, DEFAULT_FIXED_RECONCILIATION_FILE)
            fixed_assignments, mapping_issues = create_fixed_assignments(fixed_sessions, rooms)
            conflict_issues = validate_fixed_assignments(fixed_assignments)
            empty_report = LoaderReport()
            guarded_state = build_guarded_generation_state(
                courses=courses,
                rooms_loaded=len(rooms),
                fixed_sessions=fixed_sessions,
                fixed_loader_report=fixed_loader_report,
                reconciliation_report=reconciliation_report,
                fixed_assignments=fixed_assignments,
                fixed_assignment_issues=mapping_issues + conflict_issues,
            )
            readiness = build_input_readiness_result(
                fixed_loader_report=fixed_loader_report,
                reconciliation_report=reconciliation_report,
                fixed_assignment_issues=mapping_issues + conflict_issues,
                loader_report=empty_report,
                global_errors=guarded_state.global_errors,
                quarantined_requirements=guarded_state.quarantined_requirements,
            )
            export_input_readiness_report(readiness, DEFAULT_INPUT_READINESS_REPORT_FILE)
            export_fixed_issue_workbooks(
                fixed_sessions=fixed_sessions,
                courses=courses,
                assignments=fixed_assignments,
                rooms=rooms,
                loader_report=fixed_loader_report,
                reconciliation_report=reconciliation_report,
                mapping_issues=mapping_issues,
                conflict_issues=conflict_issues,
                root_cause_path=DEFAULT_FIXED_ROOT_CAUSE_FILE,
                conflict_triage_path=DEFAULT_FIXED_CONFLICT_TRIAGE_FILE,
                supervisor_queries_path=DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE,
                location_evidence_path=DEFAULT_LOCATION_MAPPING_EVIDENCE_FILE,
                supervisor_pack_path=DEFAULT_SUPERVISOR_CLARIFICATION_PACK_FILE,
                resolution_template_path=DEFAULT_FIXED_RESOLUTION_TEMPLATE_FILE,
                resolution_audit_path=DEFAULT_FIXED_RESOLUTION_AUDIT_FILE,
            )
        except Exception:
            return ValidationResult(False, "Input validation failed. Review the input issue report.")
        return ValidationResult(readiness.ready, readiness.message)

    def run_pipeline(
        self,
        options: PipelineOptions,
        progress_callback: Callable[[str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> ControllerRunResult:
        """Validate the selected workbook and invoke the reusable pipeline service."""
        validation = self.validate_consolidated_schedule(options.consolidated_schedule_path or options.input_path)
        if not validation.valid:
            return ControllerRunResult(False, validation.message)
        try:
            result = self.pipeline_runner(options, progress_callback, cancel_event)
        except PipelineCancelled as exc:
            return ControllerRunResult(False, str(exc))
        except Exception as exc:  # pragma: no cover - varied user files should still show concise messages
            return ControllerRunResult(False, f"Scheduling failed: {exc}")
        if not result.validation_passed:
            return ControllerRunResult(False, "Scheduling finished, but one or more output workbooks failed integrity validation.")
        return ControllerRunResult(True, "Timetable generation completed.", result)

    def display_values(self, result: PipelineResult) -> dict[str, str]:
        """Map pipeline result values to concise completion-screen text."""
        hard_conflicts = str(result.scheduled_hard_violations)
        coverage = result.selected_schedulable_coverage_percent or result.coverage_percent
        scheduled = result.scheduled_teaching_occurrences or result.selected_scheduled_occurrences or result.scheduled_occurrences
        review_rows = result.assignments_needing_review or result.input_rows_needing_review or 0
        search_failures = result.scheduler_search_failures if result.scheduler_search_failures else result.selected_search_failures
        return {
            "Coverage of schedulable teaching occurrences": f"{coverage:.2f}% of schedulable teaching occurrences",
            "Scheduled teaching occurrences": f"{scheduled} teaching occurrences",
            "Scheduling requirements needing review": f"{review_rows} scheduling requirements",
            "Scheduler placement failures": f"{search_failures} teaching occurrences",
            "Hard conflicts": hard_conflicts,
            "Visual timetable status": "Visual timetable files created"
            if {"programme_visuals", "tutor_visuals", "room_visuals"} <= set(result.output_paths)
            else "Not created",
        }

    def output_actions(self) -> dict[str, OutputAction]:
        """Return plain-language output actions in display order."""
        return OUTPUT_ACTIONS.copy()

    def open_output(self, result: PipelineResult | None, key: str) -> ValidationResult:
        """Open an output file/folder when present, returning a safe status."""
        if result is None:
            return ValidationResult(False, "No completed run is available yet.")
        action = OUTPUT_ACTIONS.get(key)
        output_key = action.output_key if action else key
        path = result.output_paths.get(output_key)
        if path is None:
            return ValidationResult(False, f"No output path is registered for {output_key}.")
        if not path.exists():
            return ValidationResult(False, f"Output file is missing: {path}")
        self.file_opener(str(path))
        if action and action.success_message:
            return ValidationResult(True, action.success_message)
        return ValidationResult(True, f"Opened {path.name if path.is_file() else path}.")
