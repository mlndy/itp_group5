"""Tests for command-line pipeline controls."""

from __future__ import annotations

import sys

import main as app
from data.loader import LoaderReport
from data.models import Assignment, Course, Room


def make_course(**overrides: object) -> Course:
    """Create a small test course."""
    data = {
        "module_code": "ENG1001",
        "activity": "Lecture",
        "prog_yr": "ENG/YR 1",
        "class_size": 30,
        "delivery_mode": "f2f",
        "teaching_weeks": [1],
        "week_pattern": "ALL",
        "staff_ids": ["S001"],
        "duration_hrs": 2,
        "is_common_module": False,
    }
    data.update(overrides)
    return Course(**data)


def _stub_pipeline(monkeypatch, generated: list[Assignment]) -> None:
    """Replace file and reporting side effects for main() tests."""
    course = generated[0].course
    rooms = [Room("R1", 100, "physical")]

    monkeypatch.setattr(app, "load_common_modules", lambda path: set())
    monkeypatch.setattr(app, "load_courses", lambda scope, common_modules: ([course], LoaderReport()))
    monkeypatch.setattr(app, "load_rooms_from_csv", lambda path: rooms)
    monkeypatch.setattr(app, "export_loader_report", lambda report, output_path: None)
    monkeypatch.setattr(app, "run_preflight_checks", lambda courses, rooms: [])
    monkeypatch.setattr(app, "export_preflight_report", lambda issues, output_path: None)
    monkeypatch.setattr(app, "annotate_schedule_violations", lambda assignments, **kwargs: assignments)
    monkeypatch.setattr(app, "count_soft_violations", lambda assignments, **kwargs: 0)
    monkeypatch.setattr(app, "optimise_schedule", lambda assignments, rooms_arg, max_iterations: assignments)
    monkeypatch.setattr(app, "export_run_summary", lambda assignments, output_path, **kwargs: None)
    monkeypatch.setattr(app, "export_stakeholder_views", lambda assignments, rooms_arg, output_path, **kwargs: None)
    monkeypatch.setattr(app, "export_remarks_audit", lambda courses, output_path: None)
    monkeypatch.setattr(
        app,
        "export_remarks_coverage_comparison",
        lambda courses, baseline, enhanced, output_path, **kwargs: type("Comparison", (), {"attribution_reconciles": True})(),
    )
    monkeypatch.setattr(app, "export_run_manifest", lambda courses, assignments, output_path, **kwargs: None)
    monkeypatch.setattr(app, "export_outputs", lambda assignments, scope, **kwargs: {})
    monkeypatch.setattr(app, "export_timetable_visuals", lambda **kwargs: type("VisualResult", (), {"status": "PASS"})())
    monkeypatch.setattr(app, "export_visualisation_failure_report", lambda *args, **kwargs: type("VisualResult", (), {"status": "FAIL"})())


def test_parse_args_accepts_demo_safety_controls() -> None:
    """The CLI should accept Engineering demo safety controls."""
    args = app.parse_args(
        [
            "--scope",
            "eng",
            "--max-retry-assignments",
            "20",
            "--progress-interval",
            "10",
            "--skip-unscheduled-diagnostics",
            "--max-candidate-patterns",
            "150",
            "--max-diagnostic-assignments",
            "5",
            "--optimisation-time-limit",
            "120",
            "--optimisation-patience",
            "2",
            "--audit-demand-metrics",
            "--skip-preflight",
            "--disable-remark-interpretation",
        ]
    )

    assert args.scope == "eng"
    assert args.max_retry_assignments == 20
    assert args.progress_interval == 10
    assert args.skip_unscheduled_diagnostics is True
    assert args.max_candidate_patterns == 150
    assert args.max_diagnostic_assignments == 5
    assert args.optimisation_time_limit == 120
    assert args.optimisation_patience == 2
    assert args.audit_demand_metrics is True
    assert args.skip_preflight is True
    assert args.disable_remark_interpretation is True


