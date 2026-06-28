"""Run the full SIT timetabling pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_COURSE_FILE,
    DEFAULT_ENGINEERING_FOLDER,
    DEFAULT_FIXED_RECONCILIATION_FILE,
    DEFAULT_FIXED_CONFLICT_TRIAGE_FILE,
    DEFAULT_FIXED_RESOLUTION_AUDIT_FILE,
    DEFAULT_FIXED_RESOLUTION_TEMPLATE_FILE,
    DEFAULT_FIXED_ROOT_CAUSE_FILE,
    DEFAULT_FIXED_SESSION_FILE,
    DEFAULT_FIXED_SESSION_INTEGRITY_FILE,
    DEFAULT_FIXED_SESSIONS_AUDIT_FILE,
    DEFAULT_GUARDED_GENERATION_REPORT_FILE,
    DEFAULT_INPUT_READINESS_REPORT_FILE,
    DEFAULT_LOCATION_MAPPING_EVIDENCE_FILE,
    DEFAULT_LOADER_REPORT_FILE,
    DEFAULT_PROGRAMME_VISUALS_FILE,
    DEFAULT_PREFLIGHT_REPORT_FILE,
    DEFAULT_REMARKS_AUDIT_FILE,
    DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE,
    DEFAULT_ROOM_FILE,
    DEFAULT_ROOM_VISUALS_FILE,
    DEFAULT_RUN_MANIFEST_FILE,
    DEFAULT_RUN_SUMMARY_FILE,
    DEFAULT_REMARKS_COMPARISON_FILE,
    DEFAULT_STAKEHOLDER_VIEWS_FILE,
    DEFAULT_SUPERVISOR_CLARIFICATION_PACK_FILE,
    DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE,
    DEFAULT_TEMPLATE2_ALL_VALID_FILE,
    DEFAULT_TEMPLATE2_EXCLUSION_AUDIT_FILE,
    DEFAULT_TEMPLATE2_PROGRAMME_YEAR_RECONCILIATION_FILE,
    DEFAULT_TEMPLATE2_SUBMISSION_FILE,
    DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE,
    DEFAULT_TEMPLATE2_FILE,
    DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE,
    DEFAULT_TUTOR_VISUALS_FILE,
    OUTPUT_DIR,
)
from data.fixed_sessions import export_fixed_sessions_audit, load_fixed_sessions
from data.loader import (
    LoaderReport,
    export_loader_report,
    load_common_modules,
    load_courses_from_folder,
    load_courses_from_requirements,
    load_rooms_from_csv,
)
from data.models import Course
from engine.constraint_checker import annotate_schedule_violations, count_soft_violations, soft_violation_breakdown, weighted_soft_score
from engine.demand_metrics import build_demand_metrics
from engine.fixed_reconciliation import (
    adjusted_courses_after_exact_matches,
    export_fixed_reconciliation_report,
    reconcile_fixed_sessions,
)
from engine.fixed_issue_analysis import export_fixed_issue_workbooks
from engine.guarded_generation import (
    build_guarded_generation_state,
    build_programme_completeness_rows,
    complete_programme_set,
    export_guarded_generation_report,
    quarantined_requirement_courses,
)
from engine.input_readiness import build_input_readiness_result, export_input_readiness_report
from engine.preflight_validator import run_preflight_checks
from engine.remarks_comparison import export_remarks_coverage_comparison
from engine.remarks_interpreter import courses_with_effective_remark_durations, export_remarks_audit
from engine.resource_audit import audit_resources
from engine.unscheduled_diagnostics import (
    UnscheduledDiagnosticsReport,
    diagnose_unscheduled_assignments,
    export_unscheduled_diagnostics,
)
from generator.scheduler import generate_schedule
from generator.fixed_scheduler import create_fixed_assignments, validate_fixed_assignments
from optimiser.local_search import optimise_schedule, optimise_schedule_with_stats
from output.exporter import export_schedule, export_violations
from output.fixed_session_integrity import export_fixed_session_integrity_report
from output.report_exporter import export_preflight_report, export_run_manifest, export_run_summary, export_stakeholder_views
from output.submission_validator import (
    export_all_valid_scheduled_schedule,
    export_submission_ready_schedule,
    export_template2_exclusion_audit,
    export_template2_programme_year_reconciliation,
    export_template2_validation_report,
    submission_assignments,
    validate_template2_submission,
)
from output.timetable_visualizer import export_timetable_visuals, export_visualisation_failure_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for DSC or Engineering-cluster runs."""
    parser = argparse.ArgumentParser(description="SIT timetabling prototype")
    parser.add_argument("--scope", choices=["dsc", "eng"], default="dsc", help="Dataset scope to run")
    parser.add_argument("--max-iterations", type=int, default=8, help="Local-search optimisation iterations")
    parser.add_argument("--optimisation-time-limit", type=float, default=None, help="Maximum optimiser runtime in seconds")
    parser.add_argument("--optimisation-patience", type=int, default=None, help="Stop after this many non-improving optimiser iterations")
    parser.add_argument("--skip-optimisation", action="store_true", help="Generate only the greedy timetable")
    parser.add_argument("--max-retry-assignments", type=int, default=None, help="Maximum unscheduled assignments to retry")
    parser.add_argument("--progress-interval", type=int, default=25, help="Engineering progress update interval")
    parser.add_argument(
        "--skip-unscheduled-diagnostics",
        action="store_true",
        help="Skip unscheduled diagnostics generation and export",
    )
    parser.add_argument(
        "--max-candidate-patterns",
        type=int,
        default=None,
        help="Maximum room/day/start candidate patterns to check per course",
    )
    parser.add_argument(
        "--max-diagnostic-assignments",
        type=int,
        default=None,
        help="Maximum unscheduled assignments to run detailed diagnostics for",
    )
    parser.add_argument("--skip-preflight", action="store_true", help="Skip input preflight validation report")
    parser.add_argument("--audit-demand-metrics", action="store_true", help="Print invariant demand coverage metrics")
    parser.add_argument(
        "--disable-remark-interpretation",
        action="store_true",
        help="Disable deterministic remarks processing for regression comparison",
    )
    return parser.parse_args(argv)


