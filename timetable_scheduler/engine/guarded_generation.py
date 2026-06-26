"""Guarded partial-generation helpers for fixed-session input issues."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pandas as pd

from data.fixed_sessions import FixedSessionLoaderReport
from data.models import Assignment, Course, FixedSession
from engine.demand_metrics import build_requirement_demands
from engine.fixed_reconciliation import FixedReconciliationReport, normalise_programme_year


class ValidationDisposition(Enum):
    """Validation disposition used by the guarded scheduler."""

    GLOBAL_BLOCK = "global_block"
    QUARANTINE = "quarantine"
    WARNING = "warning"
    INFORMATION = "information"


@dataclass(frozen=True, slots=True)
class QuarantinedRequirement:
    """One source requirement excluded from automatic scheduling."""

    requirement_id: str
    source_file: str
    source_sheet: str
    source_row: int | str
    programme_year: str | None
    module_code: str | None
    activity: str | None
    teaching_weeks: tuple[int, ...]
    disposition_reason: str
    issue_codes: tuple[str, ...]
    affected_occurrences: int
    related_requirement_ids: tuple[str, ...] = ()
    original_values: dict[str, object] = field(default_factory=dict)
    normalised_values: dict[str, object] = field(default_factory=dict)
    conflict_group_id: str = ""
    query_id: str = ""


@dataclass(slots=True)
class GuardedGenerationState:
    """Inputs and derived decisions for guarded generation."""

    global_errors: list[dict[str, object]]
    quarantined_requirements: list[QuarantinedRequirement]
    anchored_fixed_assignments: list[Assignment]
    quarantined_fixed_assignments: list[Assignment]
    warning_issues: list[dict[str, object]]

    @property
    def can_generate(self) -> bool:
        """Return True when no global blocking errors remain."""
        return not self.global_errors


def source_ref(source_file: object, source_sheet: object, source_row: object) -> str:
    """Return a stable source-row reference."""
    return f"{source_file}:{source_sheet}:{source_row}"


def fixed_session_ref(session: FixedSession) -> str:
    """Return the source reference for one fixed session."""
    return source_ref(session.source_file, session.source_sheet, session.source_row)


def assignment_source_refs(assignment: Assignment) -> tuple[str, ...]:
    """Return all fixed source references attached to an assignment."""
    return tuple(part.strip() for part in str(assignment.fixed_source or "").split("|") if part.strip())


def quarantine_source_set(quarantined: list[QuarantinedRequirement]) -> set[str]:
    """Return quarantined source-reference IDs."""
    return {item.requirement_id for item in quarantined}


def filter_quarantined_fixed_assignments(
    assignments: list[Assignment],
    quarantined: list[QuarantinedRequirement],
) -> tuple[list[Assignment], list[Assignment]]:
    """Split fixed assignments into anchored and quarantined rows."""
    quarantined_refs = quarantine_source_set(quarantined)
    anchored: list[Assignment] = []
    excluded: list[Assignment] = []
    for assignment in assignments:
        refs = set(assignment_source_refs(assignment))
        if refs & quarantined_refs:
            excluded.append(assignment)
        else:
            anchored.append(assignment)
    return anchored, excluded


def build_guarded_generation_state(
    *,
    courses: list[Course],
    rooms_loaded: int,
    fixed_sessions: list[FixedSession],
    fixed_loader_report: FixedSessionLoaderReport,
    reconciliation_report: FixedReconciliationReport,
    fixed_assignments: list[Assignment],
    fixed_assignment_issues: list[dict[str, object]],
) -> GuardedGenerationState:
    """Build guarded-generation decisions from validation evidence."""
    global_errors = _global_errors(courses, rooms_loaded, fixed_loader_report)
    quarantined = build_quarantined_requirements(
        fixed_sessions=fixed_sessions,
        loader_report=fixed_loader_report,
        reconciliation_report=reconciliation_report,
        fixed_assignment_issues=fixed_assignment_issues,
    )
    anchored, excluded = filter_quarantined_fixed_assignments(fixed_assignments, quarantined)
    warnings = [issue for issue in fixed_assignment_issues if str(issue.get("severity", "")).casefold() == "warning"]
    return GuardedGenerationState(global_errors, quarantined, anchored, excluded, warnings)


def build_quarantined_requirements(
    *,
    fixed_sessions: list[FixedSession],
    loader_report: FixedSessionLoaderReport,
    reconciliation_report: FixedReconciliationReport,
    fixed_assignment_issues: list[dict[str, object]],
) -> list[QuarantinedRequirement]:
    """Return deduplicated quarantined fixed-session requirements."""
    session_index = {fixed_session_ref(session): session for session in fixed_sessions}
    records: dict[str, dict[str, object]] = {}

    for row in loader_report.audit_rows:
        severity = str(row.get("severity") or "").casefold()
        status = str(row.get("loader status") or "").casefold()
        if severity != "critical" or status == "loaded":
            continue
        ref = source_ref(row.get("source workbook"), row.get("source sheet"), row.get("source row"))
        _merge_quarantine_record(records, ref, row, "QUARANTINED_INCOMPLETE", str(row.get("issue") or "Invalid fixed source row."))

    for row in reconciliation_report.partial_matches:
        ref = str(row.get("fixed source") or "")
        _merge_quarantine_record(records, ref, row, "QUARANTINED_AMBIGUOUS", str(row.get("manual-review reason") or "Partial fixed/non-fixed mapping."))
    for row in reconciliation_report.ambiguous_matches:
        ref = str(row.get("fixed source") or "")
        _merge_quarantine_record(records, ref, row, "QUARANTINED_AMBIGUOUS", str(row.get("manual-review reason") or "Ambiguous fixed/non-fixed mapping."))
    for row in reconciliation_report.invalid_fixed_rows:
        if str(row.get("severity") or "critical").casefold() != "critical":
            continue
        ref = str(row.get("fixed source") or "")
        _merge_quarantine_record(records, ref, row, "QUARANTINED_INCOMPLETE", str(row.get("manual-review reason") or "Invalid fixed source row."))

    for issue in fixed_assignment_issues:
        if str(issue.get("severity") or "").casefold() != "critical":
            continue
        refs = _issue_source_refs(issue)
        group_id = _conflict_group_id(refs, str(issue.get("problem") or ""))
        code = _issue_code(issue)
        for ref in refs:
            source_row = _source_row_from_session_or_issue(ref, session_index, issue)
            _merge_quarantine_record(records, ref, source_row, code, str(issue.get("problem") or "Fixed-session validation issue."), refs, group_id)

    return [_build_quarantine(record, session_index) for _, record in sorted(records.items())]


def quarantined_requirement_courses(quarantined: list[QuarantinedRequirement]) -> list[Course]:
    """Convert quarantine records with known weeks into demand courses."""
    courses: list[Course] = []
    for item in quarantined:
        if not item.teaching_weeks:
            continue
        courses.append(
            Course(
                module_code=item.module_code or "UNKNOWN",
                activity=item.activity or "Fixed Session",
                prog_yr=item.programme_year or "",
                class_size=1,
                delivery_mode="f2f",
                teaching_weeks=list(item.teaching_weeks),
                week_pattern="CUSTOM",
                staff_ids=[],
                duration_hrs=1,
                source_file=item.source_file,
                source_sheet=item.source_sheet,
                source_row=int(item.source_row) if str(item.source_row).isdigit() else None,
                is_fixed_requirement=True,
                fixed_source=item.requirement_id,
            )
        )
    return courses


def build_programme_completeness_rows(
    demand_courses: list[Course],
    assignments: list[Assignment],
    quarantined: list[QuarantinedRequirement],
    submission_ready_programmes: set[str] | None = None,
) -> list[dict[str, object]]:
    """Return programme-year completion rows for guarded generation."""
    required: Counter[str] = Counter()
    scheduled: Counter[str] = Counter()
    fixed: Counter[str] = Counter()
    quarantined_counts: Counter[str] = Counter()
    for demand in build_requirement_demands(demand_courses, assignments):
        programme = normalise_programme_year(demand.course.prog_yr)
        required[programme] += demand.required_week_count
        scheduled[programme] += demand.scheduled_week_count
    for assignment in assignments:
        if assignment.is_fixed and assignment.room is not None and assignment.timeslot is not None:
            fixed[normalise_programme_year(assignment.course.prog_yr)] += 1
    for item in quarantined:
        programme = normalise_programme_year(item.programme_year or "")
        quarantined_counts[programme] += item.affected_occurrences
    programmes = sorted(set(required) | set(scheduled) | set(quarantined_counts))
    submission_ready_programmes = submission_ready_programmes or set()
    rows: list[dict[str, object]] = []
    for programme in programmes:
        total = required[programme]
        placed = scheduled[programme]
        quarantined_occurrences = quarantined_counts[programme]
        search_failures = max(total - placed - quarantined_occurrences, 0)
        if quarantined_occurrences:
            status = "INCOMPLETE_QUARANTINED_INPUT"
        elif search_failures:
            status = "INCOMPLETE_UNSCHEDULED"
        else:
            status = "COMPLETE"
        rows.append(
            {
                "Programme/Year": programme,
                "Total Required Occurrences": total,
                "Anchored Fixed Occurrences": fixed[programme],
                "Generated Non-Fixed Occurrences": max(placed - fixed[programme], 0),
                "Unscheduled Search Failures": search_failures,
                "Quarantined Occurrences": quarantined_occurrences,
                "Missing Template 2 Mappings": 0 if programme in submission_ready_programmes else "",
                "Valid Exported Rows": placed,
                "Completion Percentage": (placed / total * 100) if total else 0,
                "Proposed Timetable Status": "HAS_VALID_ROWS" if placed else "NO_VALID_ROWS",
                "Submission-Ready Status": "PASS" if programme in submission_ready_programmes else "FAIL",
                "Reason for Incompleteness": _programme_reason(status),
                "Status": status,
                "Counts Toward Minimum 20": "Yes" if status in {"COMPLETE", "COMPLETE_WITH_WARNINGS"} and programme in submission_ready_programmes else "No",
            }
        )
    return rows


def complete_programme_set(programme_rows: list[dict[str, object]]) -> set[str]:
    """Return programme-years that satisfy the guarded complete-schedule policy."""
    return {
        str(row.get("Programme/Year"))
        for row in programme_rows
        if row.get("Status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
    }


def export_guarded_generation_report(
    *,
    output_path: Path,
    global_errors: list[dict[str, object]],
    quarantined: list[QuarantinedRequirement],
    fixed_conflict_issues: list[dict[str, object]],
    warnings: list[dict[str, object]],
    assignments: list[Assignment],
    demand_courses: list[Course],
    programme_rows: list[dict[str, object]],
    template2_summary: dict[str, object] | None = None,
) -> None:
    """Export guarded-generation exception and audit workbook."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scheduled = [item for item in assignments if item.room is not None and item.timeslot is not None]
    unscheduled = [item for item in assignments if item.room is None or item.timeslot is None]
    scheduled_hard = sum(len(item.hard_violations) for item in scheduled)
    demand = build_requirement_demands(demand_courses, assignments)
    total_occurrences = sum(row.required_week_count for row in demand)
    scheduled_occurrences = sum(row.scheduled_week_count for row in demand)
    quarantined_occurrences = sum(item.affected_occurrences for item in quarantined)
    unscheduled_search_occurrences = max(total_occurrences - scheduled_occurrences - quarantined_occurrences, 0)
    complete_programmes = sum(1 for row in programme_rows if row.get("Status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"})
    submission_ready = sum(1 for row in programme_rows if row.get("Submission-Ready Status") == "PASS")
    summary = [
        {"Metric": "Total source requirements", "Value": len(demand_courses)},
        {"Metric": "Total teaching occurrences", "Value": total_occurrences},
        {"Metric": "Schedulable occurrences", "Value": total_occurrences - quarantined_occurrences},
        {"Metric": "Quarantined occurrences", "Value": quarantined_occurrences},
        {"Metric": "Scheduled occurrences", "Value": scheduled_occurrences},
        {"Metric": "Unscheduled search failures", "Value": unscheduled_search_occurrences},
        {"Metric": "Unscheduled search-failure assignment rows", "Value": len(unscheduled)},
        {"Metric": "Scheduled hard violations", "Value": scheduled_hard},
        {"Metric": "Complete programme-years", "Value": complete_programmes},
        {"Metric": "Incomplete programme-years", "Value": max(len(programme_rows) - complete_programmes, 0)},
        {"Metric": "Submission-ready programme-years", "Value": submission_ready},
    ]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(global_errors).to_excel(writer, sheet_name="Global Errors", index=False)
        pd.DataFrame([quarantine_to_row(item) for item in quarantined]).to_excel(writer, sheet_name="Quarantined Requirements", index=False)
        pd.DataFrame(fixed_conflict_issues).to_excel(writer, sheet_name="Fixed Conflicts", index=False)
        pd.DataFrame([quarantine_to_row(item) for item in quarantined if not item.teaching_weeks]).to_excel(writer, sheet_name="Missing Information", index=False)
        pd.DataFrame(warnings).to_excel(writer, sheet_name="Location Limitations", index=False)
        pd.DataFrame(_unscheduled_rows(unscheduled)).to_excel(writer, sheet_name="Unscheduled Search Failures", index=False)
        pd.DataFrame(programme_rows).to_excel(writer, sheet_name="Programme Completeness", index=False)
        pd.DataFrame([{"Metric": key, "Value": value} for key, value in (template2_summary or {}).items()]).to_excel(
            writer,
            sheet_name="Submission Exclusions",
            index=False,
        )
        pd.DataFrame(_resolution_guidance()).to_excel(writer, sheet_name="Resolution Guidance", index=False)


