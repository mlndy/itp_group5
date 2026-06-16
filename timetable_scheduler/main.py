"""Run the full SIT timetabling pipeline."""

from __future__ import annotations

import argparse

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_COURSE_FILE,
    DEFAULT_ENGINEERING_FOLDER,
    DEFAULT_LOADER_REPORT_FILE,
    DEFAULT_PREFLIGHT_REPORT_FILE,
    DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE,
    DEFAULT_ROOM_FILE,
    DEFAULT_RUN_SUMMARY_FILE,
    OUTPUT_DIR,
)
from data.loader import (
    LoaderReport,
    export_loader_report,
    load_common_modules,
    load_courses_from_folder,
    load_courses_from_requirements,
    load_rooms_from_csv,
)
from data.models import Course
from engine.constraint_checker import annotate_schedule_violations, count_hard_violations, count_soft_violations
from engine.preflight_validator import run_preflight_checks
from engine.unscheduled_diagnostics import (
    UnscheduledDiagnosticsReport,
    diagnose_unscheduled_assignments,
    export_unscheduled_diagnostics,
)
from generator.scheduler import generate_schedule
from optimiser.local_search import optimise_schedule
from output.exporter import export_schedule, export_violations
from output.report_exporter import export_preflight_report, export_run_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for DSC or Engineering-cluster runs."""
    parser = argparse.ArgumentParser(description="SIT timetabling prototype")
    parser.add_argument("--scope", choices=["dsc", "eng"], default="dsc", help="Dataset scope to run")
    parser.add_argument("--max-iterations", type=int, default=8, help="Local-search optimisation iterations")
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
    parser.add_argument("--skip-preflight", action="store_true", help="Skip input preflight validation report")
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


def export_outputs(assignments: list, scope: str) -> None:
    """Export timetable and violation reports for the selected scope."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "engineering_cluster" if scope == "eng" else "dsc"
    timetable_path = OUTPUT_DIR / f"final_timetable_{suffix}.xlsx"
    violation_path = OUTPUT_DIR / f"violation_report_{suffix}.xlsx"
    export_schedule(assignments, timetable_path)
    export_violations(assignments, violation_path)
    # Keep the original filenames for demo convenience when running DSC mode.
    if scope == "dsc":
        export_schedule(assignments, OUTPUT_DIR / "final_timetable.xlsx")
        export_violations(assignments, OUTPUT_DIR / "violation_report.xlsx")
    print(f"Saved: {timetable_path}")
    print(f"Saved: {violation_path}")


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

    print("\nGenerating initial schedule...")

    def _progress(position: int, total: int, course: Course) -> None:
        if args.scope == "eng":
            print(f"  progress: {position}/{total} -> {course.module_code} {course.activity}")

    initial_schedule = generate_schedule(
        courses,
        rooms,
        progress_callback=_progress if args.scope == "eng" else None,
        progress_interval=args.progress_interval,
        max_retry_assignments=args.max_retry_assignments,
        max_candidate_patterns=args.max_candidate_patterns,
    )
    annotate_schedule_violations(initial_schedule)
    initial_hard = count_hard_violations(initial_schedule)
    initial_soft = count_soft_violations(initial_schedule)
    _report_schedule_metrics("Initial", initial_schedule)
    print(f"Initial hard violations (all assignments): {initial_hard}")
    print(f"Initial soft violations: {initial_soft}")

    final_schedule = initial_schedule
    if not args.skip_optimisation:
        print("\nOptimising schedule...")
        final_schedule = optimise_schedule(initial_schedule, rooms, max_iterations=args.max_iterations)
    final_hard = count_hard_violations(final_schedule)
    final_soft = count_soft_violations(final_schedule)
    _report_schedule_metrics("Final", final_schedule)
    print(f"Final hard violations (all assignments): {final_hard}")
    print(f"Final soft violations: {final_soft}")

    export_run_summary(final_schedule, DEFAULT_RUN_SUMMARY_FILE)
    print(f"Saved: {DEFAULT_RUN_SUMMARY_FILE}")

    if args.skip_unscheduled_diagnostics:
        print("Skipped unscheduled diagnostics.")
    else:
        unscheduled_report = diagnose_unscheduled_assignments(final_schedule, rooms)
        _print_unscheduled_reason_summary(unscheduled_report)
        export_unscheduled_diagnostics(unscheduled_report, DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE)
        print(f"Saved: {DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE}")

    print("\nExporting files...")
    export_outputs(final_schedule, args.scope)


if __name__ == "__main__":
    main()
