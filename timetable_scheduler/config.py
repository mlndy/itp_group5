"""Project-wide rules for the SIT timetabling prototype."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output_files"
GENERATED_DIR = BASE_DIR / "generated"

DEFAULT_COURSE_FILE = INPUT_DIR / "2510_DSC.xlsx"
DEFAULT_ENGINEERING_FOLDER = INPUT_DIR / "Requirements_ENG"
DEFAULT_ROOM_FILE = INPUT_DIR / "Venue Information(Campus Court).csv"
DEFAULT_COMMON_MODULE_FILE = INPUT_DIR / "Common Modules(Sheet1).csv"
DEFAULT_TEMPLATE2_FILE = INPUT_DIR / "Upload template_System (Template 2).xlsx"
DEFAULT_LOADER_REPORT_FILE = GENERATED_DIR / "loader_report.xlsx"
DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE = GENERATED_DIR / "unscheduled_diagnostics.xlsx"
DEFAULT_PREFLIGHT_REPORT_FILE = GENERATED_DIR / "preflight_report.xlsx"
DEFAULT_RUN_SUMMARY_FILE = GENERATED_DIR / "run_summary.xlsx"
DEFAULT_STAKEHOLDER_VIEWS_FILE = GENERATED_DIR / "stakeholder_views.xlsx"
DEFAULT_RUN_MANIFEST_FILE = GENERATED_DIR / "run_manifest.xlsx"

VALID_DAYS: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_ABBREVIATIONS: dict[str, str] = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri",
}

EARLIEST_START_HOUR = 9
LATEST_END_HOUR = 18
VALID_START_TIMES: list[str] = [f"{hour:02d}:00" for hour in range(EARLIEST_START_HOUR, LATEST_END_HOUR)]

# Flexible lunch rule: each group should keep at least one free 1-hour block in this window.
LUNCH_START_HOUR = 11
LUNCH_END_HOUR = 14
LUNCH_BLOCKS: list[str] = [f"{hour:02d}:00" for hour in range(LUNCH_START_HOUR, LUNCH_END_HOUR)]

# Hard blocked periods.
BLOCKED_START_TIMES: dict[str, set[str]] = {
    "Wednesday": {"13:00", "14:00", "15:00", "16:00", "17:00"},
    "Friday": {"12:00", "13:00", "17:00"},
}

TERM_WEEKS: list[int] = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13]

# Prototype calendar assumption: the input files provide teaching week numbers,
# not exact dates. Public holidays and term breaks are therefore represented by
# teaching week for this milestone.
TERM_BREAK_WEEKS: set[int] = {7}
PUBLIC_HOLIDAY_WEEKS: set[int] = set()
BLOCKED_WEEKS: set[int] = TERM_BREAK_WEEKS | PUBLIC_HOLIDAY_WEEKS

VIRTUAL_ROOM_ID = "ONLINE_ROOM"
VIRTUAL_ROOM_CAPACITY = 9999
# False means the virtual-room object is a delivery-mode placeholder.
# Multiple unrelated online classes may use it concurrently. Tutor and
# student-group clashes still apply, and physical rooms remain exclusive.
VIRTUAL_ROOM_IS_EXCLUSIVE = False
DEFAULT_UNKNOWN_ROOM_CAPACITY = 999
MIN_ROOM_UTILISATION = 0.60
MAX_CONSECUTIVE_HOURS = 4
MAX_TUTOR_IDLE_GAP_HOURS = 2
SHORT_CAMPUS_DAY_MIN_HOURS = 1
SHORT_CAMPUS_DAY_MAX_HOURS = 2
PREFERRED_ONLINE_DAYS: set[str] = {"Monday", "Tuesday"}

ACTIVITY_DURATION_HOURS: dict[str, int] = {
    "lecture": 2,
    "lectorial": 2,
    "tutorial": 2,
    "laboratory": 3,
    "lab": 3,
    "practical": 3,
    "workshop": 2,
    "seminar": 2,
    "quiz": 1,
    "exam": 2,
}

ACTIVITY_TYPE_CODES: dict[str, str] = {
    "lecture": "LEC",
    "lectorial": "LET",
    "tutorial": "TUT",
    "laboratory": "LAB",
    "lab": "LAB",
    "practical": "LAB",
    "workshop": "WRK",
    "seminar": "SEM",
    "quiz": "QUIZ",
    "exam": "EXAM",
}

# Soft preference: avoid using these as first/last teaching slots where possible.
FIRST_SLOT = "09:00"
LAST_SLOT_STARTS: set[str] = {"16:00", "17:00"}

SOFT_RULE_LOW_ROOM_UTILISATION = "Low room utilisation"
SOFT_RULE_FIRST_SLOT = "Uses first teaching slot"
SOFT_RULE_ENDS_AFTER_17 = "Class does not end by 17:00"
SOFT_RULE_ONLINE_F2F_SWITCH = "Adjacent online/F2F switch"
SOFT_RULE_TUTOR_IDLE_GAP = "Tutor idle gap longer than configured limit"
SOFT_RULE_WASTED_FREE_SLOT = "Tutor timetable has wasted free slot"
SOFT_RULE_BACK_TO_BACK_HOURS = "Back-to-back classes exceed configured consecutive hours"
SOFT_RULE_MAX_CONSECUTIVE_HOURS = "More than configured consecutive teaching hours"
SOFT_RULE_SHORT_CAMPUS_DAY = "Short campus day"
SOFT_RULE_PROGRAMME_ONLINE_DAY_SPREAD = "Programme online-day clustering"
SOFT_RULE_ONLINE_PREFERRED_DAY = "Online class outside preferred Monday/Tuesday window"

SOFT_CONSTRAINT_WEIGHTS: dict[str, int] = {
    SOFT_RULE_LOW_ROOM_UTILISATION: 1,
    SOFT_RULE_FIRST_SLOT: 1,
    SOFT_RULE_ENDS_AFTER_17: 1,
    SOFT_RULE_ONLINE_F2F_SWITCH: 2,
    SOFT_RULE_TUTOR_IDLE_GAP: 2,
    SOFT_RULE_WASTED_FREE_SLOT: 1,
    SOFT_RULE_BACK_TO_BACK_HOURS: 2,
    SOFT_RULE_MAX_CONSECUTIVE_HOURS: 3,
    SOFT_RULE_SHORT_CAMPUS_DAY: 2,
    SOFT_RULE_PROGRAMME_ONLINE_DAY_SPREAD: 2,
    SOFT_RULE_ONLINE_PREFERRED_DAY: 1,
}
