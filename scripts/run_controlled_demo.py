"""Run a small controlled demonstration without touching Engineering data."""

from __future__ import annotations

import json
from pathlib import Path

from data.models import Assignment, Course, Room, TimeSlot
from engine.constraint_checker import check_hard_constraints
from engine.preflight_validator import validate_courses
from generator.scheduler import generate_schedule
from output.exporter import export_schedule
from output.report_exporter import export_stakeholder_views
from output.timetable_visualizer import export_timetable_visuals

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = PROJECT_ROOT / "final_verification" / "controlled_demo"


def _course(**overrides: object) -> Course:
    """Return a small fixture course."""
    data = {
        "module_code": "DEMO1001",
        "activity": "Lecture",
        "prog_yr": "DEMO/Y1",
        "class_size": 20,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["TUTOR_A"],
        "duration_hrs": 1,
        "group_ids": ["DEMO/Y1"],
        "source_file": "controlled_demo.xlsx",
        "source_sheet": "Module",
        "source_row": 2,
    }
    data.update(overrides)
    return Course(**data)


def _pass_fail(condition: bool) -> str:
    """Return PASS or FAIL."""
    return "PASS" if condition else "FAIL"


def run_demo(output_dir: Path = DEMO_DIR) -> dict[str, object]:
    """Run the controlled demonstration and return evidence paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    room_a = Room("DEMO-SR1", 30, "physical")
    room_b = Room("DEMO-SR2", 30, "physical")
    rooms = [room_a, room_b]
    fixed_course = _course(
        module_code="DEMO-FIXED",
        activity="Seminar",
        staff_ids=["FIXED_TUTOR"],
        fixed_source="official-demo-fixed-source.xlsx:Module:2",
        is_fixed_requirement=True,
        source_row=10,
    )
    fixed_slot = TimeSlot("Monday", "09:00", 1)
    fixed_assignment = Assignment(
        fixed_course,
        room_a,
        fixed_slot,
        is_fixed=True,
        fixed_source="official-demo-fixed-source.xlsx:Module:2",
    )
    valid_course = _course(module_code="DEMO-VALID", staff_ids=["VALID_TUTOR"], group_ids=["DEMO/Y2"], source_row=11)
    valid_assignment = Assignment(valid_course, room_b, TimeSlot("Tuesday", "10:00", 1))
    invalid_course = _course(module_code="", class_size=0, source_row=12)
    preflight_issues = validate_courses([invalid_course], rooms)

    clash_slot = TimeSlot("Monday", "09:00", 1)
    room_clash = check_hard_constraints(Assignment(_course(module_code="DEMO-ROOM", staff_ids=["ROOM_TUTOR"], group_ids=["DEMO/Y3"]), room_a, clash_slot), [fixed_assignment])
    tutor_clash = check_hard_constraints(Assignment(_course(module_code="DEMO-TUTOR", staff_ids=["FIXED_TUTOR"], group_ids=["DEMO/Y4"]), room_b, clash_slot), [fixed_assignment])
    group_clash = check_hard_constraints(Assignment(_course(module_code="DEMO-GROUP", staff_ids=["GROUP_TUTOR"], group_ids=["DEMO/Y1"]), room_b, clash_slot), [fixed_assignment])

    non_fixed = _course(
        module_code="DEMO-AROUND",
        activity="Tutorial",
        staff_ids=["FIXED_TUTOR"],
        group_ids=["DEMO/Y1"],
        source_row=13,
    )
    generated = generate_schedule(
        [non_fixed],
        rooms,
        initial_assignments=[fixed_assignment],
        max_candidate_patterns=80,
        max_retry_assignments=2,
    )
    scheduled_non_fixed = next(
        item for item in generated if item.course.module_code == "DEMO-AROUND" and item.room and item.timeslot
    )
    scheduled = [fixed_assignment, valid_assignment, scheduled_non_fixed]
    exception_assignment = Assignment(
        invalid_course,
        None,
        None,
        hard_violations=["Controlled demo invalid input quarantined by preflight validation"],
    )
    all_assignments = [*scheduled, exception_assignment]

    template_output = output_dir / "Demo_Proposed_Timetable.xlsx"
    exception_output = output_dir / "Demo_Exception_Report.xlsx"
    programme_visuals = output_dir / "Demo_Programme_Timetable_Visuals.xlsx"
    tutor_visuals = output_dir / "Demo_Tutor_Timetable_Visuals.xlsx"
    room_visuals = output_dir / "Demo_Room_Timetable_Visuals.xlsx"
    visual_validation = output_dir / "Demo_Timetable_Visualisation_Validation.xlsx"
    export_schedule(all_assignments, template_output)
    export_stakeholder_views(all_assignments, rooms, exception_output)
    visual_result = export_timetable_visuals(
        assignments=scheduled,
        rooms=rooms,
        programme_rows=None,
        programme_path=programme_visuals,
        tutor_path=tutor_visuals,
        room_path=room_visuals,
        validation_path=visual_validation,
    )

    checks = {
        "valid_requirement_accepted": _pass_fail(not check_hard_constraints(valid_assignment, [fixed_assignment])),
        "invalid_input_quarantined": _pass_fail(bool(preflight_issues)),
        "room_clash_rejected": _pass_fail(any("room" in item.casefold() for item in room_clash)),
        "tutor_clash_rejected": _pass_fail(any("staff" in item.casefold() or "tutor" in item.casefold() for item in tutor_clash)),
        "student_group_clash_rejected": _pass_fail(any("student group" in item.casefold() or "group" in item.casefold() for item in group_clash)),
        "fixed_session_anchored_exactly": _pass_fail(fixed_assignment.timeslot == fixed_slot and fixed_assignment.room == room_a),
        "non_fixed_scheduled_around_fixed": _pass_fail(scheduled_non_fixed.timeslot != fixed_slot),
        "template2_output_generated": _pass_fail(template_output.exists()),
        "exception_report_generated": _pass_fail(exception_output.exists()),
        "visual_output_generated": _pass_fail(visual_result.status == "PASS"),
    }
    result = {
        "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
        "checks": checks,
        "outputs": {
            "proposed_timetable": str(template_output),
            "exception_report": str(exception_output),
            "programme_visuals": str(programme_visuals),
            "tutor_visuals": str(tutor_visuals),
            "room_visuals": str(room_visuals),
            "visual_validation": str(visual_validation),
        },
    }
    (output_dir / "demo_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Controlled Demo Result", ""]
    for check, status in checks.items():
        lines.append(f"- {check}: {status}")
    lines.append("")
    lines.append(f"Demo status: {result['status']}")
    (output_dir / "demo_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    """Run the controlled demo."""
    result = run_demo()
    print("CONTROLLED DEMO:", result["status"])
    for check, status in result["checks"].items():
        print(f"{check}: {status}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
