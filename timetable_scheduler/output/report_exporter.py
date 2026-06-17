"""Export preflight and post-run stakeholder reports."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pandas as pd

from data.models import Assignment, Course, Room
from engine.constraint_checker import annotate_schedule_violations
from engine.demand_metrics import DemandMetrics, build_demand_metrics, requirement_demand_lookup, requirement_key
from engine.resource_audit import ResourceAudit, audit_resources

PREFLIGHT_COLUMNS = ["severity", "entity_type", "entity_id", "issue", "recommendation"]
VIOLATION_COLUMNS = ["Module", "Activity", "Programme/Year", "Week", "Day", "Start", "Room", "Violation"]
UNSCHEDULED_ANALYSIS_COLUMNS = [
    "Original Reason",
    "Reason Category",
    "Programme/Year",
    "Module Code",
    "Activity",
    "Class Size",
    "Class Size Band",
    "Delivery Mode",
    "Duration",
    "Teaching Week",
    "Common Module",
    "Candidate Limit",
    "Source File",
    "Required Week Count",
    "Scheduled Week Count",
    "Unscheduled Week Count",
]
UNSCHEDULED_BREAKDOWN_COLUMNS = ["Breakdown", "Value", "Count"]
PROGRAMME_COLUMNS = [
    "Programme/Year",
    "Source File",
    "DSC Indicator",
    "Assignments",
    "Scheduled Assignments",
    "Unscheduled Assignments",
    "Hard Violations on Scheduled Assignments",
]
VALIDATION_COLUMNS = ["Check", "Value", "Status", "Notes"]
METADATA_COLUMNS = ["Setting", "Value"]


def _metric_rows(values: dict[str, object]) -> pd.DataFrame:
    """Return metric/value rows in insertion order."""
    return pd.DataFrame([{"Metric": key, "Value": value} for key, value in values.items()])


def export_preflight_report(issues: list[dict[str, str]], output_path: Path) -> None:
    """Export preflight issues to an Excel workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = issues or [
        {
            "severity": "info",
            "entity_type": "run",
            "entity_id": "preflight",
            "issue": "No preflight issues found",
            "recommendation": "Proceed with scheduling.",
        }
    ]
    pd.DataFrame(rows, columns=PREFLIGHT_COLUMNS).to_excel(output_path, sheet_name="Preflight Issues", index=False)


def _snapshot(assignments: list[Assignment]) -> list[Assignment]:
    """Return an annotated copy while preserving original unscheduled reasons."""
    original_unscheduled_reasons = {
        id(assignment): list(assignment.hard_violations)
        for assignment in assignments
        if assignment.room is None or assignment.timeslot is None
    }
    copied = deepcopy(assignments)
    annotate_schedule_violations(copied)
    for original, copied_assignment in zip(assignments, copied, strict=False):
        reasons = original_unscheduled_reasons.get(id(original))
        if reasons:
            copied_assignment.hard_violations = reasons
    return copied


def _demand_summary_rows(demand_metrics: DemandMetrics | None) -> dict[str, object]:
    """Return demand metrics for Summary when available."""
    if demand_metrics is None:
        return {}
    return {
        "input_course_records": demand_metrics.input_course_records,
        "consolidated_course_requirements": demand_metrics.consolidated_course_requirements,
        "required_teaching_occurrences": demand_metrics.required_teaching_occurrences,
        "scheduled_teaching_occurrences": demand_metrics.scheduled_teaching_occurrences,
        "unscheduled_teaching_occurrences": demand_metrics.unscheduled_teaching_occurrences,
        "coverage_rate_percent": demand_metrics.coverage_rate_percent,
        "courses_fully_scheduled": demand_metrics.courses_fully_scheduled,
        "courses_partially_scheduled": demand_metrics.courses_partially_scheduled,
        "courses_fully_unscheduled": demand_metrics.courses_fully_unscheduled,
    }


