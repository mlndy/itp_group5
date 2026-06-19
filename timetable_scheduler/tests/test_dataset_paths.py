"""Tests for supplied Engineering dataset resource paths."""

from __future__ import annotations

from pathlib import Path

from config import (
    DEFAULT_COMMON_MODULE_FILE,
    DEFAULT_CONSTRAINTS_FILE,
    DEFAULT_ENGINEERING_FOLDER,
    DEFAULT_ROOM_FILE,
    DEFAULT_TEMPLATE2_FILE,
    DEFAULT_UNI_WIDE_MODULE_FILE,
)
from data.loader import WorkbookRole, detect_workbook_role, load_common_modules, load_courses_from_folder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "Data"


def test_default_dataset_paths_resolve_to_supplied_data_folder() -> None:
    """Runtime defaults should point at the supplied Engineering dataset when present."""
    assert DEFAULT_ENGINEERING_FOLDER == DATA_DIR / "Requirements_ENG"
    assert DEFAULT_COMMON_MODULE_FILE == DATA_DIR / "Common Modules(Sheet1).csv"
    assert DEFAULT_ROOM_FILE == DATA_DIR / "Venue Information(Campus Court).csv"
    assert DEFAULT_TEMPLATE2_FILE == DATA_DIR / "Upload template_System (Template 2).xlsx"
    assert DEFAULT_CONSTRAINTS_FILE == DATA_DIR / "TTConstraints_timetline(Constraints).xlsx"
    assert DEFAULT_UNI_WIDE_MODULE_FILE == DATA_DIR / "Uni-Wide Module.xlsx"
    for path in [
        DEFAULT_ENGINEERING_FOLDER,
        DEFAULT_COMMON_MODULE_FILE,
        DEFAULT_ROOM_FILE,
        DEFAULT_TEMPLATE2_FILE,
        DEFAULT_CONSTRAINTS_FILE,
        DEFAULT_UNI_WIDE_MODULE_FILE,
    ]:
        assert path.exists()


def test_engineering_requirement_workbooks_are_template1_structured() -> None:
    """The 35 Engineering programme workbooks should be recognised as Template 1 inputs."""
    workbooks = sorted(DEFAULT_ENGINEERING_FOLDER.glob("*.xlsx"))
    unrecognised = [
        f"{detect_workbook_role(path).value}: {path.name}"
        for path in workbooks
        if detect_workbook_role(path) != WorkbookRole.TEMPLATE1_REQUIREMENTS
    ]

    assert len(workbooks) == 35
    assert unrecognised == []


def test_common_modules_and_dsc_are_part_of_engineering_dataset() -> None:
    """Common modules should load and DSC should appear in the Engineering input folder."""
    common_modules = load_common_modules(DEFAULT_COMMON_MODULE_FILE)
    courses, report = load_courses_from_folder(DEFAULT_ENGINEERING_FOLDER, common_modules=common_modules)

    assert {"ENG1001", "ENG1004", "INF1002", "INF1003"} <= common_modules
    assert any("DSC" in course.prog_yr.upper() or "DSC" in course.source_file.upper() for course in courses)
    assert report.workbooks