def load_courses(scope: str, common_modules: set[str]) -> tuple[list[Course], LoaderReport]:
    """Load either DSC-only or Engineering-cluster requirement files."""
    if scope == "eng" and DEFAULT_ENGINEERING_FOLDER.exists():
        return load_courses_from_folder(DEFAULT_ENGINEERING_FOLDER, common_modules=common_modules)
    courses, workbook_report = load_courses_from_requirements(DEFAULT_COURSE_FILE, common_modules=common_modules)
    report = LoaderReport()
    report.add(workbook_report)
    return courses, report


def _report_schedule_metrics(label: str, assignments: list) -> None:
    """Print schedule counts split between scheduled and unscheduled items."""
    scheduled = [item for item in assignments if item.room is not None and item.timeslot is not None]
    unscheduled = [item for item in assignments if item.room is None or item.timeslot is None]
    scheduled_hard = sum(len(item.hard_violations) for item in scheduled)
    unscheduled_hard = sum(len(item.hard_violations) for item in unscheduled)
    print(f"{label} scheduled assignments: {len(scheduled)}")
    print(f"{label} unscheduled assignments: {len(unscheduled)}")
    print(f"{label} hard violations on scheduled assignments: {scheduled_hard}")
    print(f"{label} unscheduled feasibility failures: {len(unscheduled)}")
    print(f"{label} unscheduled hard violations: {unscheduled_hard}")


def _print_unscheduled_reason_summary(report: UnscheduledDiagnosticsReport) -> None:
    """Print the most common reasons assignments remain unscheduled."""
    reason_counts = report.reason_counts().most_common(5)
    if not reason_counts:
        print("Top unscheduled failure reasons: none")
        return
    print("Top unscheduled failure reasons:")
    for reason, count in reason_counts:
        print(f"  {reason}: {count}")


def _snapshot_unscheduled_reasons(assignments: list) -> dict[int, list[str]]:
    """Capture existing unscheduled reasons before metric annotation."""
    return {
        id(assignment): list(assignment.hard_violations)
        for assignment in assignments
        if (assignment.room is None or assignment.timeslot is None) and assignment.hard_violations
    }


def _restore_unscheduled_reasons(assignments: list, reasons: dict[int, list[str]]) -> None:
    """Restore scheduler-provided unscheduled reasons after metric annotation."""
    for assignment in assignments:
        if assignment.room is None or assignment.timeslot is None:
            original = reasons.get(id(assignment))
            if original:
                assignment.hard_violations = original


def _count_current_hard_violations(assignments: list) -> int:
    """Count currently recorded hard violations without re-annotating."""
    return sum(len(assignment.hard_violations) for assignment in assignments)


def _count_scheduled_hard_violations(assignments: list) -> int:
    """Count hard violations only on scheduled timetable entries."""
    return sum(
        len(assignment.hard_violations)
        for assignment in assignments
        if assignment.room is not None and assignment.timeslot is not None
    )


def _remark_interpretation_enabled(args: argparse.Namespace) -> bool:
    """Return whether remark rules should affect scheduling and scoring."""
    return not args.disable_remark_interpretation


def _count_weighted_soft_score(assignments: list, enable_remark_interpretation: bool = True) -> int:
    """Count weighted soft score without replacing unscheduled reasons."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    score = weighted_soft_score(
        assignments,
        enable_remark_interpretation=enable_remark_interpretation,
    )
    _restore_unscheduled_reasons(assignments, reasons)
    return score


def _soft_rule_breakdown_metrics(
    prefix: str,
    assignments: list,
    enable_remark_interpretation: bool = True,
) -> dict[str, object]:
    """Return per-soft-rule counts with stable metric labels."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    breakdown = soft_violation_breakdown(
        assignments,
        enable_remark_interpretation=enable_remark_interpretation,
    )
    _restore_unscheduled_reasons(assignments, reasons)
    return {f"{prefix} soft rule - {rule}": count for rule, count in breakdown.items()}


def _run_metadata(args: argparse.Namespace) -> dict[str, object]:
    """Return CLI settings for run-summary evidence."""
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
    }


