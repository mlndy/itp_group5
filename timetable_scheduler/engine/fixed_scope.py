"""Scope fixed-session support rows to the selected scheduling input."""

from __future__ import annotations

from data.fixed_sessions import FixedSessionLoaderReport
from data.models import Course, FixedSession
from engine.fixed_reconciliation import normalise_programme_year
from generator.fixed_scheduler import normalise_module_code


def selected_module_codes(courses: list[Course]) -> set[str]:
    """Return normalised module codes represented by selected demand."""
    return {normalise_module_code(course.module_code) for course in courses if course.module_code}


def _programme_matches(fixed_programme: str, course_programme: str) -> bool:
    """Return True for conservative programme/year matches."""
    fixed = normalise_programme_year(fixed_programme)
    course = normalise_programme_year(course_programme)
    return fixed == course or fixed.startswith(f"{course}/") or course.startswith(f"{fixed}/")


def _session_scope_status(session: FixedSession, courses: list[Course]) -> str:
    """Classify one fixed session against the selected input scope."""
    module = normalise_module_code(session.module_code)
    module_courses = [course for course in courses if normalise_module_code(course.module_code) == module]
    if not module_courses:
        return "OUT_OF_SCOPE_FIXED"
    if any(_programme_matches(session.programme_year, course.prog_yr) for course in module_courses):
        return "IN_SCOPE_FIXED"
    if any(course.is_common_module for course in module_courses):
        return "IN_SCOPE_FIXED"
    return "AMBIGUOUS_SCOPE"


def _audit_scope_status(row: dict[str, object], courses: list[Course]) -> str:
    """Classify one fixed loader audit row against the selected input scope."""
    module = normalise_module_code(str(row.get("module code") or ""))
    module_courses = [course for course in courses if normalise_module_code(course.module_code) == module]
    if not module_courses:
        return "OUT_OF_SCOPE_FIXED"
    programme = str(row.get("programme/year") or "")
    if any(_programme_matches(programme, course.prog_yr) for course in module_courses):
        return "IN_SCOPE_FIXED"
    if any(course.is_common_module for course in module_courses):
        return "IN_SCOPE_FIXED"
    return "AMBIGUOUS_SCOPE"


def _source_key(source_file: object, source_sheet: object, source_row: object) -> str:
    """Return a fixed source-row key."""
    return f"{source_file}:{source_sheet}:{source_row}"


def _audit_key(row: dict[str, object]) -> str:
    """Return a fixed source-row key for an audit row."""
    return _source_key(row.get("source workbook"), row.get("source sheet"), row.get("source row"))


def _issue_key(issue: dict[str, object], workbook_name: str) -> str:
    """Return a fixed source-row key for an issue row."""
    return _source_key(workbook_name, issue.get("sheet"), issue.get("row"))


def filter_fixed_sessions_to_selected_scope(
    fixed_sessions: list[FixedSession],
    loader_report: FixedSessionLoaderReport,
    courses: list[Course],
) -> tuple[list[FixedSession], FixedSessionLoaderReport, list[dict[str, object]]]:
    """Return fixed sessions and diagnostics scoped to selected courses."""
    statuses: dict[str, str] = {}
    scoped_sessions: list[FixedSession] = []
    for session in fixed_sessions:
        key = _source_key(session.source_file, session.source_sheet, session.source_row)
        status = _session_scope_status(session, courses)
        statuses[key] = status
        if status == "IN_SCOPE_FIXED":
            scoped_sessions.append(session)

    scoped_audit_rows: list[dict[str, object]] = []
    scope_rows: list[dict[str, object]] = []
    included_keys: set[str] = set()
    for row in loader_report.audit_rows:
        key = _audit_key(row)
        status = statuses.get(key) or _audit_scope_status(row, courses)
        scoped = {**row, "scope status": status}
        scope_rows.append(scoped)
        if status in {"IN_SCOPE_FIXED", "AMBIGUOUS_SCOPE"}:
            scoped_audit_rows.append(scoped)
            included_keys.add(key)

    workbook_name = str(loader_report.workbook_path).replace("\\", "/").rsplit("/", 1)[-1]
    scoped_issues = [
        issue
        for issue in loader_report.issues
        if _issue_key(issue, workbook_name) in included_keys
    ]
    scoped_report = FixedSessionLoaderReport(
        workbook_path=loader_report.workbook_path,
        authoritative_sheets=list(loader_report.authoritative_sheets),
        ignored_sheets=list(loader_report.ignored_sheets),
        source_rows=len(scoped_audit_rows),
        duplicate_rows_removed=0,
        issues=scoped_issues,
        audit_rows=scoped_audit_rows,
    )
    return scoped_sessions, scoped_report, scope_rows
