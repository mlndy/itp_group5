"""Regression tests for selected-workbook UI run scoping."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pipeline
from ui.controller import build_default_ui_options


def test_ui_selected_workbook_excludes_unrelated_fixed_sessions(monkeypatch, tmp_path: Path) -> None:
    """A selected workbook must not pull unrelated fixed sessions into the run."""
    selected = Path(__file__).resolve().parents[2] / "Data" / "Requirements_ENG" / "2510_DSC.xlsx"
    selected_modules = {"DSC1001", "DSC2302", "DSC3002A", "DSC3002B", "MET2602"}
    captured: dict[str, set[str]] = {}

    monkeypatch.setattr(
        pipeline,
        "build_input_readiness_result",
        lambda **kwargs: SimpleNamespace(ready=True, message="Ready for scoped UI test."),
    )
    monkeypatch.setattr(pipeline, "export_loader_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_preflight_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_fixed_sessions_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_fixed_reconciliation_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_input_readiness_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_fixed_issue_workbooks", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_run_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_stakeholder_views", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_remarks_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_submission_ready_schedule", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_template2_validation_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_guarded_generation_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_timetable_visuals", lambda **kwargs: SimpleNamespace(status="PASS"))
    monkeypatch.setattr(pipeline, "export_visualisation_failure_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "export_run_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pipeline,
        "validate_template2_submission",
        lambda *args, **kwargs: SimpleNamespace(
            ready=True,
            summary={},
            programme_rows=[],
        ),
    )

    def fake_generate_schedule(courses, rooms, **kwargs):
        initial = list(kwargs.get("initial_assignments") or [])
        captured["schedule_modules"] = {assignment.course.module_code for assignment in initial}
        return initial

    def fake_export_outputs(assignments, scope, **kwargs):
        captured["output_modules"] = {assignment.course.module_code for assignment in assignments}
        return {"timetable": tmp_path / "Proposed_Timetable.xlsx", "violations": tmp_path / "violations.xlsx"}

    monkeypatch.setattr(pipeline, "generate_schedule", fake_generate_schedule)
    monkeypatch.setattr(pipeline, "export_outputs", fake_export_outputs)

    result = pipeline.run_timetable_pipeline(
        build_default_ui_options(selected),
        progress_callback=None,
    )

    assert result.required_occurrences > 0
    assert captured["schedule_modules"] <= selected_modules
    assert captured["output_modules"] <= selected_modules
    assert not ({"CVE2151", "MEC1151", "RSE1101", "SBE2113", "NME1103"} & captured["output_modules"])
