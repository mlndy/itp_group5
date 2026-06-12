"""Run the full SIT timetabling pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_COURSE_FILE,
    DEFAULT_ENGINEERING_FOLDER,
    DEFAULT_ROOM_FILE,
    OUTPUT_DIR,
)
from data.loader import load_common_modules, load_courses_from_folder, load_courses_from_requirements, load_rooms_from_csv
from engine.constraint_checker import annotate_schedule_violations, count_hard_violations, count_soft_violations
from generator.scheduler import generate_schedule
from optimiser.local_search import optimise_schedule
from output.exporter import export_schedule, export_violations


def parse_args() -> argparse.Namespace:
    """Parse command-line options for DSC or Engineering-cluster runs."""
    parser = argparse.ArgumentParser(description="SIT timetabling prototype")
    parser.add_argument("--scope", choices=["dsc", "eng"], default="dsc", help="Dataset scope to run")
    parser.add_argument("--max-iterations", type=int, default=8, help="Local-search optimisation iterations")
    parser.add_argument("--skip-optimisation", action="store_true", help="Generate only the greedy timetable")
    return parser.parse_args()


def load_courses(scope: str) -> list:
    """Load either DSC-only or Engineering-cluster requirement files."""
    common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
    if scope == "eng" and DEFAULT_ENGINEERING_FOLDER.exists():
        return load_courses_from_folder(DEFAULT_ENGINEERING_FOLDER, common_modules=common_modules)
    return load_courses_from_requirements(DEFAULT_COURSE_FILE, common_modules=common_modules)


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
    courses = load_courses(args.scope)
    rooms = load_rooms_from_csv(DEFAULT_ROOM_FILE)
    print(f"Scope: {args.scope}")
    print(f"Courses loaded: {len(courses)}")
    print(f"Rooms loaded: {len(rooms)}")
    print(f"Common modules loaded: {len(common_modules)}")

    print("\nGenerating initial schedule...")
    initial_schedule = generate_schedule(courses, rooms)
    annotate_schedule_violations(initial_schedule)
    initial_hard = count_hard_violations(initial_schedule)
    initial_soft = count_soft_violations(initial_schedule)
    scheduled = sum(1 for item in initial_schedule if item.room is not None and item.timeslot is not None)
    print(f"Scheduled assignments: {scheduled} / {len(initial_schedule)}")
    print(f"Hard violations before optimisation: {initial_hard}")
    print(f"Soft violations before optimisation: {initial_soft}")

    final_schedule = initial_schedule
    if not args.skip_optimisation:
        print("\nOptimising schedule...")
        final_schedule = optimise_schedule(initial_schedule, rooms, max_iterations=args.max_iterations)
    final_hard = count_hard_violations(final_schedule)
    final_soft = count_soft_violations(final_schedule)
    print(f"Hard violations after optimisation: {final_hard}")
    print(f"Soft violations after optimisation: {final_soft}")

    print("\nExporting files...")
    export_outputs(final_schedule, args.scope)


if __name__ == "__main__":
    main()
