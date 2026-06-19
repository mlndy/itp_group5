"""Headless tests for simplified desktop UI helpers."""

from __future__ import annotations

import inspect
import queue

import ui.app as app
import ui.styles as styles


def test_ui_source_exposes_one_consolidated_schedule_selector() -> None:
    """The simplified UI should show one consolidated schedule file selector."""
    source = inspect.getsource(app.TimetableSchedulerApp)

    assert "Consolidated Schedule" in source
    assert "Select the consolidated scheduling requirements workbook." in source
    assert source.count("askopenfilename") == 1
    assert "askdirectory" not in source
    assert "Template 1" not in source
    assert "Template 2" not in source


def test_ui_source_hides_room_selector_and_scheduling_options() -> None:
    """Technical path and scheduling controls should not appear in the UI."""
    source = inspect.getsource(app.TimetableSchedulerApp)

    assert "Room / supporting file" not in source
    assert "Scheduling Options" not in source
    assert "Includes DSC" not in source
    assert "Consolidated Template 1" not in source


def test_progress_stage_mapping_returns_bounded_values() -> None:
    """High-level pipeline messages should map to stage progress values."""
    for message in [
        "Loading input",
        "Running preflight checks",
        "Generating timetable",
        "Running optimiser",
        "Generating stakeholder reports",
        "Validating outputs",
        "Completed",
    ]:
        _stage, percent = app.progress_for_message(message)
        assert 0 <= percent <= 100


def test_generation_progress_maps_into_expected_range() -> None:
    """Course progress should occupy the 15 to 75 percent generation range."""
    assert app.generation_progress_percent(0, 100) == 15
    assert app.generation_progress_percent(50, 100) == 45
    assert app.generation_progress_percent(100, 100) == 75
    assert app.progress_for_message("Generating timetable: 25/100 ENG1001 Lecture") == ("Creating timetable", 30)


def test_worker_progress_only_queues_messages() -> None:
    """Worker callbacks must not update Tk widgets directly."""
    ui = object.__new__(app.TimetableSchedulerApp)
    ui.queue = queue.Queue()

    ui._worker_progress("Loading input")

    assert ui.queue.get_nowait() == ("progress", "Loading input")


def test_dark_style_configuration_uses_clam(monkeypatch) -> None:
    """Dark mode should be applied through the clam ttk theme."""
    calls: dict[str, object] = {"configure": {}, "map": {}}

    class FakeStyle:
        def __init__(self, root) -> None:
            self.root = root

        def theme_names(self):
            return ("default", "clam")

        def theme_use(self, name: str) -> None:
            calls["theme"] = name

        def configure(self, name: str, **kwargs) -> None:
            calls["configure"][name] = kwargs

        def map(self, name: str, **kwargs) -> None:
            calls["map"][name] = kwargs

    monkeypatch.setattr(styles.ttk, "Style", FakeStyle)

    styles.configure_styles(object())

    assert calls["theme"] == "clam"
    assert calls["configure"]["App.TFrame"]["background"] == styles.COLORS["window"]
    assert calls["configure"]["Primary.TButton"]["background"] == styles.COLORS["accent"]
    assert "Primary.TButton" in calls["map"]