def build_run_summary(assignments: list[Assignment], demand_metrics: DemandMetrics | None = None) -> dict[str, object]:
    """Build headline metrics for a completed run."""
    snapshot = _snapshot(assignments)
    total = len(snapshot)
    scheduled = [item for item in snapshot if item.room is not None and item.timeslot is not None]
    unscheduled_items = [item for item in snapshot if item.room is None or item.timeslot is None]
    unscheduled = total - len(scheduled)
    scheduled_hard = sum(len(item.hard_violations) for item in scheduled)
    unscheduled_hard = sum(len(item.hard_violations) for item in unscheduled_items)
    all_hard = sum(len(item.hard_violations) for item in snapshot)
    all_soft = sum(len(item.soft_violations) for item in snapshot)
    summary = {
        "assignments": total,
        "scheduled_assignments": len(scheduled),
        "unscheduled_assignments": unscheduled,
        "hard_violations_on_scheduled_assignments": scheduled_hard,
        "hard_violations_from_unscheduled_feasibility_failures": unscheduled_hard,
        "hard_violations_all_assignments": all_hard,
        "soft_violations": all_soft,
        "feasibility_rate": len(scheduled) / total if total else 0,
    }
    summary.update(_demand_summary_rows(demand_metrics))
    return summary


def _summary_df(assignments: list[Assignment], demand_metrics: DemandMetrics | None = None) -> pd.DataFrame:
    """Return summary metrics as rows."""
    summary = build_run_summary(assignments, demand_metrics=demand_metrics)
    labels = {
        "assignments": "Assignments",
        "scheduled_assignments": "Scheduled assignments",
        "unscheduled_assignments": "Unscheduled assignments",
        "hard_violations_on_scheduled_assignments": "Hard violations on scheduled assignments",
        "hard_violations_from_unscheduled_feasibility_failures": "Hard violations from unscheduled feasibility failures",
        "hard_violations_all_assignments": "Hard violations on all assignments",
        "soft_violations": "Soft violations",
        "feasibility_rate": "Feasibility rate",
        "input_course_records": "Input course records",
        "consolidated_course_requirements": "Consolidated course requirements",
        "required_teaching_occurrences": "Required teaching occurrences",
        "scheduled_teaching_occurrences": "Scheduled teaching occurrences",
        "unscheduled_teaching_occurrences": "Unscheduled teaching occurrences",
        "coverage_rate_percent": "Coverage rate percent",
        "courses_fully_scheduled": "Fully scheduled course requirements",
        "courses_partially_scheduled": "Partially scheduled course requirements",
        "courses_fully_unscheduled": "Fully unscheduled course requirements",
    }
    return pd.DataFrame([{"Metric": labels[key], "Value": value} for key, value in summary.items()])


def _violations_df(assignments: list[Assignment], violation_type: str) -> pd.DataFrame:
    """Return hard or soft violations as spreadsheet rows."""
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        violations = assignment.hard_violations if violation_type == "hard" else assignment.soft_violations
        for violation in violations:
            rows.append(
                {
                    "Module": assignment.course.module_code,
                    "Activity": assignment.course.activity,
                    "Programme/Year": assignment.course.prog_yr,
                    "Week": assignment.timeslot.week if assignment.timeslot else None,
                    "Day": assignment.timeslot.day if assignment.timeslot else None,
                    "Start": assignment.timeslot.start_time if assignment.timeslot else None,
                    "Room": assignment.room.room_id if assignment.room else None,
                    "Violation": violation,
                }
            )
    return pd.DataFrame(rows, columns=VIOLATION_COLUMNS)


def _unscheduled_reasons_df(assignments: list[Assignment]) -> pd.DataFrame:
    """Return counts of reasons unscheduled assignments remain unresolved."""
    reasons: Counter[str] = Counter()
    for assignment in assignments:
        if assignment.room is not None and assignment.timeslot is not None:
            continue
        if assignment.hard_violations:
            reasons.update(assignment.hard_violations)
        else:
            reasons["Unscheduled without recorded reason"] += 1
    return pd.DataFrame([{"Reason": reason, "Count": count} for reason, count in reasons.most_common()], columns=["Reason", "Count"])


