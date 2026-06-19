"""Tests for the desktop UI launcher."""

from __future__ import annotations

import importlib


def test_importing_run_ui_does_not_launch_window(monkeypatch) -> None:
    """Importing the launcher should not call run_app automatically."""
    launched: list[bool] = []
    import ui.app

    monkeypatch.setattr(ui.app, "run_app", lambda: launched.append(True))

    module = importlib.import_module("run_ui")
    importlib.reload(module)

    assert launched == []
    assert callable(module.main)
