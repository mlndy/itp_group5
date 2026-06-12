"""Load SIT timetabling input files into dataclasses."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from config import (
    ACTIVITY_DURATION_HOURS,
    DEFAULT_UNKNOWN_ROOM_CAPACITY,
    TERM_WEEKS,
    VIRTUAL_ROOM_CAPACITY,
    VIRTUAL_ROOM_ID,
)
from data.models import Course, Room


COMMON_COLUMNS = {
    "prog_yr": ["Prog/Yr", "Prog Yr", "Programme/Year", "Programme Year"],
    "class_size": ["Class Size", "Size", "Enrolment"],
    "module_code": ["Module Code", "Module", "Course Code"],
    "activity": ["Activity", "Class Type", "Activity Type"],
    "delivery_mode": ["Delivery Mode", "Mode"],
    "teaching_weeks": ["Teaching Weeks", "Tri Week", "Weeks"],
    "staff_1": ["Staff ID 1", "Staff1", "SIS Staff ID"],
    "staff_2": ["Staff ID 2", "Staff2", "SIS Staff ID.1"],
    "staff_3": ["Staff ID 3", "Staff3", "SIS Staff ID.2"],
    "staff_name_1": ["Staff 1", "Staff1", "Staff"],
    "staff_name_2": ["Staff 2", "Staff2"],
    "staff_name_3": ["Staff 3", "Staff3"],
    "remarks": ["Remarks", "Remark"],
}


def _normalise_header(value: object) -> str:
    """Return a comparable column header string."""
    return re.sub(r"\s+", " ", str(value or "").strip())


def _find_header_row(path: Path, sheet_name: str) -> int:
    """Find the row index containing the Module sheet headers."""
    preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=20, engine="openpyxl")
    for idx, row in preview.iterrows():
        values = {_normalise_header(value) for value in row.tolist()}
        if "Module Code" in values and "Activity" in values:
            return int(idx)
    return 0


def _get_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    """Return the first matching column from candidate names."""
    normalised = {_normalise_header(col): col for col in df.columns}
    for candidate in candidates:
        if candidate in normalised:
            return normalised[candidate]
    return None


def _clean_text(value: object, default: str = "") -> str:
    """Return a stripped string, treating NaN as empty."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).strip()
    return text if text and text.lower() != "nan" else default


def _clean_int(value: object, default: int = 0) -> int:
    """Return an integer from messy Excel values."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    match = re.search(r"\d+", text)
    return int(match.group()) if match else default


def parse_teaching_weeks(value: object) -> list[int]:
    """Parse teaching weeks from values like '1,2,3' or '1-6,8,9'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return TERM_WEEKS.copy()
    if isinstance(value, int):
        return [value]
    if isinstance(value, float) and value.is_integer():
        return [int(value)]

    text = str(value).strip()
    if not text:
        return TERM_WEEKS.copy()

    weeks: set[int] = set()
    for part in re.split(r"[,;/\s]+", text):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if start_text.isdigit() and end_text.isdigit():
                weeks.update(range(int(start_text), int(end_text) + 1))
        elif part.isdigit():
            weeks.add(int(part))

    parsed = sorted(week for week in weeks if 1 <= week <= 20)
    return parsed or TERM_WEEKS.copy()


def infer_week_pattern(weeks: list[int]) -> str:
    """Infer ALL, ODD, EVEN, or CUSTOM from teaching weeks."""
    if not weeks:
        return "ALL"
    if all(week % 2 == 1 for week in weeks):
        return "ODD"
    if all(week % 2 == 0 for week in weeks):
        return "EVEN"
    if set(weeks) == set(TERM_WEEKS):
        return "ALL"
    return "CUSTOM"


def infer_duration_hrs(activity: str) -> int:
    """Infer a default duration from the activity name."""
    activity_key = activity.strip().lower()
    for keyword, duration in ACTIVITY_DURATION_HOURS.items():
        if keyword in activity_key:
            return duration
    return 2


def _collect_staff_ids(row: pd.Series, df: pd.DataFrame) -> list[str]:
    """Collect non-empty staff IDs from a row."""
    ids: list[str] = []
    for key in ["staff_1", "staff_2", "staff_3"]:
        col = _get_column(df, COMMON_COLUMNS[key])
        if not col:
            continue
        staff_id = _clean_text(row.get(col))
        if staff_id and staff_id not in ids:
            ids.append(staff_id)
    return ids


def _collect_staff_names(row: pd.Series, df: pd.DataFrame) -> list[str]:
    """Collect non-empty staff names from a row."""
    names: list[str] = []
    for key in ["staff_name_1", "staff_name_2", "staff_name_3"]:
        col = _get_column(df, COMMON_COLUMNS[key])
        if not col:
            continue
        name = _clean_text(row.get(col))
        if name and name not in names:
            names.append(name)
    return names