def categorise_unscheduled_reason(assignment: Assignment, reason: str) -> str:
    """Map one unscheduled reason to a stakeholder-facing category."""
    text = reason.lower()
    if "max candidate pattern limit" in text:
        return "Candidate pattern limit"
    if "capacity" in text or "room large enough" in text:
        return "Room capacity"
    if "compatible room" in text or "delivery mode" in text or "virtual room" in text:
        return "No compatible room"
    if "staff clash" in text or "tutor" in text:
        return "Tutor clash"
    if "student group clash" in text or "group conflict" in text:
        return "Student-group clash"
    if "blocked" in text or "time window" in text or "no schedulable" in text or "valid teaching week" in text:
        return "Blocked or unavailable timeslot"
    if "feasible slot for week" in text or "weekly room/day/start pattern" in text:
        return "No complete multi-week placement"
    if assignment.course.is_common_module:
        return "Common-module constraint"
    return "Other / unknown"


def _class_size_band(class_size: int) -> str:
    """Return a compact class-size band for unscheduled breakdowns."""
    if class_size <= 30:
        return "1-30"
    if class_size <= 60:
        return "31-60"
    if class_size <= 100:
        return "61-100"
    if class_size <= 150:
        return "101-150"
    return "151+"


def _failed_week(reason: str) -> int | None:
    """Extract a failed teaching week from a reason when present."""
    match = re.search(r"week\s+(\d+)", reason, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _unscheduled_analysis_df(assignments: list[Assignment], demand_courses: list[Course] | None = None) -> pd.DataFrame:
    """Return detailed unscheduled bottleneck rows without replacing original reasons."""
    demand_lookup = requirement_demand_lookup(demand_courses, assignments) if demand_courses is not None else {}
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        if assignment.room is not None and assignment.timeslot is not None:
            continue
        demand = demand_lookup.get(requirement_key(assignment.course))
        reasons = assignment.hard_violations or ["Unscheduled without recorded reason"]
        for reason in reasons:
            rows.append(
                {
                    "Original Reason": reason,
                    "Reason Category": categorise_unscheduled_reason(assignment, reason),
                    "Programme/Year": assignment.course.prog_yr,
                    "Module Code": assignment.course.module_code,
                    "Activity": assignment.course.activity,
                    "Class Size": assignment.course.class_size,
                    "Class Size Band": _class_size_band(assignment.course.class_size),
                    "Delivery Mode": assignment.course.delivery_mode,
                    "Duration": assignment.course.duration_hrs,
                    "Teaching Week": _failed_week(reason),
                    "Common Module": "Yes" if assignment.course.is_common_module else "No",
                    "Candidate Limit": "Yes" if "max candidate pattern limit" in reason.lower() else "No",
                    "Source File": assignment.course.source_file,
                    "Required Week Count": demand.required_week_count if demand else None,
                    "Scheduled Week Count": demand.scheduled_week_count if demand else None,
                    "Unscheduled Week Count": demand.unscheduled_week_count if demand else None,
                }
            )
    return pd.DataFrame(rows, columns=UNSCHEDULED_ANALYSIS_COLUMNS)


def _unscheduled_breakdown_df(analysis_df: pd.DataFrame) -> pd.DataFrame:
    """Return grouped counts for unscheduled bottleneck dimensions."""
    if analysis_df.empty:
        return pd.DataFrame(columns=UNSCHEDULED_BREAKDOWN_COLUMNS)

    breakdowns = {
        "Reason Category": "Reason Category",
        "Programme/Year": "Programme/Year",
        "Activity": "Activity",
        "Delivery Mode": "Delivery Mode",
        "Class Size Band": "Class Size Band",
        "Duration": "Duration",
        "Common Module": "Common Module",
    }
    rows: list[dict[str, object]] = []
    for label, column in breakdowns.items():
        counts = analysis_df[column].fillna("Unknown").astype(str).value_counts()
        for value, count in counts.items():
            rows.append({"Breakdown": label, "Value": value, "Count": int(count)})
    return pd.DataFrame(rows, columns=UNSCHEDULED_BREAKDOWN_COLUMNS)


def _room_utilisation_df(assignments: list[Assignment]) -> pd.DataFrame:
    """Return scheduled room usage and enrolment utilisation."""
    usage: dict[str, dict[str, object]] = defaultdict(lambda: {"Scheduled Assignments": 0, "Total Enrolment": 0, "Total Capacity": 0})
    for assignment in assignments:
        if assignment.room is None or assignment.timeslot is None:
            continue
        row = usage[assignment.room.room_id]
        row["Scheduled Assignments"] = int(row["Scheduled Assignments"]) + 1
        row["Total Enrolment"] = int(row["Total Enrolment"]) + assignment.course.class_size
        row["Total Capacity"] = int(row["Total Capacity"]) + assignment.room.capacity

    rows: list[dict[str, object]] = []
    for room_id, row in sorted(usage.items()):
        total_capacity = int(row["Total Capacity"])
        utilisation = int(row["Total Enrolment"]) / total_capacity if total_capacity else 0
        rows.append({"Room": room_id, **row, "Average Utilisation": utilisation})
    return pd.DataFrame(rows, columns=["Room", "Scheduled Assignments", "Total Enrolment", "Total Capacity", "Average Utilisation"])


def _resource_audit_df(resource_audit: ResourceAudit | None) -> pd.DataFrame:
    """Return resource audit metrics for spreadsheet export."""
    if resource_audit is None:
        return _metric_rows({"Resource audit": "Not available"})
    return _metric_rows(
        {
            "Total raw room rows": resource_audit.total_raw_room_rows,
            "Total loaded rooms": resource_audit.total_loaded_rooms,
            "Loaded physical room count": resource_audit.physical_room_count,
            "Loaded virtual room count": resource_audit.virtual_room_count,
            "Virtual room IDs": ", ".join(room.room_id for room in resource_audit.virtual_rooms),
            "Duplicate room-ID count": resource_audit.duplicate_room_id_count,
            "Skipped or invalid room rows": resource_audit.skipped_or_invalid_room_rows,
            "Online course requirement count": resource_audit.online_course_requirements,
            "Required online teaching occurrences": resource_audit.required_online_teaching_occurrences,
            "Scheduled online teaching occurrences": resource_audit.scheduled_online_teaching_occurrences,
            "Unscheduled online teaching occurrences": resource_audit.unscheduled_online_teaching_occurrences,
            "Online coverage rate percent": resource_audit.online_coverage_rate_percent,
            "Virtual room exclusivity note": resource_audit.exclusivity_note,
        }
    )


def _virtual_room_detail_df(resource_audit: ResourceAudit | None) -> pd.DataFrame:
    """Return loaded virtual-room details and online demand peaks."""
    rows: list[dict[str, object]] = []
    if resource_audit is not None:
        for room in resource_audit.virtual_rooms:
            rows.append(
                {
                    "Section": "Virtual Room",
                    "Room ID": room.room_id,
                    "Capacity": room.capacity,
                    "Resource Type": room.resource_type,
                    "Recording": room.recording,
                    "Programme/Year": None,
                    "Week": None,
                    "Required Online Occurrences": None,
                }
            )
        for row in resource_audit.peak_online_demand_by_week[:25]:
            rows.append(
                {
                    "Section": "Peak Online Demand",
                    "Room ID": None,
                    "Capacity": None,
                    "Resource Type": None,
                    "Recording": None,
                    **row,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "Section",
            "Room ID",
            "Capacity",
            "Resource Type",
            "Recording",
            "Programme/Year",
            "Week",
            "Required Online Occurrences",
        ],
    )


def _is_dsc_assignment(assignment: Assignment) -> bool:
    """Return True when an assignment appears to belong to DSC input or programme data."""
    course = assignment.course
    text = " ".join([course.module_code, course.prog_yr, course.source_file]).upper()
    return "DSC" in text


def _programme_breakdown_df(assignments: list[Assignment]) -> pd.DataFrame:
    """Return scheduled and unscheduled counts by programme/source."""
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "Assignments": 0,
            "Scheduled Assignments": 0,
            "Unscheduled Assignments": 0,
            "Hard Violations on Scheduled Assignments": 0,
            "DSC Indicator": "No",
        }
    )
    for assignment in assignments:
        key = (assignment.course.prog_yr, assignment.course.source_file)
        row = grouped[key]
        row["Assignments"] = int(row["Assignments"]) + 1
        if _is_dsc_assignment(assignment):
            row["DSC Indicator"] = "Yes"
        if assignment.room is not None and assignment.timeslot is not None:
            row["Scheduled Assignments"] = int(row["Scheduled Assignments"]) + 1
            row["Hard Violations on Scheduled Assignments"] = int(row["Hard Violations on Scheduled Assignments"]) + len(assignment.hard_violations)
        else:
            row["Unscheduled Assignments"] = int(row["Unscheduled Assignments"]) + 1

    rows = [
        {"Programme/Year": programme, "Source File": source_file, **values}
        for (programme, source_file), values in sorted(grouped.items())
    ]
    return pd.DataFrame(rows, columns=PROGRAMME_COLUMNS)