def _print_demand_audit(courses: list[Course], assignments: list) -> None:
    """Print invariant demand metrics for Engineering evidence."""
    metrics = build_demand_metrics(courses, assignments, input_course_records=len(courses))
    status = "PASS" if metrics.is_consistent else "FAIL"
    print("\nDemand metric audit:")
    print(f"  input course records: {metrics.input_course_records}")
    print(f"  consolidated course requirements: {metrics.consolidated_course_requirements}")
    print(f"  required teaching occurrences: {metrics.required_teaching_occurrences}")
    print(f"  scheduled teaching occurrences: {metrics.scheduled_teaching_occurrences}")
    print(f"  unscheduled teaching occurrences: {metrics.unscheduled_teaching_occurrences}")
    print(f"  coverage rate: {metrics.coverage_rate_percent:.2f}%")
    print(f"  consistency status: {status}")


def _fixed_requirement_courses(assignments: list) -> list[Course]:
    """Return one fixed requirement course per fixed source row."""
    courses: dict[str, Course] = {}
    weeks_by_source: dict[str, set[int]] = {}
    for assignment in assignments:
        if not assignment.is_fixed or not assignment.fixed_source:
            continue
        courses.setdefault(assignment.fixed_source, assignment.course)
        if assignment.timeslot is not None:
            weeks_by_source.setdefault(assignment.fixed_source, set()).add(assignment.timeslot.week)
    result: list[Course] = []
    for source, course in courses.items():
        copy = Course(
            module_code=course.module_code,
            activity=course.activity,
            prog_yr=course.prog_yr,
            class_size=course.class_size,
            delivery_mode=course.delivery_mode,
            teaching_weeks=sorted(weeks_by_source.get(source, set(course.teaching_weeks))),
            week_pattern=course.week_pattern,
            staff_ids=list(course.staff_ids),
            duration_hrs=course.duration_hrs,
            is_common_module=course.is_common_module,
            staff_names=list(course.staff_names),
            remarks=course.remarks,
            source_file=course.source_file,
            group_ids=list(course.group_ids),
            source_sheet=course.source_sheet,
            source_row=course.source_row,
            remark_requirements=course.remark_requirements,
            is_fixed_requirement=True,
            fixed_source=course.fixed_source,
        )
        result.append(copy)
    return result


def _skipped_optimisation_summary(
    args: argparse.Namespace,
    initial_soft: int,
    initial_soft_score: int,
    courses: list[Course],
    assignments: list,
    rooms: list,
) -> dict[str, object]:
    """Return optimisation evidence rows for skipped optimisation."""
    demand = build_demand_metrics(courses, assignments, input_course_records=len(courses))
    resource_audit = audit_resources(courses, rooms, assignments)
    scheduled_hard = _count_scheduled_hard_violations(assignments)
    remarks_enabled = _remark_interpretation_enabled(args)
    summary = {
        "optimisation_enabled": "No",
        "status": "Skipped",
        "requested_max_iterations": args.max_iterations,
        "time_limit_seconds": args.optimisation_time_limit,
        "patience": args.optimisation_patience,
        "iterations_completed": 0,
        "runtime_seconds": 0.0,
        "scheduled_teaching_occurrences_before": demand.scheduled_teaching_occurrences,
        "scheduled_teaching_occurrences_after": demand.scheduled_teaching_occurrences,
        "required_teaching_occurrences_before": demand.required_teaching_occurrences,
        "required_teaching_occurrences_after": demand.required_teaching_occurrences,
        "online_scheduled_occurrences_before": resource_audit.scheduled_online_teaching_occurrences,
        "online_scheduled_occurrences_after": resource_audit.scheduled_online_teaching_occurrences,
        "online_required_occurrences_before": resource_audit.required_online_teaching_occurrences,
        "online_required_occurrences_after": resource_audit.required_online_teaching_occurrences,
        "hard_violations_before": scheduled_hard,
        "hard_violations_after": scheduled_hard,
        "soft_violations_before": initial_soft,
        "soft_violations_after": initial_soft,
        "weighted_soft_score_before": initial_soft_score,
        "weighted_soft_score_after": initial_soft_score,
        "absolute_soft_violation_improvement": 0,
        "percentage_soft_violation_improvement": 0.0,
        "absolute_weighted_soft_score_improvement": 0,
        "percentage_weighted_soft_score_improvement": 0.0,
        "coverage_unchanged_status": "PASS",
        "hard_safety_status": "PASS" if scheduled_hard == 0 else "FAIL",
        "soft_score_not_worsened_status": "PASS",
        "online_coverage_preserved_status": "PASS",
    }
    summary.update(_soft_rule_breakdown_metrics("Before", assignments, remarks_enabled))
    summary.update(_soft_rule_breakdown_metrics("After", assignments, remarks_enabled))
    return summary


