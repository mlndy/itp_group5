"""Tests for explicit Template 1 input and Template 2 output pipeline roles."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pipeline
from data.loader import WorkbookDiagnostic
from data.models import Assignment, Course, Room, TimeSlot


def make_course() -> Course:
    """Create one course for pipeline role tests."""
    return Course(
        module_code="ENG1001",
        activity="Lecture",
        prog_yr="ENG/YR 1",
        class_size=30,
        delivery_mode="f2f",
        teaching_weeks=[1],
        week_pattern="ALL",
        staff_ids=["S001"],
        duration_hrs=2,
        source_file="selected_template1.xlsx",
        group_ids=["ENG/YR 1"],
    )


def test_selected_template1_path_reaches_course_loader(monkeypatch, tmp_path: Path) -> None:
    """Selected consolidated schedule path should be passed to the Template 1 loader."""
    selected = tmp_path / "selected_template1.xlsx"
    selected.write_text("placeholder", encoding="utf-8")
    captured: dict[str, Path] = {}

    def fake_loader(path: Path, common_modules=None):
        captured["path"] = path
        return [make_course()], WorkbookDiagnostic(str(path), "Module", "parsed", "ok", rows_parsed=1)

    monkeypatch.setattr(pipeline, "load_consolidated_schedule_with_report", fake_loader)

    courses, report = pipeline._load_courses_from_path(selected, "eng", set())

    assert captured["path"] == selected
    assert courses[0].module_code == "ENG1001"
    assert report.workbooks[0].file_path == str(selected)


def test_pipeline_keeps_template1_input_separate_from_template2_output_template(monkeypatch, tmp_path: Path) -> None:
    """The selected Template 1 path must not be passed as the Template 2 output template."""
    selected_template1 = tmp_path / "selected_template1.xlsx"
    bundled_template2 = tmp_path / "bundled_template2.xlsx"
    generated_template2 = tmp_path / "generated_template2.xlsx"
    selected_template1.write_text("template 1", encoding="utf-8")
    bundled_template2.write_text("template 2", encoding="utf-8")
    course = make_course()
    room = Room("R1", 100, "physical")
    assignment = Assignment(course, room, TimeSlot("Monday", "09:00", 1))
    captured: dict[str, object] = {}

    monkeypatch.setattr(pipeline, "load_common_modules", lambda path: set())
    monkeypatch.setattr(
        pipeline,
        "load_consolidated_schedule_with_report",
        lambda path, common_modules=None: (
            [course],
            WorkbookDiagnostic(str(path), "Module", "parsed", "ok", rows_parsed=1),
        ),
    )
    monkeypatch.setattr(pipeline, "load_rooms_from_csv", lambda path: [room])
    monkeypatch.setattr(pipeline, "export_loader_report", lambda report, path: None)
    monkeypatch.setattr(pipeline, "generate_schedule", lambda courses, rooms, **kwargs: [assignment])
    monkeypatch.setattr(pipeline, "annotate_schedule_violations", lambda assignments: None)
    monkeypatch.setattr(pipeline, "count_soft_violations", lambda assignments: 0)
    monkeypatch.setattr(pipeline, "_count_weighted_soft_score", lambda assignments: 0)
    monkeypatch.setattr(pipeline, "_skipped_optimisation_summary", lambda *args, **kwargs: {"status": "Skipped"})
    monkeypatch.setattr(pipeline, "export_run_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_stakeholder_views", lambda *args, **kwargs: None)

    def fake_export_outputs(assignments, scope, template2_path):
        captured["export_template2_path"] = template2_path
        return {"timetable": generated_template2, "violations": tmp_path / "violations.xlsx"}

    def fake_manifest(courses, assignments, output_path, **kwargs):
        captured["manifest_metadata"] = kwargs["metadata"]
        captured["manifest_template2_path"] = kwargs["template2_path"]
        captured["manifest_outputs"] = kwargs["output_files"]

    monkeypatch.setattr(pipeline, "export_outputs", fake_export_outputs)
    monkeypatch.setattr(pipeline, "export_run_manifest", fake_manifest)
    monkeypatch.setattr(
        pipeline,
        "build_demand_metrics",
        lambda *args, **kwargs: SimpleNamespace(
            required_teaching_occurrences=1,
            scheduled_teaching_occurrences=1,
            unscheduled_teaching_occurrences=0,
            coverage_rate_percent=100.0,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "audit_resources",
        lambda *args, **kwargs: SimpleNamespace(
            required_online_teaching_occurrences=0,
            scheduled_online_teaching_occurrences=0,
        ),
    )
    monkeypatch.setattr(pipeline, "validate_release", lambda *args, **kwargs: SimpleNamespace(passed=True))

    pipeline.run_timetable_pipeline(
        pipeline.PipelineOptions(
            consolidated_schedule_path=selected_template1,
            template2_output_template_path=bundled_template2,
            skip_preflight=True,
            skip_unscheduled_diagnostics=True,
        )
    )

    assert captured["export_template2_path"] == bundled_template2
    assert captured["export_template2_path"] != selected_template1
    assert captured["manifest_template2_path"] == bundled_template2
    assert captured["manifest_metadata"]["input_workbook"] == str(selected_template1)
    assert captured["manifest_metadata"]["output_template"] == str(bundled_template2)
    assert captured["manifest_outputs"]["timetable"] == generated_template2