def quarantine_to_row(item: QuarantinedRequirement) -> dict[str, object]:
    """Return one spreadsheet row for a quarantined requirement."""
    return {
        "Requirement ID": item.requirement_id,
        "Source Workbook": item.source_file,
        "Source Sheet": item.source_sheet,
        "Source Row": item.source_row,
        "Programme/Year": item.programme_year,
        "Module Code": item.module_code,
        "Activity": item.activity,
        "Teaching Weeks": ", ".join(str(week) for week in item.teaching_weeks),
        "Disposition Reason": item.disposition_reason,
        "Issue Codes": ", ".join(item.issue_codes),
        "Affected Occurrences": item.affected_occurrences,
        "Related Requirement IDs": ", ".join(item.related_requirement_ids),
        "Conflict Group ID": item.conflict_group_id,
        "Query ID": item.query_id,
        "Original Values": str(item.original_values),
        "Normalised Values": str(item.normalised_values),
    }


def deterministic_hash(rows: list[dict[str, object]]) -> str:
    """Return a deterministic short hash for report rows."""
    text = "\n".join(str(sorted(row.items())) for row in rows)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _global_errors(courses: list[Course], rooms_loaded: int, fixed_loader_report: FixedSessionLoaderReport) -> list[dict[str, object]]:
    """Return structural errors that block all scheduling."""
    errors: list[dict[str, object]] = []
    if not courses:
        errors.append({"severity": "critical", "disposition": ValidationDisposition.GLOBAL_BLOCK.value, "problem": "No course requirements were loaded."})
    if rooms_loaded <= 0:
        errors.append({"severity": "critical", "disposition": ValidationDisposition.GLOBAL_BLOCK.value, "problem": "No room records were loaded."})
    if fixed_loader_report.workbook_path and fixed_loader_report.source_rows == 0 and fixed_loader_report.critical_errors:
        errors.append({"severity": "critical", "disposition": ValidationDisposition.GLOBAL_BLOCK.value, "problem": "Fixed-session workbook could not be read safely."})
    return errors