def load_common_modules(path: str | Path) -> set[str]:
    """Load common module codes from the common modules CSV."""
    path = Path(path)
    if not path.exists():
        return set()

    modules: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            module_text = _clean_text(row.get("Module"))
            for module in re.split(r"[/,;&]+", module_text):
                clean = module.strip().upper()
                if clean:
                    modules.add(clean)
    return modules


def load_courses_from_requirements(
    path: str | Path,
    common_modules: Optional[set[str]] = None,
    sheet_name: str = "Module",
) -> list[Course]:
    """Load course activities from a requirements workbook."""
    path = Path(path)
    common_modules = common_modules or set()
    header_row = _find_header_row(path, sheet_name)
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row, engine="openpyxl")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df.columns = [_normalise_header(col) for col in df.columns]

    prog_col = _get_column(df, COMMON_COLUMNS["prog_yr"])
    size_col = _get_column(df, COMMON_COLUMNS["class_size"])
    module_col = _get_column(df, COMMON_COLUMNS["module_code"])
    activity_col = _get_column(df, COMMON_COLUMNS["activity"])
    mode_col = _get_column(df, COMMON_COLUMNS["delivery_mode"])
    weeks_col = _get_column(df, COMMON_COLUMNS["teaching_weeks"])
    remarks_col = _get_column(df, COMMON_COLUMNS["remarks"])

    required = [prog_col, size_col, module_col, activity_col, mode_col, weeks_col]
    if any(col is None for col in required):
        raise ValueError(f"Missing required columns in {path.name}. Found: {list(df.columns)}")

    for col in [prog_col, size_col, module_col]:
        df[col] = df[col].ffill()

    courses: list[Course] = []
    for _, row in df.iterrows():
        module_code = _clean_text(row.get(module_col)).upper()
        activity = _clean_text(row.get(activity_col))
        prog_yr = _clean_text(row.get(prog_col))
        delivery_mode = _clean_text(row.get(mode_col), default="f2f")

        if not module_code or not activity or not prog_yr:
            continue
        if module_code.lower() in {"module code", "nan"}:
            continue

        weeks = parse_teaching_weeks(row.get(weeks_col))
        class_size = _clean_int(row.get(size_col), default=1)
        staff_ids = _collect_staff_ids(row, df)
        staff_names = _collect_staff_names(row, df)
        remarks = _clean_text(row.get(remarks_col)) if remarks_col else ""

        courses.append(
            Course(
                module_code=module_code,
                activity=activity,
                prog_yr=prog_yr,
                class_size=class_size,
                delivery_mode=delivery_mode,
                teaching_weeks=weeks,
                week_pattern=infer_week_pattern(weeks),
                staff_ids=staff_ids,
                duration_hrs=infer_duration_hrs(activity),
                is_common_module=module_code in common_modules,
                staff_names=staff_names,
                remarks=remarks,
                source_file=path.name,
                group_ids=[prog_yr],
            )
        )
    return courses


def load_courses_from_folder(folder: str | Path, common_modules: Optional[set[str]] = None) -> list[Course]:
    """Load courses from all requirement workbooks in a folder."""
    courses: list[Course] = []
    for path in sorted(Path(folder).glob("*.xlsx")):
        try:
            courses.extend(load_courses_from_requirements(path, common_modules=common_modules))
        except Exception as exc:
            print(f"Skipped {path.name}: {exc}")
    return courses


def _parse_capacity(value: object) -> int:
    """Parse capacity, using a safe high default for blank teaching rooms."""
    parsed = _clean_int(value, default=0)
    return parsed if parsed > 0 else DEFAULT_UNKNOWN_ROOM_CAPACITY


def load_rooms_from_csv(path: str | Path) -> list[Room]:
    """Load physical rooms from the venue CSV and add one virtual room."""
    path = Path(path)
    rooms: list[Room] = [
        Room(
            room_id=VIRTUAL_ROOM_ID,
            capacity=VIRTUAL_ROOM_CAPACITY,
            room_type="virtual",
            resource_type="Virtual Room",
            recording="Yes",
        )
    ]

    with path.open(newline="", encoding="cp1252") as file:
        reader = csv.DictReader(file)
        for row in reader:
            room_id = _clean_text(row.get("Location Name"))
            if not room_id:
                continue
            rooms.append(
                Room(
                    room_id=room_id,
                    capacity=_parse_capacity(row.get("Capacity")),
                    room_type="physical",
                    resource_type=_clean_text(row.get("Resource Type")),
                    recording=_clean_text(row.get("Recording?")),
                )
            )
    return rooms
