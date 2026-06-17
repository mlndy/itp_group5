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
    monkeypatch.setattr(app, "annotate_schedule_violations", lambda assignments: assignments)
    monkeypatch.setattr(app, "count_soft_violations", lambda assignments: 0)
    monkeypatch.setattr(app, "optimise_schedule", lambda assignments, rooms_arg, max_iterations: assignments)
    monkeypatch.setattr(app, "export_run_summary", lambda assignments, output_path, metadata=None: None)
    monkeypatch.setattr(app, "export_outputs", lambda assignments, scope: None)


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
            "--skip-preflight",
        ]
    )

    assert args.scope == "eng"
    assert args.max_retry_assignments == 20
    assert args.progress_interval == 10
    assert args.skip_unscheduled_diagnostics is True
    assert args.max_candidate_patterns == 150
    assert args.skip_preflight is True


def test_main_passes_demo_safety_controls_to_generate_schedule(monkeypatch) -> None:
    """main() should pass demo safety controls into generate_schedule()."""
    generated = [Assignment(course=make_course(), room=None, timeslot=None)]
    captured: dict[str, object] = {}
    _stub_pipeline(monkeypatch, generated)

    def fake_generate_schedule(courses, rooms, **kwargs):
        captured.update(kwargs)
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

    assert captured["progress_interval"] == 25
    assert captured["max_retry_assignments"] == 20
    assert captured["max_candidate_patterns"] == 150


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
        lambda assignments, scope: exported.update({"assignments": assignments, "scope": scope}),
    )
    monkeypatch.setattr(sys, "argv", ["main.py", "--skip-optimisation", "--skip-unscheduled-diagnostics"])

    app.main()

    assert exported == {"assignments": generated, "scope": "dsc"}


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