def _merge_quarantine_record(
    records: dict[str, dict[str, object]],
    ref: str,
    row: dict[str, object],
    issue_code: str,
    reason: str,
    related_refs: tuple[str, ...] = (),
    conflict_group_id: str = "",
) -> None:
    """Merge one quarantine cause into a source-row record."""
    if not ref:
        return
    record = records.setdefault(
        ref,
        {
            "ref": ref,
            "row": row,
            "reasons": [],
            "issue_codes": set(),
            "related_refs": set(),
            "conflict_group_id": conflict_group_id,
        },
    )
    record["reasons"].append(reason)
    record["issue_codes"].add(issue_code)
    record["related_refs"].update(related_refs)
    if conflict_group_id:
        record["conflict_group_id"] = conflict_group_id


def _build_quarantine(record: dict[str, object], session_index: dict[str, FixedSession]) -> QuarantinedRequirement:
    """Build a structured quarantine record from merged data."""
    ref = str(record["ref"])
    row = record["row"]
    session = session_index.get(ref)
    source_file, source_sheet, source_row = _split_ref(ref)
    programme = session.programme_year if session else _row_value(row, "fixed programme/year", "programme/year")
    module = session.module_code if session else _row_value(row, "fixed module", "module code")
    weeks = session.teaching_weeks if session else _parse_weeks(_row_value(row, "fixed weeks", "teaching weeks"))
    related = tuple(sorted(str(item) for item in record["related_refs"] if str(item) and str(item) != ref))
    return QuarantinedRequirement(
        requirement_id=ref,
        source_file=source_file,
        source_sheet=source_sheet,
        source_row=source_row,
        programme_year=programme,
        module_code=module,
        activity=_row_value(row, "matched activity") or "Fixed Session",
        teaching_weeks=weeks,
        disposition_reason=" | ".join(dict.fromkeys(str(reason) for reason in record["reasons"] if reason)),
        issue_codes=tuple(sorted(str(code) for code in record["issue_codes"])),
        affected_occurrences=len(weeks),
        related_requirement_ids=related,
        original_values=dict(row),
        normalised_values={"programme/year": normalise_programme_year(str(programme or "")), "module_code": str(module or "").upper()},
        conflict_group_id=str(record.get("conflict_group_id") or ""),
    )