def _validation_checks_df(
    assignments: list[Assignment],
    generated_at: str,
    demand_metrics: DemandMetrics | None = None,
) -> pd.DataFrame:
    """Return validation checks for Engineering final evidence."""
    summary = build_run_summary(assignments, demand_metrics=demand_metrics)
    programme_df = _programme_breakdown_df(assignments)
    reasons_df = _unscheduled_reasons_df(assignments)
    total = int(summary["assignments"])
    scheduled = int(summary["scheduled_assignments"])
    unscheduled = int(summary["unscheduled_assignments"])
    scheduled_hard = int(summary["hard_violations_on_scheduled_assignments"])
    total_check = scheduled + unscheduled
    has_dsc = bool((programme_df["DSC Indicator"] == "Yes").any()) if not programme_df.empty else False
    reasons_exist = not reasons_df.empty
    unscheduled_visible = unscheduled == 0 or reasons_exist
    rows = [
        {"Check": "Generated timestamp", "Value": generated_at, "Status": "INFO", "Notes": "Report generation time."},
        {"Check": "Total assignments", "Value": total, "Status": "INFO", "Notes": "All scheduled and unscheduled assignment rows in this run."},
        {"Check": "Scheduled assignments", "Value": scheduled, "Status": "INFO", "Notes": "Assignments with both room and timeslot."},
        {"Check": "Unscheduled assignments", "Value": unscheduled, "Status": "INFO", "Notes": "Assignments intentionally left unresolved rather than forced invalid."},
        {
            "Check": "Scheduled + unscheduled total check",
            "Value": total_check,
            "Status": "PASS" if total_check == total else "FAIL",
            "Notes": "Must equal total assignments.",
        },
        {
            "Check": "Demand occurrence consistency",
            "Value": (
                ""
                if demand_metrics is None
                else demand_metrics.scheduled_teaching_occurrences + demand_metrics.unscheduled_teaching_occurrences
            ),
            "Status": "INFO" if demand_metrics is None else ("PASS" if demand_metrics.is_consistent else "FAIL"),
            "Notes": "Required teaching occurrences must equal scheduled plus unscheduled occurrences.",
        },
        {
            "Check": "Stable demand metric status",
            "Value": "" if demand_metrics is None else demand_metrics.required_teaching_occurrences,
            "Status": "INFO" if demand_metrics is None else "PASS",
            "Notes": "Required teaching occurrences are calculated from consolidated input requirements, not room availability.",
        },
        {
            "Check": "Hard violations on scheduled assignments",
            "Value": scheduled_hard,
            "Status": "PASS" if scheduled_hard == 0 else "FAIL",
            "Notes": "Main hard-constraint safety metric.",
        },
        {
            "Check": "Hard-constraint safety status",
            "Value": "0 scheduled hard violations" if scheduled_hard == 0 else f"{scheduled_hard} scheduled hard violations",
            "Status": "PASS" if scheduled_hard == 0 else "FAIL",
            "Notes": "Scheduled timetable entries must be hard-feasible.",
        },
        {
            "Check": "DSC inclusion status",
            "Value": "DSC rows found" if has_dsc else "No DSC rows found",
            "Status": "PASS" if has_dsc else "FAIL",
            "Notes": "Programme Breakdown must contain DSC evidence for Engineering scope.",
        },
        {
            "Check": "Unscheduled visibility status",
            "Value": f"{unscheduled} unscheduled assignments",
            "Status": "PASS" if unscheduled_visible else "FAIL",
            "Notes": "Unscheduled assignments must remain visible with reasons when present.",
        },
        {
            "Check": "Result total comparability note",
            "Value": "Compare scheduled counts only when total assignment pool and run metadata match.",
            "Status": "INFO",
            "Notes": "Retry and candidate settings can change week-level unscheduled placeholder counts.",
        },
    ]
    return pd.DataFrame(rows, columns=VALIDATION_COLUMNS)