def _completed_optimisation_summary(
    args: argparse.Namespace,
    before: list,
    after: list,
    courses: list[Course],
    rooms: list,
    initial_soft: int,
    final_soft: int,
    initial_soft_score: int,
    final_soft_score: int,
    runtime_seconds: float,
    iterations_completed: int,
    optimisation_status: str,
    stop_reason: str,
) -> dict[str, object]:
    """Return optimiser acceptance metrics for the run summary."""
    before_demand = build_demand_metrics(courses, before, input_course_records=len(courses))
    after_demand = build_demand_metrics(courses, after, input_course_records=len(courses))
    before_audit = audit_resources(courses, rooms, before)
    after_audit = audit_resources(courses, rooms, after)
    improvement = initial_soft - final_soft
    improvement_pct = (improvement / initial_soft * 100) if initial_soft else 0.0
    score_improvement = initial_soft_score - final_soft_score
    score_improvement_pct = (score_improvement / initial_soft_score * 100) if initial_soft_score else 0.0
    coverage_unchanged = (
        before_demand.required_teaching_occurrences == after_demand.required_teaching_occurrences
        and before_demand.scheduled_teaching_occurrences == after_demand.scheduled_teaching_occurrences
        and before_demand.unscheduled_teaching_occurrences == after_demand.unscheduled_teaching_occurrences
    )
    online_preserved = (
        before_audit.required_online_teaching_occurrences == after_audit.required_online_teaching_occurrences
        and before_audit.scheduled_online_teaching_occurrences == after_audit.scheduled_online_teaching_occurrences
    )
    hard_after = _count_scheduled_hard_violations(after)
    remarks_enabled = _remark_interpretation_enabled(args)
    summary = {
        "optimisation_enabled": "Yes",
        "status": optimisation_status,
        "stop_reason": stop_reason,
        "requested_max_iterations": args.max_iterations,
        "time_limit_seconds": args.optimisation_time_limit,
        "patience": args.optimisation_patience,
        "iterations_completed": iterations_completed,
        "runtime_seconds": round(runtime_seconds, 3),
        "scheduled_teaching_occurrences_before": before_demand.scheduled_teaching_occurrences,
        "scheduled_teaching_occurrences_after": after_demand.scheduled_teaching_occurrences,
        "required_teaching_occurrences_before": before_demand.required_teaching_occurrences,
        "required_teaching_occurrences_after": after_demand.required_teaching_occurrences,
        "online_scheduled_occurrences_before": before_audit.scheduled_online_teaching_occurrences,
        "online_scheduled_occurrences_after": after_audit.scheduled_online_teaching_occurrences,
        "online_required_occurrences_before": before_audit.required_online_teaching_occurrences,
        "online_required_occurrences_after": after_audit.required_online_teaching_occurrences,
        "hard_violations_before": _count_scheduled_hard_violations(before),
        "hard_violations_after": hard_after,
        "soft_violations_before": initial_soft,
        "soft_violations_after": final_soft,
        "weighted_soft_score_before": initial_soft_score,
        "weighted_soft_score_after": final_soft_score,
        "absolute_soft_violation_improvement": improvement,
        "percentage_soft_violation_improvement": improvement_pct,
        "absolute_weighted_soft_score_improvement": score_improvement,
        "percentage_weighted_soft_score_improvement": score_improvement_pct,
        "coverage_unchanged_status": "PASS" if coverage_unchanged else "FAIL",
        "hard_safety_status": "PASS" if hard_after == 0 else "FAIL",
        "soft_score_not_worsened_status": "PASS" if score_improvement >= 0 else "FAIL",
        "online_coverage_preserved_status": "PASS" if online_preserved else "FAIL",
    }
    summary.update(_soft_rule_breakdown_metrics("Before", before, remarks_enabled))
    summary.update(_soft_rule_breakdown_metrics("After", after, remarks_enabled))
    return summary


def export_outputs(
    assignments: list,
    scope: str,
    template2_path=None,
    enable_remark_interpretation: bool = True,
    output_dir=None,
    timetable_filename: str | None = None,
) -> dict[str, object]:
    """Export timetable and violation reports for the selected scope."""
    template2_path = template2_path or DEFAULT_TEMPLATE2_FILE
    target_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = "engineering_cluster" if scope == "eng" else "dsc"
    timetable_path = target_dir / (timetable_filename or f"final_timetable_{suffix}.xlsx")
    violation_path = target_dir / f"violation_report_{suffix}.xlsx"
    export_schedule(
        submission_assignments(assignments),
        timetable_path,
        template2_path=template2_path,
        enable_remark_interpretation=enable_remark_interpretation,
    )
    export_violations(
        assignments,
        violation_path,
        enable_remark_interpretation=enable_remark_interpretation,
    )
    # Keep the original filenames for demo convenience when running DSC mode.
    if scope == "dsc" and output_dir is None:
        export_schedule(
            submission_assignments(assignments),
            OUTPUT_DIR / "final_timetable.xlsx",
            template2_path=template2_path,
            enable_remark_interpretation=enable_remark_interpretation,
        )
        export_violations(
            assignments,
            OUTPUT_DIR / "violation_report.xlsx",
            enable_remark_interpretation=enable_remark_interpretation,
        )
    print(f"Saved: {timetable_path}")
    print(f"Saved: {violation_path}")
    return {"timetable": timetable_path, "violations": violation_path}