def _source_row_from_session_or_issue(ref: str, session_index: dict[str, FixedSession], issue: dict[str, object]) -> dict[str, object]:
    """Return row-like source metadata for a fixed assignment issue."""
    session = session_index.get(ref)
    if session is None:
        return issue
    return {
        "fixed source": ref,
        "fixed programme/year": session.programme_year,
        "fixed module": session.module_code,
        "fixed group": session.group_id,
        "fixed weeks": ", ".join(str(week) for week in session.teaching_weeks),
        "source": session.source_file,
        "sheet": session.source_sheet,
        "row": session.source_row,
    }


def _issue_source_refs(issue: dict[str, object]) -> tuple[str, ...]:
    """Return every source reference linked to a validation issue."""
    raw = " | ".join(
        str(issue.get(field) or "")
        for field in ["source refs", "related source refs"]
        if issue.get(field)
    )
    refs = [part.strip() for part in raw.split("|") if part.strip()]
    if refs:
        return tuple(dict.fromkeys(refs))
    if issue.get("source") and issue.get("sheet") and issue.get("row") not in (None, ""):
        return (source_ref(issue.get("source"), issue.get("sheet"), issue.get("row")),)
    return ()


def _issue_code(issue: dict[str, object]) -> str:
    """Return a compact issue code for quarantine rows."""
    problem = str(issue.get("problem") or "").casefold()
    if "room clash" in problem or "staff clash" in problem or "student group clash" in problem:
        return "QUARANTINED_CONFLICT"
    if "not found" in problem or "location" in problem or "room" in problem:
        return "QUARANTINED_INCOMPLETE"
    if "ambiguous" in problem:
        return "QUARANTINED_AMBIGUOUS"
    return "QUARANTINED_INCOMPLETE"


