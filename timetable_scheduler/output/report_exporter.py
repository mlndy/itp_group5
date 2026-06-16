"""Export preflight and post-run stakeholder reports."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

import pandas as pd

from data.models import Assignment
from engine.constraint_checker import annotate_schedule_violations

PREFLIGHT_COLUMNS = ["severity", "entity_type", "entity_id", "issue", "recommendation"]
VIOLATION_COLUMNS = ["Module", "Activity", "Programme/Year", "Week", "Day", "Start", "Room", "Violation"]


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
    """Return an annotated copy of assignments for reporting."""
    copied = deepcopy(assignments)
    annotate_schedule_violations(copied)
    return copied


def build_run_summary(assignments: list[Assignment]) -> dict[str, object]:
    """Build headline metrics for a completed run."""
    snapshot = _snapshot(assignments)
    total = len(snapshot)
    scheduled = [item for item in snapshot if item.room is not None and item.timeslot is not None]
    unscheduled = total - len(scheduled)
    scheduled_hard = sum(len(item.hard_violations) for item in scheduled)
    all_hard = sum(len(item.hard_violations) for item in snapshot)
    all_soft = sum(len(item.soft_violations) for item in snapshot)
    return {
        "assignments": total,
        "scheduled_assignments": len(scheduled),
        "unscheduled_assignments": unscheduled,
        "hard_violations_on_scheduled_assignments": scheduled_hard,
        "hard_violations_all_assignments": all_hard,
        "soft_violations": all_soft,
        "feasibility_rate": len(scheduled) / total if total else 0,
    }


def _summary_df(assignments: list[Assignment]) -> pd.DataFrame:
    """Return summary metrics as rows."""
    summary = build_run_summary(assignments)
    labels = {
        "assignments": "Assignments",
        "scheduled_assignments": "Scheduled assignments",
        "unscheduled_assignments": "Unscheduled assignments",
        "hard_violations_on_scheduled_assignments": "Hard violations on scheduled assignments",
        "hard_violations_all_assignments": "Hard violations on all assignments",
        "soft_violations": "Soft violations",
        "feasibility_rate": "Feasibility rate",
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


def export_run_summary(assignments: list[Assignment], output_path: Path) -> None:
    """Export a stakeholder-friendly run summary workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot(assignments)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _summary_df(snapshot).to_excel(writer, sheet_name="Summary", index=False)
        _violations_df(snapshot, "hard").to_excel(writer, sheet_name="Hard Violations", index=False)
        _violations_df(snapshot, "soft").to_excel(writer, sheet_name="Soft Violations", index=False)
        _unscheduled_reasons_df(snapshot).to_excel(writer, sheet_name="Unscheduled Reasons", index=False)
        _room_utilisation_df(snapshot).to_excel(writer, sheet_name="Room Utilisation", index=False)