def _metadata_df(metadata: dict[str, object] | None, generated_at: str) -> pd.DataFrame:
    """Return run metadata as setting/value rows."""
    rows = [{"Setting": "generated_at", "Value": generated_at}]
    for key, value in (metadata or {}).items():
        rows.append({"Setting": key, "Value": value})
    return pd.DataFrame(rows, columns=METADATA_COLUMNS)


def export_run_summary(
    assignments: list[Assignment],
    output_path: Path,
    metadata: dict[str, object] | None = None,
    demand_courses: list[Course] | None = None,
    input_course_records: int | None = None,
    rooms: list[Room] | None = None,
    room_source_path: Path | None = None,
) -> None:
    """Export a stakeholder-friendly run summary workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot(assignments)
    generated_at = datetime.now().isoformat(timespec="seconds")
    demand_metrics = (
        build_demand_metrics(demand_courses, snapshot, input_course_records=input_course_records)
        if demand_courses is not None
        else None
    )
    unscheduled_analysis = _unscheduled_analysis_df(snapshot, demand_courses=demand_courses)
    resource_audit = (
        audit_resources(demand_courses, rooms, snapshot, room_source_path=room_source_path)
        if demand_courses is not None and rooms is not None
        else None
    )
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _summary_df(snapshot, demand_metrics=demand_metrics).to_excel(writer, sheet_name="Summary", index=False)
        _violations_df(snapshot, "hard").to_excel(writer, sheet_name="Hard Violations", index=False)
        _violations_df(snapshot, "soft").to_excel(writer, sheet_name="Soft Violations", index=False)
        _unscheduled_reasons_df(snapshot).to_excel(writer, sheet_name="Unscheduled Reasons", index=False)
        unscheduled_analysis.to_excel(writer, sheet_name="Unscheduled Analysis", index=False)
        _unscheduled_breakdown_df(unscheduled_analysis).to_excel(writer, sheet_name="Unscheduled Breakdown", index=False)
        _room_utilisation_df(snapshot).to_excel(writer, sheet_name="Room Utilisation", index=False)
        _resource_audit_df(resource_audit).to_excel(writer, sheet_name="Resource Audit", index=False)
        _virtual_room_detail_df(resource_audit).to_excel(writer, sheet_name="Virtual Room Detail", index=False)
        _programme_breakdown_df(snapshot).to_excel(writer, sheet_name="Programme Breakdown", index=False)
        _validation_checks_df(snapshot, generated_at, demand_metrics=demand_metrics).to_excel(writer, sheet_name="Validation Checks", index=False)
        _metadata_df(metadata, generated_at).to_excel(writer, sheet_name="Run Metadata", index=False)