def _conflict_group_id(refs: tuple[str, ...], problem: str) -> str:
    """Return a stable conflict-group ID."""
    if len(refs) < 2:
        return ""
    raw = "|".join(sorted(refs)) + "|" + problem
    return "CFG-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10].upper()


def _split_ref(ref: str) -> tuple[str, str, int | str]:
    """Split a source reference into workbook, sheet and row."""
    parts = ref.rsplit(":", 2)
    if len(parts) != 3:
        return ref, "", ""
    row: int | str
    row = int(parts[2]) if parts[2].isdigit() else parts[2]
    return parts[0], parts[1], row


def _row_value(row: dict[str, object], *keys: str) -> str:
    """Return the first non-empty row value for candidate keys."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _parse_weeks(value: object) -> tuple[int, ...]:
    """Parse simple teaching-week text for quarantine accounting."""
    weeks: set[int] = set()
    for part in re.split(r"[,;\s]+", str(value or "")):
        if part.isdigit():
            weeks.add(int(part))
    return tuple(sorted(weeks))


def _programme_reason(status: str) -> str:
    """Return a human-readable incompleteness reason."""
    if status == "INCOMPLETE_QUARANTINED_INPUT":
        return "One or more source requirements were quarantined."
    if status == "INCOMPLETE_UNSCHEDULED":
        return "One or more schedulable requirements could not be placed."
    if status == "INCOMPLETE_OUTPUT_MAPPING":
        return "One or more rows cannot be exported to submission-ready Template 2."
    return ""


def _unscheduled_rows(assignments: list[Assignment]) -> list[dict[str, object]]:
    """Return unscheduled search-failure rows."""
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        rows.append(
            {
                "Programme/Year": assignment.course.prog_yr,
                "Module Code": assignment.course.module_code,
                "Activity": assignment.course.activity,
                "Teaching Weeks": ", ".join(str(week) for week in assignment.course.teaching_weeks),
                "Reason": " | ".join(assignment.hard_violations),
            }
        )
    return rows


def _resolution_guidance() -> list[dict[str, str]]:
    """Return plain-language guarded-generation resolution guidance."""
    return [
        {"Issue": "Quarantined incomplete row", "Guidance": "Complete or approve the missing fixed-session details before including it in automatic scheduling."},
        {"Issue": "Fixed conflict", "Guidance": "Confirm whether the rows are shared sessions, duplicates, or source records requiring correction."},
        {"Issue": "Location limitation", "Guidance": "Confirm official host keys for capacity-unverified or external venues before submission-ready export."},
    ]