def test_main_passes_demo_safety_controls_to_generate_schedule(monkeypatch, tmp_path) -> None:
    """main() should pass demo safety controls into generate_schedule()."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    captured: list[dict[str, object]] = []
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "DEFAULT_FIXED_SESSION_FILE", tmp_path / "missing_fixed_sessions.xlsx")

    def fake_generate_schedule(courses, rooms, **kwargs):
        captured.append(kwargs)
        return generated

    monkeypatch.setattr(app, "generate_schedule", fake_generate_schedule)
    monkeypatch.setattr(app, "diagnose_unscheduled_assignments", lambda assignments, rooms: None)
    monkeypatch.setattr(app, "export_unscheduled_diagnostics", lambda report, output_path: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--scope",
            "eng",
            "--skip-optimisation",
            "--max-retry-assignments",
            "20",
            "--progress-interval",
            "25",
            "--max-candidate-patterns",
            "150",
            "--skip-unscheduled-diagnostics",
        ],
    )

    app.main()

    enhanced_call = captured[0]
    baseline_call = captured[1]
    assert enhanced_call["progress_interval"] == 25
    assert enhanced_call["max_retry_assignments"] == 20
    assert enhanced_call["max_candidate_patterns"] == 150
    assert enhanced_call["enable_remark_interpretation"] is True
    assert baseline_call["enable_remark_interpretation"] is False


def test_skip_unscheduled_diagnostics_does_not_break_pipeline(monkeypatch) -> None:
    """Skipping diagnostics should avoid diagnostic calls and still export outputs."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    exported: dict[str, object] = {}
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)
    monkeypatch.setattr(
        app,
        "diagnose_unscheduled_assignments",
        lambda assignments, rooms: (_ for _ in ()).throw(AssertionError("diagnostics should be skipped")),
    )
    monkeypatch.setattr(
        app,
        "export_outputs",
        lambda assignments, scope, **kwargs: exported.update({"assignments": assignments, "scope": scope}),
    )
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-unscheduled-diagnostics"])

    app.main()

    assert exported == {"assignments": generated, "scope": "dsc"}


def test_main_passes_max_diagnostic_assignments(monkeypatch) -> None:
    """main() should pass the optional diagnostic cap into diagnostics."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    captured: dict[str, object] = {}
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)

    def fake_diagnose(assignments, rooms, **kwargs):
        captured.update(kwargs)
        return app.UnscheduledDiagnosticsReport()

    monkeypatch.setattr(app, "diagnose_unscheduled_assignments", fake_diagnose)
    monkeypatch.setattr(app, "export_unscheduled_diagnostics", lambda report, output_path: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--skip-optimisation", "--skip-preflight", "--max-diagnostic-assignments", "3"],
    )

    app.main()

    assert captured["max_diagnostic_assignments"] == 3


def test_main_accepts_skip_preflight(monkeypatch) -> None:
    """Skipping preflight should avoid preflight checks and still run."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)
    monkeypatch.setattr(
        app,
        "run_preflight_checks",
        lambda courses, rooms: (_ for _ in ()).throw(AssertionError("preflight should be skipped")),
    )
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-preflight", "--skip-unscheduled-diagnostics"])

    app.main()


def test_main_accepts_audit_demand_metrics(monkeypatch) -> None:
    """The optional demand audit should run without changing the pipeline."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-preflight", "--skip-unscheduled-diagnostics", "--audit-demand-metrics"])

    app.main()


def test_main_reports_skipped_optimisation(monkeypatch) -> None:
    """main() should pass skipped optimisation evidence into the run summary."""
    generated = [Assignment(course=make_course(), room=Room("R1", 100, "physical"), timeslot=None)]
    captured: dict[str, object] = {}
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)
    monkeypatch.setattr(app, "export_run_summary", lambda assignments, output_path, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-preflight", "--skip-unscheduled-diagnostics"])

    app.main()

    optimisation_summary = captured["optimisation_summary"]
    assert optimisation_summary["optimisation_enabled"] == "No"
    assert optimisation_summary["status"] == "Skipped"


def test_main_passes_optimiser_runtime_controls(monkeypatch) -> None:
    """main() should pass time-limit and patience settings into the optimiser."""
    generated = [Assignment(course=make_course(), room=Room("R1", 100, "physical"), timeslot=None)]
    captured: dict[str, object] = {}
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)

    class Result:
        assignments = generated
        iterations_completed = 0
        status = "Time limit reached"
        stop_reason = "Stopped after 1 seconds"

    def fake_optimise(assignments, rooms, **kwargs):
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr(app, "optimise_schedule_with_stats", fake_optimise)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--skip-preflight",
            "--skip-unscheduled-diagnostics",
            "--optimisation-time-limit",
            "1",
            "--optimisation-patience",
            "2",
        ],
    )

    app.main()

    assert captured["time_limit_seconds"] == 1
    assert captured["patience"] == 2


def test_main_exports_acceptance_workbooks(monkeypatch) -> None:
    """main() should write stakeholder views and the run manifest."""
    generated = [Assignment(course=make_course(), room=Room("R1", 100, "physical"), timeslot=None)]
    exported: dict[str, bool] = {}
    _stub_pipeline(monkeypatch, generated)
    monkeypatch.setattr(app, "generate_schedule", lambda courses, rooms, **kwargs: generated)
    monkeypatch.setattr(app, "export_stakeholder_views", lambda assignments, rooms, output_path, **kwargs: exported.update({"stakeholder": True}))
    monkeypatch.setattr(app, "export_run_manifest", lambda courses, assignments, output_path, **kwargs: exported.update({"manifest": True}))
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-preflight", "--skip-unscheduled-diagnostics"])

    app.main()

    assert exported == {"stakeholder": True, "manifest": True}
