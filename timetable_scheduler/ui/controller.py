"""Headless-friendly controller logic for the desktop UI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from config import DEFAULT_COMMON_MODULE_FILE
from data.loader import (
    ConsolidatedScheduleValidationError,
    load_common_modules,
    load_consolidated_schedule,
)
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
        output_key="proposed_template2",
    ),
    "timetable_views": OutputAction(
        label="View Timetable Views",
        description="Review programme, tutor and room schedules.",
        output_key="stakeholder_views",
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
            courses = load_consolidated_schedule(consolidated_schedule_path, common_modules=common_modules)
        except ConsolidatedScheduleValidationError as exc:
            return ValidationResult(False, str(exc))
        except Exception:
            return ValidationResult(False, "This workbook does not match the consolidated schedule format.")
        if not courses:
            return ValidationResult(False, "The selected workbook contains no scheduling records")
        return ValidationResult(True, "Schedule selected")

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
        return ControllerRunResult(True, "Timetable generation completed.", result)

    def display_values(self, result: PipelineResult) -> dict[str, str]:
        """Map pipeline result values to concise completion-screen text."""
        hard_conflicts = (
            "No hard-constraint conflicts"
            if result.scheduled_hard_violations == 0
            else str(result.scheduled_hard_violations)
        )
        review_text = (
            f"{result.unscheduled_occurrences} teaching occurrences require review"
            if result.unscheduled_occurrences
            else "0 teaching occurrences require review"
        )
        return {
            "Coverage": f"{result.coverage_percent:.2f}%",
            "Scheduled classes": str(result.scheduled_occurrences),
            "Classes needing review": review_text,
            "Hard conflicts": hard_conflicts,
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
