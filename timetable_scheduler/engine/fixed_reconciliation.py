"""Reconcile structured fixed sessions with ordinary Engineering requirements."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd

from data.fixed_sessions import FixedSessionLoaderReport
from data.models import Course, FixedSession
from generator.fixed_scheduler import normalise_module_code

SUMMARY_COLUMNS = ["Metric", "Value"]
MATCH_COLUMNS = [
    "fixed source",
    "fixed programme/year",
    "fixed module",
    "fixed group",
    "fixed weeks",
    "matched source",
    "matched programme/year",
    "matched module",
    "matched activity",
    "matched weeks",
    "match method",
    "confidence",
    "severity",
    "teaching occurrences",
    "duplicate prevention result",
    "manual-review reason",
]
DEMAND_COLUMNS = ["Metric", "Assignment-level total", "Teaching-occurrence total"]


@dataclass(slots=True)
class FixedReconciliationReport:
    """Outcome of fixed/non-fixed demand reconciliation."""

    exact_matches: list[dict[str, object]] = field(default_factory=list)
    partial_matches: list[dict[str, object]] = field(default_factory=list)
    standalone_fixed: list[dict[str, object]] = field(default_factory=list)
    ambiguous_matches: list[dict[str, object]] = field(default_factory=list)
    invalid_fixed_rows: list[dict[str, object]] = field(default_factory=list)
    original_nonfixed_assignments: int = 0
    original_nonfixed_occurrences: int = 0
    converted_assignments: int = 0
    converted_occurrences: int = 0
    standalone_assignments: int = 0
    standalone_occurrences: int = 0

    @property
    def has_critical_issues(self) -> bool:
        """Return True when reconciliation cannot safely proceed."""
        critical_invalid = any(row.get("severity", "critical") == "critical" for row in self.invalid_fixed_rows)
        return bool(self.partial_matches or self.ambiguous_matches or critical_invalid)

    @property
    def final_assignment_total(self) -> int:
        """Return reconciled assignment-level demand."""
        return self.original_nonfixed_assignments - self.converted_assignments + self.standalone_assignments

    @property
    def final_occurrence_total(self) -> int:
        """Return reconciled teaching-occurrence demand."""
        return self.original_nonfixed_occurrences - self.converted_occurrences + self.standalone_occurrences


def normalise_programme_year(value: str) -> str:
    """Normalise programme/year labels for conservative matching."""
    text = re.sub(r"\s+", " ", str(value or "").upper().replace("YEAR", "Y").replace("YR", "Y")).strip()
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    text = re.sub(r"\bY\s*([0-9])\b", r"Y\1", text)
    return text


def _course_weeks(course: Course) -> set[int]:
    """Return teaching weeks for one course."""
    return set(course.teaching_weeks)


def _staff_overlap(session: FixedSession, course: Course) -> bool:
    """Return True when staff evidence overlaps or either side lacks staff IDs."""
    fixed_staff = {staff.casefold() for staff in (*session.staff_ids, *session.staff_names) if staff}
    course_staff = {staff.casefold() for staff in (*course.staff_ids, *course.staff_names) if staff}
    return not fixed_staff or not course_staff or bool(fixed_staff & course_staff)


def _programme_matches(session: FixedSession, course: Course) -> bool:
    """Return True when programme/year labels match conservatively."""
    fixed = normalise_programme_year(session.programme_year)
    course_label = normalise_programme_year(course.prog_yr)
    return fixed == course_label or fixed.startswith(f"{course_label}/") or course_label.startswith(f"{fixed}/")


def _candidate_courses(session: FixedSession, courses: list[Course]) -> list[Course]:
    """Return non-fixed courses that could match a fixed session."""
    module = normalise_module_code(session.module_code)
    return [
        course
        for course in courses
        if normalise_module_code(course.module_code) == module
        and _programme_matches(session, course)
        and bool(set(session.teaching_weeks) & _course_weeks(course))
        and _staff_overlap(session, course)
    ]


def _source(session: FixedSession) -> str:
    """Return a compact fixed source marker."""
    return f"{session.source_file}:{session.source_sheet}:{session.source_row}"


def _match_row(
    session: FixedSession,
    course: Course | None,
    *,
    method: str,
    confidence: str,
    occurrences: int,
    result: str,
    reason: str = "",
) -> dict[str, object]:
    """Build one reconciliation row."""
    return {
        "fixed source": _source(session),
        "fixed programme/year": session.programme_year,
        "fixed module": normalise_module_code(session.module_code),
        "fixed group": session.group_id,
        "fixed weeks": ", ".join(str(week) for week in session.teaching_weeks),
        "matched source": course.source_file if course else "",
        "matched programme/year": course.prog_yr if course else "",
        "matched module": course.module_code if course else "",
        "matched activity": course.activity if course else "",
        "matched weeks": ", ".join(str(week) for week in course.teaching_weeks) if course else "",
        "match method": method,
        "confidence": confidence,
        "teaching occurrences": occurrences,
        "duplicate prevention result": result,
        "manual-review reason": reason,
    }


def _loaded_fixed_sources(loader_report: FixedSessionLoaderReport) -> set[str]:
    """Return fixed source markers that were loaded as valid sessions."""
    return {
        f"{row['source workbook']}:{row['source sheet']}:{row['source row']}"
        for row in loader_report.audit_rows
        if row.get("loader status") == "loaded"
    }


def _invalid_rows(loader_report: FixedSessionLoaderReport) -> list[dict[str, object]]:
    """Return invalid or incomplete fixed source rows."""
    rows: list[dict[str, object]] = []
    for row in loader_report.audit_rows:
        if row.get("loader status") == "loaded":
            continue
        rows.append(
            {
                "fixed source": f"{row.get('source workbook')}:{row.get('source sheet')}:{row.get('source row')}",
                "fixed programme/year": row.get("programme/year", ""),
                "fixed module": row.get("module code", ""),
                "fixed group": row.get("group", ""),
                "fixed weeks": row.get("teaching weeks", ""),
                "matched source": "",
                "matched programme/year": "",
                "matched module": "",
                "matched activity": "",
                "matched weeks": "",
                "match method": "invalid fixed source row",
                "confidence": "none",
                "severity": row.get("severity", "critical"),
                "teaching occurrences": 0,
                "duplicate prevention result": "blocked",
                "manual-review reason": row.get("issue", ""),
            }
        )
    return rows


def reconcile_fixed_sessions(
    fixed_sessions: list[FixedSession],
    courses: list[Course],
    loader_report: FixedSessionLoaderReport,
) -> FixedReconciliationReport:
    """Reconcile fixed sessions to existing non-fixed requirements."""
    report = FixedReconciliationReport(
        original_nonfixed_assignments=len(courses),
        original_nonfixed_occurrences=sum(len(course.teaching_weeks) for course in courses),
        invalid_fixed_rows=_invalid_rows(loader_report),
    )
    loaded_sources = _loaded_fixed_sources(loader_report)
    for session in fixed_sessions:
        if _source(session) not in loaded_sources:
            continue
        candidates = _candidate_courses(session, courses)
        exact = [
            course
            for course in candidates
            if set(session.teaching_weeks) <= _course_weeks(course)
            and abs(float(course.duration_hrs) - session.duration_hours) < 0.01
        ]
        occurrences = len(session.teaching_weeks)
        if len(exact) == 1:
            report.exact_matches.append(
                _match_row(
                    session,
                    exact[0],
                    method="programme/module/staff/duration/week subset",
                    confidence="high",
                    occurrences=occurrences,
                    result="converted fixed portion without adding duplicate demand",
                )
            )
            report.converted_assignments += 1
            report.converted_occurrences += occurrences
        elif len(exact) > 1:
            report.ambiguous_matches.append(
                _match_row(
                    session,
                    exact[0],
                    method="multiple exact candidates",
                    confidence="ambiguous",
                    occurrences=occurrences,
                    result="blocked",
                    reason=f"{len(exact)} matching non-fixed requirements found.",
                )
            )
        elif len(candidates) == 1:
            report.partial_matches.append(
                _match_row(
                    session,
                    candidates[0],
                    method="programme/module/staff/week overlap",
                    confidence="medium",
                    occurrences=occurrences,
                    result="manual review before split",
                    reason="Only partial evidence exists; split must be reviewed before preventing duplicate demand.",
                )
            )
        elif len(candidates) > 1:
            report.ambiguous_matches.append(
                _match_row(
                    session,
                    candidates[0],
                    method="multiple partial candidates",
                    confidence="ambiguous",
                    occurrences=occurrences,
                    result="blocked",
                    reason=f"{len(candidates)} possible non-fixed requirements found.",
                )
            )
        else:
            report.standalone_fixed.append(
                _match_row(
                    session,
                    None,
                    method="no safe non-fixed match",
                    confidence="standalone",
                    occurrences=occurrences,
                    result="added once as standalone fixed demand",
                )
            )
            report.standalone_assignments += 1
            report.standalone_occurrences += occurrences
    return report


def _summary_df(report: FixedReconciliationReport) -> pd.DataFrame:
    """Return reconciliation summary metrics."""
    rows = [
        {"Metric": "Original non-fixed assignments", "Value": report.original_nonfixed_assignments},
        {"Metric": "Original non-fixed teaching occurrences", "Value": report.original_nonfixed_occurrences},
        {"Metric": "Exact matches", "Value": len(report.exact_matches)},
        {"Metric": "Partial matches", "Value": len(report.partial_matches)},
        {"Metric": "Standalone fixed rows", "Value": len(report.standalone_fixed)},
        {"Metric": "Ambiguous matches", "Value": len(report.ambiguous_matches)},
        {"Metric": "Invalid fixed rows", "Value": len(report.invalid_fixed_rows)},
        {"Metric": "Demand converted to fixed assignments", "Value": report.converted_assignments},
        {"Metric": "Demand converted to fixed teaching occurrences", "Value": report.converted_occurrences},
        {"Metric": "Standalone fixed assignments", "Value": report.standalone_assignments},
        {"Metric": "Standalone fixed teaching occurrences", "Value": report.standalone_occurrences},
        {"Metric": "Final assignment-level demand", "Value": report.final_assignment_total},
        {"Metric": "Final teaching-occurrence demand", "Value": report.final_occurrence_total},
        {"Metric": "Reconciliation status", "Value": "FAIL" if report.has_critical_issues else "PASS"},
    ]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _demand_df(report: FixedReconciliationReport) -> pd.DataFrame:
    """Return assignment and occurrence-level demand reconciliation."""
    rows = [
        {
            "Metric": "Original non-fixed demand",
            "Assignment-level total": report.original_nonfixed_assignments,
            "Teaching-occurrence total": report.original_nonfixed_occurrences,
        },
        {
            "Metric": "Demand converted to fixed",
            "Assignment-level total": -report.converted_assignments,
            "Teaching-occurrence total": -report.converted_occurrences,
        },
        {
            "Metric": "Standalone fixed demand",
            "Assignment-level total": report.standalone_assignments,
            "Teaching-occurrence total": report.standalone_occurrences,
        },
        {
            "Metric": "Final total demand",
            "Assignment-level total": report.final_assignment_total,
            "Teaching-occurrence total": report.final_occurrence_total,
        },
    ]
    return pd.DataFrame(rows, columns=DEMAND_COLUMNS)


def export_fixed_reconciliation_report(report: FixedReconciliationReport, output_path: Path) -> None:
    """Export fixed/non-fixed reconciliation evidence."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _summary_df(report).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(report.exact_matches, columns=MATCH_COLUMNS).to_excel(writer, sheet_name="Exact Matches", index=False)
        pd.DataFrame(report.partial_matches, columns=MATCH_COLUMNS).to_excel(writer, sheet_name="Partial Matches", index=False)
        pd.DataFrame(report.standalone_fixed, columns=MATCH_COLUMNS).to_excel(writer, sheet_name="Standalone Fixed", index=False)
        pd.DataFrame(report.ambiguous_matches, columns=MATCH_COLUMNS).to_excel(writer, sheet_name="Ambiguous Matches", index=False)
        pd.DataFrame(report.invalid_fixed_rows, columns=MATCH_COLUMNS).to_excel(writer, sheet_name="Invalid Fixed Rows", index=False)
        _demand_df(report).to_excel(writer, sheet_name="Demand Reconciliation", index=False)