def main() -> None:
    """Load data, generate timetable, optimise, and export reports."""
    args = parse_args()
    print("Loading input data...")
    common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
    courses, loader_report = load_courses(args.scope, common_modules)
    rooms = load_rooms_from_csv(DEFAULT_ROOM_FILE)
    export_loader_report(loader_report, DEFAULT_LOADER_REPORT_FILE)

    print(f"Scope: {args.scope}")
    print(f"Courses loaded: {len(courses)}")
    print(f"Rooms loaded: {len(rooms)}")
    print(f"Common modules loaded: {len(common_modules)}")
    print(f"Skipped workbooks: {loader_report.skipped_workbooks}")
    print(f"Loader report: {DEFAULT_LOADER_REPORT_FILE}")
    for workbook in loader_report.workbooks:
        if workbook.status != "parsed":
            missing = f" | missing: {', '.join(workbook.missing_columns)}" if workbook.missing_columns else ""
            print(
                f"Loader notice: {workbook.file_path} [{workbook.sheet_name}] - "
                f"{workbook.status} - {workbook.reason}{missing}"
            )

    if args.skip_preflight:
        print("Skipped preflight validation.")
    else:
        preflight_issues = run_preflight_checks(courses, rooms)
        export_preflight_report(preflight_issues, DEFAULT_PREFLIGHT_REPORT_FILE)
        print(f"Preflight issues: {len(preflight_issues)}")
        print(f"Saved: {DEFAULT_PREFLIGHT_REPORT_FILE}")

    fixed_sessions = []
    fixed_assignments: list = []
    fixed_conflict_issues: list[dict[str, object]] = []
    guarded_state = None
    schedule_courses = courses
    demand_courses = courses
    programme_completeness_rows: list[dict[str, object]] = []
    if args.scope == "eng" and DEFAULT_FIXED_SESSION_FILE.exists():
        print("\nValidating fixed-session requirements...")
        fixed_sessions, fixed_loader_report = load_fixed_sessions(DEFAULT_FIXED_SESSION_FILE)
        export_fixed_sessions_audit(fixed_loader_report, DEFAULT_FIXED_SESSIONS_AUDIT_FILE)
        reconciliation_report = reconcile_fixed_sessions(fixed_sessions, courses, fixed_loader_report)
        export_fixed_reconciliation_report(reconciliation_report, DEFAULT_FIXED_RECONCILIATION_FILE)
        fixed_assignments, fixed_mapping_issues = create_fixed_assignments(fixed_sessions, rooms)
        fixed_conflict_issues = validate_fixed_assignments(fixed_assignments)
        guarded_state = build_guarded_generation_state(
            courses=courses,
            rooms_loaded=len(rooms),
            fixed_sessions=fixed_sessions,
            fixed_loader_report=fixed_loader_report,
            reconciliation_report=reconciliation_report,
            fixed_assignments=fixed_assignments,
            fixed_assignment_issues=fixed_mapping_issues + fixed_conflict_issues,
        )
        readiness = build_input_readiness_result(
            fixed_loader_report=fixed_loader_report,
            reconciliation_report=reconciliation_report,
            fixed_assignment_issues=fixed_mapping_issues + fixed_conflict_issues,
            loader_report=loader_report,
            global_errors=guarded_state.global_errors,
            quarantined_requirements=guarded_state.quarantined_requirements,
        )
        export_input_readiness_report(readiness, DEFAULT_INPUT_READINESS_REPORT_FILE)
        fixed_analysis = export_fixed_issue_workbooks(
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
            location_evidence_path=DEFAULT_LOCATION_MAPPING_EVIDENCE_FILE,
            supervisor_pack_path=DEFAULT_SUPERVISOR_CLARIFICATION_PACK_FILE,
            resolution_template_path=DEFAULT_FIXED_RESOLUTION_TEMPLATE_FILE,
            resolution_audit_path=DEFAULT_FIXED_RESOLUTION_AUDIT_FILE,
        )
        print(f"Fixed source rows: {fixed_loader_report.source_rows}")
        print(f"Valid fixed source rows: {fixed_loader_report.fixed_rows_loaded}")
        print(f"Fixed teaching occurrences: {sum(len(session.teaching_weeks) for session in fixed_sessions)}")
        print(f"Fixed mapping issues: {len(fixed_mapping_issues)}")
        print(f"Fixed-source conflicts: {len(fixed_conflict_issues)}")
        print(f"Quarantined fixed requirements: {len(guarded_state.quarantined_requirements)}")
        print(f"Quarantined teaching occurrences: {sum(item.affected_occurrences for item in guarded_state.quarantined_requirements)}")
        print(f"Anchored fixed assignments: {len(guarded_state.anchored_fixed_assignments)}")
        print(f"Fixed assignments excluded by quarantine: {len(guarded_state.quarantined_fixed_assignments)}")
        print(f"Unique affected fixed rows: {fixed_analysis['unique_affected_rows']}")
        print(f"Confirmed shared sessions: {fixed_analysis['shared_sessions']}")
        print(f"Supervisor queries: {fixed_analysis['supervisor_queries']}")
        print(f"Supervisor decision questions: {fixed_analysis['supervisor_decisions']}")
        print(f"Input readiness: {readiness.message}")
        print(f"Saved: {DEFAULT_FIXED_SESSIONS_AUDIT_FILE}")
        print(f"Saved: {DEFAULT_FIXED_RECONCILIATION_FILE}")
        print(f"Saved: {DEFAULT_INPUT_READINESS_REPORT_FILE}")
        print(f"Saved: {DEFAULT_FIXED_ROOT_CAUSE_FILE}")
        print(f"Saved: {DEFAULT_FIXED_CONFLICT_TRIAGE_FILE}")
        print(f"Saved: {DEFAULT_SUPERVISOR_FIXED_QUERIES_FILE}")
        print(f"Saved: {DEFAULT_LOCATION_MAPPING_EVIDENCE_FILE}")
        print(f"Saved: {DEFAULT_SUPERVISOR_CLARIFICATION_PACK_FILE}")
        print(f"Saved: {DEFAULT_FIXED_RESOLUTION_TEMPLATE_FILE}")
        print(f"Saved: {DEFAULT_FIXED_RESOLUTION_AUDIT_FILE}")
        if not readiness.ready:
            print("Generation blocked because global input issues were found.")
            raise SystemExit(1)
        fixed_assignments = guarded_state.anchored_fixed_assignments
        schedule_courses = adjusted_courses_after_exact_matches(courses, reconciliation_report)
        demand_courses = schedule_courses + _fixed_requirement_courses(fixed_assignments) + quarantined_requirement_courses(guarded_state.quarantined_requirements)

    print("\nGenerating initial schedule...")
    remarks_enabled = _remark_interpretation_enabled(args)
    schedule_courses = courses_with_effective_remark_durations(
        schedule_courses,
        enabled=remarks_enabled,
    )
    demand_courses = [
        *schedule_courses,
        *_fixed_requirement_courses(fixed_assignments),
        *(
            quarantined_requirement_courses(guarded_state.quarantined_requirements)
            if guarded_state is not None
            else []
        ),
    ]

    def _progress(position: int, total: int, course: Course) -> None:
        if args.scope == "eng":
            print(f"  progress: {position}/{total} -> {course.module_code} {course.activity}")

    initial_schedule = generate_schedule(
        schedule_courses,
        rooms,
        initial_assignments=fixed_assignments,
        progress_callback=_progress if args.scope == "eng" else None,
        progress_interval=args.progress_interval,
        max_retry_assignments=args.max_retry_assignments,
        max_candidate_patterns=args.max_candidate_patterns,
        enable_remark_interpretation=remarks_enabled,
    )
    initial_unscheduled_reasons = _snapshot_unscheduled_reasons(initial_schedule)
    annotate_schedule_violations(initial_schedule, enable_remark_interpretation=remarks_enabled)
    initial_soft = count_soft_violations(initial_schedule, enable_remark_interpretation=remarks_enabled)
    initial_soft_score = _count_weighted_soft_score(initial_schedule, remarks_enabled)
    _restore_unscheduled_reasons(initial_schedule, initial_unscheduled_reasons)
    initial_hard = _count_current_hard_violations(initial_schedule)
    _report_schedule_metrics("Initial", initial_schedule)
    print(f"Initial hard violations (all assignments): {initial_hard}")
    print(f"Initial soft violations: {initial_soft}")
    print(f"Initial weighted soft score: {initial_soft_score}")

    final_schedule = initial_schedule
    optimisation_metrics = _skipped_optimisation_summary(args, initial_soft, initial_soft_score, demand_courses, initial_schedule, rooms)
    if not args.skip_optimisation:
        print("\nOptimising schedule...")
        started = perf_counter()
        result = optimise_schedule_with_stats(
            initial_schedule,
            rooms,
            max_iterations=args.max_iterations,
            time_limit_seconds=args.optimisation_time_limit,
            patience=args.optimisation_patience,
            enable_remark_interpretation=remarks_enabled,
        )
        runtime_seconds = perf_counter() - started
        final_schedule = result.assignments
    final_unscheduled_reasons = _snapshot_unscheduled_reasons(final_schedule)
    final_soft = count_soft_violations(final_schedule, enable_remark_interpretation=remarks_enabled)
    final_soft_score = _count_weighted_soft_score(final_schedule, remarks_enabled)
    _restore_unscheduled_reasons(final_schedule, final_unscheduled_reasons)
    final_hard = _count_current_hard_violations(final_schedule)
    if not args.skip_optimisation:
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
    _report_schedule_metrics("Final", final_schedule)
    print(f"Final hard violations (all assignments): {final_hard}")
    print(f"Final soft violations: {final_soft}")
    print(f"Final weighted soft score: {final_soft_score}")

    export_run_summary(
        final_schedule,
        DEFAULT_RUN_SUMMARY_FILE,
        metadata=_run_metadata(args),
        demand_courses=demand_courses,
        input_course_records=len(courses),
        rooms=rooms,
        room_source_path=DEFAULT_ROOM_FILE,
        optimisation_summary=optimisation_metrics,
        enable_remark_interpretation=remarks_enabled,
        source_courses=courses,
    )
    print(f"Saved: {DEFAULT_RUN_SUMMARY_FILE}")
    export_stakeholder_views(
        final_schedule,
        rooms,
        DEFAULT_STAKEHOLDER_VIEWS_FILE,
        enable_remark_interpretation=remarks_enabled,
    )
    print(f"Saved: {DEFAULT_STAKEHOLDER_VIEWS_FILE}")
    export_remarks_audit(courses, DEFAULT_REMARKS_AUDIT_FILE, assignments=final_schedule)
    print(f"Saved: {DEFAULT_REMARKS_AUDIT_FILE}")
    if args.audit_demand_metrics:
        _print_demand_audit(demand_courses, final_schedule)

    remarks_comparison_path = None
    if args.scope == "eng" and not args.disable_remark_interpretation:
        print("\nGenerating remarks baseline comparison...")
        baseline_schedule = generate_schedule(
            schedule_courses,
            rooms,
            initial_assignments=fixed_assignments,
            progress_callback=None,
            progress_interval=args.progress_interval,
            max_retry_assignments=args.max_retry_assignments,
            max_candidate_patterns=args.max_candidate_patterns,
            enable_remark_interpretation=False,
        )
        if not args.skip_optimisation:
            baseline_result = optimise_schedule_with_stats(
                baseline_schedule,
                rooms,
                max_iterations=args.max_iterations,
                time_limit_seconds=args.optimisation_time_limit,
                patience=args.optimisation_patience,
                enable_remark_interpretation=False,
            )
            baseline_schedule = baseline_result.assignments
        comparison = export_remarks_coverage_comparison(
            demand_courses,
            baseline_schedule,
            final_schedule,
            DEFAULT_REMARKS_COMPARISON_FILE,
            input_course_records=len(courses),
            scheduler_metadata={
                "scope": args.scope,
                "skip_optimisation": args.skip_optimisation,
                "max_iterations": args.max_iterations,
                "optimisation_time_limit": args.optimisation_time_limit,
                "optimisation_patience": args.optimisation_patience,
                "max_candidate_patterns": args.max_candidate_patterns,
                "max_retry_assignments": args.max_retry_assignments,
                "progress_interval": args.progress_interval,
            },
        )
        remarks_comparison_path = DEFAULT_REMARKS_COMPARISON_FILE
        print(f"Saved: {DEFAULT_REMARKS_COMPARISON_FILE}")
        print(f"Remarks attribution reconciliation: {'PASS' if comparison.attribution_reconciles else 'FAIL'}")

    if args.skip_unscheduled_diagnostics:
        print("Skipped unscheduled diagnostics.")
    else:
        unscheduled_report = diagnose_unscheduled_assignments(
            final_schedule,
            rooms,
            max_diagnostic_assignments=args.max_diagnostic_assignments,
            enable_remark_interpretation=remarks_enabled,
        )
        _print_unscheduled_reason_summary(unscheduled_report)
        export_unscheduled_diagnostics(unscheduled_report, DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE)
        print(f"Saved: {DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE}")

    print("\nExporting files...")
    output_paths = export_outputs(
        final_schedule,
        args.scope,
        enable_remark_interpretation=remarks_enabled,
    ) or {}
    programme_completeness_rows: list[dict[str, object]] = []
    if args.scope == "eng" and DEFAULT_FIXED_SESSION_FILE.exists():
        programme_completeness_rows = build_programme_completeness_rows(
            demand_courses,
            final_schedule,
            guarded_state.quarantined_requirements if guarded_state is not None else [],
        )
        complete_programmes = complete_programme_set(programme_completeness_rows)
        export_all_valid_scheduled_schedule(
            final_schedule,
            DEFAULT_TEMPLATE2_ALL_VALID_FILE,
            template2_path=DEFAULT_TEMPLATE2_FILE,
            enable_remark_interpretation=remarks_enabled,
            rooms=rooms,
        )
        export_submission_ready_schedule(
            final_schedule,
            DEFAULT_TEMPLATE2_SUBMISSION_FILE,
            template2_path=DEFAULT_TEMPLATE2_FILE,
            enable_remark_interpretation=remarks_enabled,
            complete_programmes=complete_programmes,
            rooms=rooms,
        )
        template2_validation = validate_template2_submission(
            DEFAULT_TEMPLATE2_SUBMISSION_FILE,
            demand_courses,
            fixed_sessions,
            final_schedule,
            rooms,
            DEFAULT_TEMPLATE2_FILE,
        )
        export_template2_validation_report(template2_validation, DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE)
        export_template2_programme_year_reconciliation(template2_validation, DEFAULT_TEMPLATE2_PROGRAMME_YEAR_RECONCILIATION_FILE)
        export_template2_exclusion_audit(
            final_schedule,
            DEFAULT_TEMPLATE2_EXCLUSION_AUDIT_FILE,
            complete_programmes=complete_programmes,
            rooms=rooms,
        )
        export_fixed_session_integrity_report(
            fixed_sessions,
            final_schedule,
            DEFAULT_FIXED_SESSION_INTEGRITY_FILE,
            guarded_state.quarantined_requirements if guarded_state is not None else [],
        )
        print(f"Saved: {DEFAULT_TEMPLATE2_ALL_VALID_FILE}")
        print(f"Saved: {DEFAULT_TEMPLATE2_SUBMISSION_FILE}")
        print(f"Saved: {DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE}")
        print(f"Saved: {DEFAULT_TEMPLATE2_PROGRAMME_YEAR_RECONCILIATION_FILE}")
        print(f"Saved: {DEFAULT_TEMPLATE2_EXCLUSION_AUDIT_FILE}")
        print(f"Saved: {DEFAULT_FIXED_SESSION_INTEGRITY_FILE}")
        print(f"Template 2 submission readiness: {'PASS' if template2_validation.ready else 'FAIL'}")
        if guarded_state is not None:
            programme_completeness_rows = build_programme_completeness_rows(
                demand_courses,
                final_schedule,
                guarded_state.quarantined_requirements,
                submission_ready_programmes={
                    str(row.get("Normalised Programme/Year"))
                    for row in template2_validation.programme_rows
                    if row.get("Included In Submission") == "Yes"
                },
            )
            export_guarded_generation_report(
                output_path=DEFAULT_GUARDED_GENERATION_REPORT_FILE,
                global_errors=guarded_state.global_errors,
                quarantined=guarded_state.quarantined_requirements,
                fixed_conflict_issues=fixed_conflict_issues,
                warnings=guarded_state.warning_issues,
                assignments=final_schedule,
                demand_courses=demand_courses,
                programme_rows=programme_completeness_rows,
                template2_summary=template2_validation.summary,
            )
            print(f"Saved: {DEFAULT_GUARDED_GENERATION_REPORT_FILE}")
        output_paths["submission_ready_timetable"] = DEFAULT_TEMPLATE2_SUBMISSION_FILE
        output_paths["template2_all_valid_timetable"] = DEFAULT_TEMPLATE2_ALL_VALID_FILE
        output_paths["template2_submission_validation"] = DEFAULT_TEMPLATE2_SUBMISSION_VALIDATION_FILE
        output_paths["template2_programme_year_reconciliation"] = DEFAULT_TEMPLATE2_PROGRAMME_YEAR_RECONCILIATION_FILE
        output_paths["template2_exclusion_audit"] = DEFAULT_TEMPLATE2_EXCLUSION_AUDIT_FILE
        output_paths["fixed_session_integrity"] = DEFAULT_FIXED_SESSION_INTEGRITY_FILE
        output_paths["guarded_generation_report"] = DEFAULT_GUARDED_GENERATION_REPORT_FILE
    output_paths.update(
        {
            "loader_report": DEFAULT_LOADER_REPORT_FILE,
            "run_summary": DEFAULT_RUN_SUMMARY_FILE,
            "stakeholder_views": DEFAULT_STAKEHOLDER_VIEWS_FILE,
            "remarks_audit": DEFAULT_REMARKS_AUDIT_FILE,
        }
    )
    if remarks_comparison_path is not None:
        output_paths["remarks_coverage_comparison"] = remarks_comparison_path
    if not args.skip_preflight:
        output_paths["preflight_report"] = DEFAULT_PREFLIGHT_REPORT_FILE
    if not args.skip_unscheduled_diagnostics:
        output_paths["unscheduled_diagnostics"] = DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE
    try:
        visual_result = export_timetable_visuals(
            assignments=final_schedule,
            rooms=rooms,
            programme_rows=programme_completeness_rows,
            programme_path=DEFAULT_PROGRAMME_VISUALS_FILE,
            tutor_path=DEFAULT_TUTOR_VISUALS_FILE,
            room_path=DEFAULT_ROOM_VISUALS_FILE,
            validation_path=DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE,
        )
        print(f"Saved: {DEFAULT_PROGRAMME_VISUALS_FILE}")
        print(f"Saved: {DEFAULT_TUTOR_VISUALS_FILE}")
        print(f"Saved: {DEFAULT_ROOM_VISUALS_FILE}")
        print(f"Saved: {DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE}")
        print(f"Visual timetable export status: {visual_result.status}")
    except Exception as exc:  # pragma: no cover - preserves official outputs on workbook failures
        visual_result = export_visualisation_failure_report(DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE, exc)
        print(f"Visual timetable export failed: {exc}")
        print(f"Saved: {DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE}")
    output_paths.update(
        {
            "programme_visuals": DEFAULT_PROGRAMME_VISUALS_FILE,
            "tutor_visuals": DEFAULT_TUTOR_VISUALS_FILE,
            "room_visuals": DEFAULT_ROOM_VISUALS_FILE,
            "visualisation_validation": DEFAULT_TIMETABLE_VISUALISATION_VALIDATION_FILE,
        }
    )
    export_run_manifest(
        demand_courses,
        final_schedule,
        DEFAULT_RUN_MANIFEST_FILE,
        metadata=_run_metadata(args),
        rooms=rooms,
        output_files=output_paths,
        enable_remark_interpretation=remarks_enabled,
    )
    print(f"Saved: {DEFAULT_RUN_MANIFEST_FILE}")


if __name__ == "__main__":
    main()
