"""Tests for the clean release ZIP builder."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path


def load_builder_module():
    """Load the root packaging script without requiring scripts on sys.path."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_clean_release.py"
    spec = importlib.util.spec_from_file_location("build_clean_release", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, content: str = "x") -> None:
    """Create a file and its parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_required_release_tree(root: Path) -> None:
    """Create the minimum required files for a release ZIP test."""
    for path in [
        "README.md",
        "DEMO.md",
        "AI_USAGE_LOG.md",
        "DEMO_SCRIPT.md",
        "FINAL_RESULTS.md",
        "PRESENTATION_EVIDENCE.md",
        "RELEASE_CHECKLIST.md",
        "REPORT_EVIDENCE.md",
        "timetable_scheduler/AGENTS.md",
        "timetable_scheduler/main.py",
        "timetable_scheduler/run_ui.py",
        "timetable_scheduler/requirements.txt",
        "timetable_scheduler/tests/test_placeholder.py",
        "Data/Common Modules(Sheet1).csv",
        "Data/Requirements_ENG/2510_DSC.xlsx",
        "Data/Requirements Template.xlsx",
        "Data/TTConstraints_timetline(Constraints).xlsx",
        "Data/Uni-Wide Module.xlsx",
        "Data/Upload template_System (Template 2).xlsx",
        "Data/Venue Information(Campus Court).csv",
    ]:
        write_file(root / path)


def test_clean_release_zip_excludes_runtime_and_development_folders(tmp_path: Path) -> None:
    """Excluded folders and runtime files should never appear in the release ZIP."""
    builder = load_builder_module()
    create_required_release_tree(tmp_path)
    for path in [
        ".git/config",
        ".venv/Scripts/python.exe",
        "venv/bin/python",
        "env/bin/python",
        ".pytest_cache/README.md",
        "__pycache__/module.pyc",
        "timetable_scheduler/__pycache__/main.pyc",
        "timetable_scheduler/generated/run_summary.xlsx",
        "timetable_scheduler/output_files/template2.xlsx",
        "dist/old.zip",
        ".vscode/settings.json",
        "~$Template.xlsx",
        "scratch.tmp",
    ]:
        write_file(tmp_path / path)

    result = builder.build_release_zip(tmp_path, tmp_path / "dist" / "itp_group5_prototype.zip")

    with zipfile.ZipFile(result.output_path) as archive:
        names = archive.namelist()

    assert "README.md" in names
    assert "Data/Requirements_ENG/2510_DSC.xlsx" in names
    assert "Data/Upload template_System (Template 2).xlsx" in names
    assert not any(name.startswith(".git/") for name in names)
    assert not any(".venv/" in name or name.startswith("venv/") or name.startswith("env/") for name in names)
    assert not any("__pycache__/" in name or ".pytest_cache/" in name for name in names)
    assert not any("generated/" in name or "output_files/" in name for name in names)
    assert not any(name.startswith("dist/") for name in names)
    assert not any(name.startswith(".vscode/") for name in names)
    assert not any(name.endswith(".pyc") or name.startswith("~$") or name.endswith(".tmp") for name in names)
    assert result.file_count == len(names)
    assert result.size_bytes > 0


def test_clean_release_builder_fails_when_required_files_are_missing(tmp_path: Path) -> None:
    """Missing required deliverables should fail clearly before creating a ZIP."""
    builder = load_builder_module()

    try:
        builder.build_release_zip(tmp_path, tmp_path / "dist" / "itp_group5_prototype.zip")
    except FileNotFoundError as exc:
        assert "Required release files are missing" in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected missing release files to fail")