def _course_match_key(course: Course) -> tuple[str, str, str, str, str]:
    """Return a conservative course identity key from reconciliation rows."""
    return (
        course.source_file,
        normalise_programme_year(course.prog_yr),
        normalise_module_code(course.module_code),
        course.activity,
        ", ".join(str(week) for week in course.teaching_weeks),
    )


def adjusted_courses_after_exact_matches(courses: list[Course], report: FixedReconciliationReport) -> list[Course]:
    """Remove exact matched fixed weeks from movable non-fixed demand."""
    remove_weeks: dict[tuple[str, str, str, str, str], set[int]] = defaultdict(set)
    for row in report.exact_matches:
        key = (
            str(row["matched source"]),
            normalise_programme_year(str(row["matched programme/year"])),
            normalise_module_code(str(row["matched module"])),
            str(row["matched activity"]),
            str(row["matched weeks"]),
        )
        remove_weeks[key].update(int(week) for week in str(row["fixed weeks"]).replace(" ", "").split(",") if week)

    adjusted: list[Course] = []
    for course in courses:
        key = _course_match_key(course)
        weeks_to_remove = remove_weeks.get(key, set())
        if not weeks_to_remove:
            adjusted.append(course)
            continue
        remaining_weeks = [week for week in course.teaching_weeks if week not in weeks_to_remove]
        if remaining_weeks:
            adjusted.append(replace(course, teaching_weeks=remaining_weeks))
    return adjusted
