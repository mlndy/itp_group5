"""Reusable orchestration service for CLI and desktop UI callers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import perf_counter
from types import SimpleNamespace
from typing import Callable

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_COURSE_FILE,
    DEFAULT_ENGINEERING_FOLDER,
    DEFAULT_FIXED_RECONCILIATION_FILE,
    DEFAULT_FIXED_CONFLICT_TRIAGE_FILE,
    DEFAULT_FIXED_ROOT_CAUSE_FILE,
    DEFAULT_FIXED_SESSION_FILE,
    DEFAULT_FIXED_SESSIONS_AUDIT_FILE,
    DEFAULT_INPUT_READINESS_REPORT_FILE,
    DEFAULT_LOADER_REPORT_FILE,
    DEFAULT_PREFLIGHT_REPORT_FILE,
    DEFAULT_REMARKS_AUDIT_FILE,
    DEFAULT_ROOM_FILE,
    DEFAULT_RUN_MANIFEST_FILE,
    DEFAULT_RUN_SUMMARY_FILE,
    DEFAULT_STAKEHOLDER_VIEWS_FILE,
    DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE,
    DEFAULT_TEMPLATE2_SUBMISSION_FILE,
    DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE,
    DEFAULT_TEMPLATE2_FILE,
    DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE,
    OUTPUT_DIR,
)
from data.loader import (
    LoaderReport,
    export_loader_report,
    load_consolidated_schedule_with_report,
    load_common_modules,
    load_courses_from_folder,
    load_courses_from_requirements,
    load_rooms_from_csv,
)
from data.fixed_sessions import export_fixed_sessions_audit, load_fixed_sessions
from data.models import Course
from engine.constraint_checker import annotate_schedule_violations, count_soft_violations
from engine.demand_metrics import build_demand_metrics
from engine.fixed_reconciliation import (
    adjusted_courses_after_exact_matches,
    export_fixed_reconciliation_report,
    reconcile_fixed_sessions,
)
from engine.fixed_issue_analysis import export_fixed_issue_workbooks
from engine.input_readiness import build_input_readiness_result, export_input_readiness_report
from engine.preflight_validator import run_preflight_checks
from engine.remarks_interpreter import export_remarks_audit
from engine.resource_audit import audit_resources
from engine.unscheduled_diagnostics import diagnose_unscheduled_assignments, export_unscheduled_diagnostics
from generator.scheduler import generate_schedule
from generator.fixed_scheduler import create_fixed_assignments, validate_fixed_assignments
from main import (
    _completed_optimisation_summary,
    _count_current_hard_violations,
    _count_scheduled_hard_violations,
    _count_weighted_soft_score,
    _fixed_requirement_courses,
    _restore_unscheduled_reasons,
    _skipped_optimisation_summary,
    _snapshot_unscheduled_reasons,
    export_outputs,
)
from optimiser.local_search import optimise_schedule_with_stats
from output.report_exporter import export_preflight_report, export_run_manifest, export_run_summary, export_stakeholder_views
from output.submission_validator import (
    export_submission_ready_schedule,
    export_template2_validation_report,
    validate_template2_submission,
)
from validate_release import validate_release

ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class PipelineOptions:
    """Runtime options for a timetable pipeline run."""

    scope: str = "eng"
    consolidated_schedule_path: Path | None = None
    # Compatibility alias: when supplied, input_path means consolidated Template 1 requirements input.
    input_path: Path | None = None
    room_source_path: Path | None = None
    common_module_path: Path = DEFAULT_COMMON_MODULE_FILE
    template2_output_template_path: Path = DEFAULT_TEMPLATE2_FILE
    # Compatibility alias for callers created before explicit workbook roles were added.
    room_path: Path | None = None
    run_optimisation: bool = False
    max_iterations: int = 5
    optimisation_time_limit: float | None = None
    optimisation_patience: int | None = None
    max_candidate_patterns: int | None = 300
    max_retry_assignments: int | None = 50
    skip_unscheduled_diagnostics: bool = True
    max_diagnostic_assignments: int | None = None
    progress_interval: int = 25
    skip_preflight: bool = False
    audit_demand_metrics: bool = True
    enable_remark_interpretation: bool = True


@dataclass(slots=True)
class PipelineResult:
    """Headline result values returned to the desktop UI."""

    required_occurrences: int
    scheduled_occurrences: int
    unscheduled_occurrences: int
    coverage_percent: float
    scheduled_hard_violations: int
    online_required: int
    online_scheduled: int
    dsc_included: bool
    validation_passed: bool
    optimisation_status: str
    output_paths: dict[str, Path]


class PipelineCancelled(RuntimeError):
    """Raised when a cooperative UI cancellation request is observed."""


def _emit(callback: ProgressCallback | None, message: str) -> None:
    """Send one progress message to the caller."""
    if callback is not None:
        callback(message)


def _check_cancel(cancel_event: Event | None) -> None:
    """Raise if the caller requested cancellation."""
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled("Run cancelled between pipeline stages.")


def _consolidated_schedule_path(options: PipelineOptions) -> Path | None:
    """Return selected Template 1 path, including the compatibility alias."""
    return options.consolidated_schedule_path or options.input_path


def _room_source_path(options: PipelineOptions) -> Path:
    """Return the configured room source path, including the compatibility alias."""
    return options.room_source_path or options.room_path or DEFAULT_ROOM_FILE


def _load_courses_from_path(path: Path | None, scope: str, common_modules: set[str]) -> tuple[list[Course], LoaderReport]:
    """Load courses from selected Template 1 input or existing CLI defaults."""
    if path is None:
        if scope == "eng" and DEFAULT_ENGINEERING_FOLDER.exists():
            return load_courses_from_folder(DEFAULT_ENGINEERING_FOLDER, common_modules=common_modules)
        courses, workbook_report = load_courses_from_requirements(DEFAULT_COURSE_FILE, common_modules=common_modules)
        report = LoaderReport()
        report.add(workbook_report)
        return courses, report

    if path.is_dir():
        return load_courses_from_folder(path, common_modules=common_modules)
    courses, workbook_report = load_consolidated_schedule_with_report(path, common_modules=common_modules)
    report = LoaderReport()
    report.add(workbook_report)
    return courses, report


def _args_namespace(options: PipelineOptions) -> SimpleNamespace:
    """Return an argparse-like namespace for existing summary helpers."""
    return SimpleNamespace(
        scope=options.scope,
        skip_optimisation=not options.run_optimisation,
        max_iterations=options.max_iterations,
        optimisation_time_limit=options.optimisation_time_limit,
        optimisation_patience=options.optimisation_patience,
        max_candidate_patterns=options.max_candidate_patterns,
        max_retry_assignments=options.max_retry_assignments,
        skip_unscheduled_diagnostics=options.skip_unscheduled_diagnostics,
        max_diagnostic_assignments=options.max_diagnostic_assignments,
        progress_interval=options.progress_interval,
        audit_demand_metrics=options.audit_demand_metrics,
        disable_remark_interpretation=not options.enable_remark_interpretation,
    )


def _metadata(options: PipelineOptions) -> dict[str, object]:
    """Return run metadata for report workbooks."""
    args = _args_namespace(options)
    return {
        "scope": args.scope,
        "skip_optimisation": args.skip_optimisation,
        "max_iterations": args.max_iterations,
        "optimisation_time_limit": args.optimisation_time_limit,
        "optimisation_patience": args.optimisation_patience,
        "max_candidate_patterns": args.max_candidate_patterns,
        "max_retry_assignments": args.max_retry_assignments,
        "skip_unscheduled_diagnostics": args.skip_unscheduled_diagnostics,
        "max_diagnostic_assignments": args.max_diagnostic_assignments,
        "progress_interval": args.progress_interval,
        "audit_demand_metrics": args.audit_demand_metrics,
        "remark_interpretation_enabled": not args.disable_remark_interpretation,
        "input_workbook": str(_consolidated_schedule_path(options) or DEFAULT_ENGINEERING_FOLDER),
        "consolidated_schedule_path": str(_consolidated_schedule_path(options) or DEFAULT_ENGINEERING_FOLDER),
        "output_template": str(options.template2_output_template_path),
        "template2_output_template_path": str(options.template2_output_template_path),
        "room_source_path": str(_room_source_path(options)),
        "common_module_path": str(options.common_module_path),
    }


def _dsc_included(courses: list[Course]) -> bool:
    """Return True when DSC appears in Engineering input data."""
    return any("DSC" in " ".join([course.module_code, course.prog_yr, course.source_file]).upper() for course in courses)


def run_timetable_pipeline(
    options: PipelineOptions,
    progress_callback: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> PipelineResult:
    """Run the existing timetable pipeline and return UI-friendly metrics."""
    _emit(progress_callback, "Loading input")
    common_modules = load_common_modules(options.common_module_path)
    courses, loader_report = _load_courses_from_path(_consolidated_schedule_path(options), options.scope, common_modules)
    rooms = load_rooms_from_csv(_room_source_path(options))
    export_loader_report(loader_report, DEFAULT_LOADER_REPORT_FILE)
    _check_cancel(cancel_event)

    if options.skip_preflight:
        _emit(progress_callback, "Skipping preflight checks")
    else:
        _emit(progress_callback, "Running preflight checks")
        preflight_issues = run_preflight_checks(courses, rooms)
        export_preflight_report(preflight_issues, DEFAULT_PREFLIGHT_REPORT_FILE)
    _check_cancel(cancel_event)

    fixed_sessions = []
    fixed_assignments: list = []
    schedule_courses = courses
    demand_courses = courses
    if options.scope == "eng" and DEFAULT_FIXED_SESSION_FILE.exists():
        _emit(progress_callback, "Checking fixed-session requirements")
        fixed_sessions, fixed_loader_report = load_fixed_sessions(DEFAULT_FIXED_SESSION_FILE)
        export_fixed_sessions_audit(fixed_loader_report, DEFAULT_FIXED_SESSIONS_AUDIT_FILE)
        reconciliation_report = reconcile_fixed_sessions(fixed_sessions, courses, fixed_loader_report)
        export_fixed_reconciliation_report(reconciliation_report, DEFAULT_FIXED_RECONCILIATION_FILE)
        fixed_assignments, fixed_mapping_issues = create_fixed_assignments(fixed_sessions, rooms)
        fixed_conflict_issues = validate_fixed_assignments(fixed_assignments)
        readiness = build_input_readiness_result(
            fixed_loader_report=fixed_loader_report,
            reconciliation_report=reconciliation_report,
            fixed_assignment_issues=fixed_mapping_issues + fixed_conflict_issues,
            loader_report=loader_report,
        )
        export_input_readiness_report(readiness, DEFAULT_INPUT_READINESS_REPORT_FILE)
        export_fixed_issue_workbooks(
            fixed_sessions=fixed_sessions,
            courses=courses,
            assignments=fixed_assignments,
            rooms=rooms,
            loader_report=fixed_loader_report,
            reconciliation_report=reconciliation_report,
            mapping_issues=fixed_mapping_issues,
            conflict_issues=fixed_conflict_issues,
            root_cause_path=DEFAULT_FIXED_ROOT_CAUSE_FILE,
            conflict_triage_path=DEFAULT_FIXED_CONFLICT_TRIAGE_FILE,
            supervisor_queries_path=DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE,
        )
        if not readiness.ready:
            raise ValueError(readiness.message)
        schedule_courses = adjusted_courses_after_exact_matches(courses, reconciliation_report)
        demand_courses = schedule_courses + _fixed_requirement_courses(fixed_assignments)
    _check_cancel(cancel_event)

    _emit(progress_callback, "Generating timetable")

    def _course_progress(position: int, total: int, course: Course) -> None:
        _emit(progress_callback, f"Generating timetable: {position}/{total} {course.module_code} {course.activity}")

    initial_schedule = generate_schedule(
        schedule_courses,
        rooms,
        initial_assignments=fixed_assignments,
        progress_callback=_course_progress,
        progress_interval=options.progress_interval,
        max_retry_assignments=options.max_retry_assignments,
        max_candidate_patterns=options.max_candidate_patterns,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    initial_reasons = _snapshot_unscheduled_reasons(initial_schedule)
    annotate_schedule_violations(
        initial_schedule,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    initial_soft = count_soft_violations(
        initial_schedule,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    initial_soft_score = _count_weighted_soft_score(
        initial_schedule,
        options.enable_remark_interpretation,
    )
    _restore_unscheduled_reasons(initial_schedule, initial_reasons)

    args = _args_namespace(options)
    final_schedule = initial_schedule
    optimisation_metrics = _skipped_optimisation_summary(args, initial_soft, initial_soft_score, demand_courses, initial_schedule, rooms)
    if options.run_optimisation:
        _check_cancel(cancel_event)
        _emit(progress_callback, "Running optimiser")
        started = perf_counter()
        result = optimise_schedule_with_stats(
            initial_schedule,
            rooms,
            max_iterations=options.max_iterations,
            time_limit_seconds=options.optimisation_time_limit,
            patience=options.optimisation_patience,
            enable_remark_interpretation=options.enable_remark_interpretation,
        )
        runtime_seconds = perf_counter() - started
        final_schedule = result.assignments
        final_reasons = _snapshot_unscheduled_reasons(final_schedule)
        final_soft = count_soft_violations(
            final_schedule,
            enable_remark_interpretation=options.enable_remark_interpretation,
        )
        final_soft_score = _count_weighted_soft_score(
            final_schedule,
            options.enable_remark_interpretation,
        )
        _restore_unscheduled_reasons(final_schedule, final_reasons)
        optimisation_metrics = _completed_optimisation_summary(
            args,
            initial_schedule,
            final_schedule,
            demand_courses,
            rooms,
            initial_soft,
            final_soft,
            initial_soft_score,
            final_soft_score,
            runtime_seconds,
            result.iterations_completed,
            result.status,
            result.stop_reason,
        )
    _check_cancel(cancel_event)

    _emit(progress_callback, "Generating stakeholder reports")
    metadata = _metadata(options)
    export_run_summary(
        final_schedule,
        DEFAULT_RUN_SUMMARY_FILE,
        metadata=metadata,
        demand_courses=demand_courses,
        input_course_records=len(demand_courses),
        rooms=rooms,
        room_source_path=_room_source_path(options),
        optimisation_summary=optimisation_metrics,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    export_stakeholder_views(
        final_schedule,
        rooms,
        DEFAULT_STAKEHOLDER_VIEWS_FILE,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    export_remarks_audit(demand_courses, DEFAULT_REMARKS_AUDIT_FILE)

    if not options.skip_unscheduled_diagnostics:
        report = diagnose_unscheduled_assignments(
            final_schedule,
            rooms,
            max_diagnostic_assignments=options.max_diagnostic_assignments,
            enable_remark_interpretation=options.enable_remark_interpretation,
        )
        export_unscheduled_diagnostics(report, DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE)
    _check_cancel(cancel_event)

    _emit(progress_callback, "Exporting proposed timetable")
    output_paths = export_outputs(
        final_schedule,
        options.scope,
        template2_path=options.template2_output_template_path,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    if options.scope == "eng" and DEFAULT_FIXED_SESSION_FILE.exists():
        export_submission_ready_schedule(
            final_schedule,
            DEFAULT_TEMPLATE2_SUBMISSION_FILE,
            template2_path=options.template2_output_template_path,
            enable_remark_interpretation=options.enable_remark_interpretation,
        )
        template2_validation = validate_template2_submission(
            DEFAULT_TEMPLATE2_SUBMISSION_FILE,
            demand_courses,
            fixed_sessions,
            final_schedule,
            rooms,
            options.template2_output_template_path,
        )
        export_template2_validation_report(template2_validation, DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE)
        output_paths["submission_ready_timetable"] = DEFAULT_TEMPLATE2_SUBMISSION_FILE
        output_paths["template2_submission_validation"] = DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE
    output_paths.update(
        {
            "loader_report": DEFAULT_LOADER_REPORT_FILE,
            "run_summary": DEFAULT_RUN_SUMMARY_FILE,
            "stakeholder_views": DEFAULT_STAKEHOLDER_VIEWS_FILE,
            "remarks_audit": DEFAULT_REMARKS_AUDIT_FILE,
        }
    )
    if not options.skip_preflight:
        output_paths["preflight_report"] = DEFAULT_PREFLIGHT_REPORT_FILE
    if options.scope == "eng" and DEFAULT_FIXED_SESSION_FILE.exists():
        output_paths["fixed_sessions_audit"] = DEFAULT_FIXED_SESSIONS_AUDIT_FILE
        output_paths["fixed_reconciliation"] = DEFAULT_FIXED_RECONCILIATION_FILE
        output_paths["input_readiness_report"] = DEFAULT_INPUT_READINESS_REPORT_FILE
        output_paths["fixed_issue_root_cause_analysis"] = DEFAULT_FIXED_ROOT_CAUSE_FILE
        output_paths["fixed_conflict_triage"] = DEFAULT_FIXED_CONFLICT_TRIAGE_FILE
        output_paths["supervisor_fixed_session_queries"] = DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE
    if not options.skip_unscheduled_diagnostics:
        output_paths["unscheduled_diagnostics"] = DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE

    _emit(progress_callback, "Validating outputs")
    export_run_manifest(
        demand_courses,
        final_schedule,
        DEFAULT_RUN_MANIFEST_FILE,
        metadata=metadata,
        rooms=rooms,
        output_files=output_paths,
        template2_path=options.template2_output_template_path,
        enable_remark_interpretation=options.enable_remark_interpretation,
    )
    output_paths["run_manifest"] = DEFAULT_RUN_MANIFEST_FILE
    output_paths["proposed_template2"] = Path(output_paths["timetable"])
    output_paths["exception_queue"] = DEFAULT_STAKEHOLDER_VIEWS_FILE
    output_paths["output_folder"] = OUTPUT_DIR

    demand = build_demand_metrics(demand_courses, final_schedule, input_course_records=len(demand_courses))
    resource_audit = audit_resources(demand_courses, rooms, final_schedule, room_source_path=_room_source_path(options))
    validation = validate_release(
        DEFAULT_RUN_SUMMARY_FILE,
        Path(output_paths["timetable"]),
        DEFAULT_STAKEHOLDER_VIEWS_FILE,
        DEFAULT_RUN_MANIFEST_FILE,
    )
    _emit(progress_callback, "Completed")
    return PipelineResult(
        required_occurrences=demand.required_teaching_occurrences,
        scheduled_occurrences=demand.scheduled_teaching_occurrences,
        unscheduled_occurrences=demand.unscheduled_teaching_occurrences,
        coverage_percent=demand.coverage_rate_percent,
        scheduled_hard_violations=_count_scheduled_hard_violations(final_schedule),
        online_required=resource_audit.required_online_teaching_occurrences,
        online_scheduled=resource_audit.scheduled_online_teaching_occurrences,
        dsc_included=_dsc_included(courses),
        validation_passed=validation.passed,
        optimisation_status=str(optimisation_metrics.get("status", "Skipped")),
        output_paths={key: Path(value) for key, value in output_paths.items()},
    )
