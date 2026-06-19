"""Compare baseline and remarks-enabled schedules for coverage attribution."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import pandas as pd

from data.models import Assignment, Course
from engine.demand_metrics import DemandMetrics, build_demand_metrics
from engine.remarks_interpreter import (
    RemarkInterpretation,
    course_remark_requirements,
    hard_enforceable_interpretations,
)
from generator.scheduler import schedulable_weeks

OccurrenceKey: TypeAlias = tuple[str, str, str, int, tuple[str, ...], str, object]

ATTRIBUTION_CATEGORIES = [
    "multiple-room requirement",
    "hybrid-capable room requirement",
    "fixed day",
    "fixed time",
    "fixed venue",
    "required room type",
    "delivery-mode requirement",
    "sequencing",
    "other",
    "suspected false positive",
]

NEWLY_UNSCHEDULED_COLUMNS = [
    "Programme/Year",
    "Module",
    "Activity",
    "Teaching Week",
    "Source Workbook",
    "Source Row",
    "Raw Remark",
    "Detected Rule",
    "Enforcement",
    "Confidence",
    "Baseline Room",
    "Baseline Day/Time",
    "Enhanced Failure Reason",
    "Responsible Remark Rule",
    "Explicit Interpretation",
    "Manual Review Required",
    "Recommended Action",
    "Attribution Category",
]


@dataclass(slots=True)
class RemarksComparison:
    """Baseline versus remarks-enabled schedule comparison."""

    baseline_metrics: DemandMetrics
    enhanced_metrics: DemandMetrics
    newly_unscheduled_rows: list[dict[str, object]]
    rule_attribution: dict[str, int]
    scheduled_hard_violations: int
    remark_related_hard_violations: int

    @property
    def attribution_total(self) -> int:
        """Return total attributed newly unscheduled occurrences."""
        return sum(self.rule_attribution.values())

    @property
    def attribution_reconciles(self) -> bool:
        """Return True when attribution exactly matches newly unscheduled rows."""
        return self.attribution_total == len(self.newly_unscheduled_rows)


def _course_identity(course: Course) -> tuple[str, str, str, tuple[str, ...], str, object]:
    """Return the course portion of an occurrence identity."""
    return (
        course.module_code.strip().upper(),
        course.activity.strip().lower(),
        course.prog_yr.strip(),
        tuple(course.group_ids),
        course.source_file.strip(),
        course.source_row,
    )


def _occurrence_key(course: Course, week: int) -> OccurrenceKey:
    """Return a stable week-level teaching occurrence identity."""
    module, activity, programme, groups, source_file, source_row = _course_identity(course)
    return (module, activity, programme, int(week), groups, source_file, source_row)


def _scheduled_occurrences(assignments: list[Assignment]) -> dict[OccurrenceKey, Assignment]:
    """Return scheduled week occurrences keyed by stable identity."""
    rows: dict[OccurrenceKey, Assignment] = {}
    for assignment in assignments:
        if assignment.room is None or assignment.timeslot is None:
            continue
        rows.setdefault(_occurrence_key(assignment.course, assignment.timeslot.week), assignment)
    return rows


def _weeks_from_reasons(assignment: Assignment) -> list[int]:
    """Extract failed weeks from unscheduled reason text."""
    weeks: list[int] = []
    for reason in assignment.hard_violations:
        for match in re.finditer(r"week\s+(\d+)", reason, flags=re.IGNORECASE):
            week = int(match.group(1))
            if week not in weeks:
                weeks.append(week)
    return weeks


def _unscheduled_occurrences(assignments: list[Assignment]) -> dict[OccurrenceKey, Assignment]:
    """Return unscheduled placeholders expanded into week occurrences."""
    rows: dict[OccurrenceKey, Assignment] = {}
    for assignment in assignments:
        if assignment.room is not None and assignment.timeslot is not None:
            continue
        weeks = _weeks_from_reasons(assignment) or schedulable_weeks(assignment.course.teaching_weeks)
        for week in weeks:
            rows.setdefault(_occurrence_key(assignment.course, week), assignment)
    return rows


def _assignment_room_text(assignment: Assignment) -> str:
    """Return baseline room text without importing report helpers."""
    rooms = assignment.all_rooms
    return ", ".join(room.room_id for room in rooms)


def _failure_reason(assignment: Assignment | None) -> str:
    """Return enhanced failure reason text."""
    if assignment is None:
        return "No enhanced unscheduled placeholder found for this occurrence."
    return " | ".join(assignment.hard_violations) or "Unscheduled without recorded reason"


def _primary_interpretation(course: Course, assignment: Assignment | None) -> RemarkInterpretation | None:
    """Return the interpretation most likely responsible for an enhanced failure."""
    requirements = course_remark_requirements(course)
    hard_items = hard_enforceable_interpretations(requirements)
    if assignment is not None and (assignment.remark_unscheduled_reason or any("explicit" in reason.casefold() for reason in assignment.hard_violations)):
        return hard_items[0] if hard_items else None
    return hard_items[0] if hard_items else (requirements.interpretations[0] if requirements.interpretations else None)


def _attribution_category(interpretation: RemarkInterpretation | None, assignment: Assignment | None) -> str:
    """Map one responsible interpretation to an attribution bucket."""
    has_explicit_failure = assignment is not None and (
        bool(assignment.remark_unscheduled_reason)
        or any("explicit" in reason.casefold() for reason in assignment.hard_violations)
    )
    if interpretation is None or not has_explicit_failure:
        return "suspected false positive"
    if interpretation.rule_name in {"multiple_room_requirement", "concurrent_parallel_groups"}:
        return "multiple-room requirement"
    if interpretation.rule_name in {"hybrid_delivery", "recording_capable_room"}:
        return "hybrid-capable room requirement"
    if interpretation.rule_name == "fixed_day_time":
        if interpretation.parameters.get("fixed_start_times"):
            return "fixed time"
        if interpretation.parameters.get("fixed_days"):
            return "fixed day"
        return "other"
    if interpretation.rule_name == "room_type":
        return "required room type"
    if interpretation.rule_name == "flexible_delivery_mode":
        return "delivery-mode requirement"
    if interpretation.rule_name == "activity_sequence":
        return "sequencing"
    return "other"


def _recommended_action(category: str) -> str:
    """Return stakeholder action for one attribution category."""
    if category == "multiple-room requirement":
        return "Confirm the simultaneous multi-room request and review room supply."
    if category == "hybrid-capable room requirement":
        return "Confirm whether recording capability is an acceptable hybrid proxy."
    if category in {"fixed day", "fixed time", "fixed venue"}:
        return "Confirm whether the fixed placement is mandatory or flexible."
    if category == "required room type":
        return "Review specialist-room availability for the requested activity."
    if category == "delivery-mode requirement":
        return "Confirm the allowed delivery mode with programme staff."
    if category == "sequencing":
        return "Review sequencing manually because it is not fully represented."
    if category == "suspected false positive":
        return "Investigate the interpretation; ambiguous, unsupported, or preference wording should not block scheduling."
    return "Review the remark and scheduler evidence manually."


def _scheduled_hard_violations(assignments: list[Assignment]) -> int:
    """Count hard violations on scheduled rows only."""
    return sum(
        len(assignment.hard_violations)
        for assignment in assignments
        if assignment.room is not None and assignment.timeslot is not None
    )


def _newly_unscheduled_rows(
    baseline_scheduled: dict[OccurrenceKey, Assignment],
    enhanced_scheduled: dict[OccurrenceKey, Assignment],
    enhanced_unscheduled: dict[OccurrenceKey, Assignment],
) -> list[dict[str, object]]:
    """Return rows scheduled in baseline but not scheduled with remarks enabled."""
    rows: list[dict[str, object]] = []
    for key in sorted(set(baseline_scheduled) - set(enhanced_scheduled)):
        baseline = baseline_scheduled[key]
        enhanced = enhanced_unscheduled.get(key)
        course = enhanced.course if enhanced is not None else baseline.course
        requirements = course_remark_requirements(course)
        interpretation = _primary_interpretation(course, enhanced)
        category = _attribution_category(interpretation, enhanced)
        manual_review = requirements.needs_manual_review or category == "suspected false positive"
        rows.append(
            {
                "Programme/Year": course.prog_yr,
                "Module": course.module_code,
                "Activity": course.activity,
                "Teaching Week": key[3],
                "Source Workbook": course.source_file,
                "Source Row": course.source_row,
                "Raw Remark": course.remarks,
                "Detected Rule": interpretation.rule_name if interpretation else "",
                "Enforcement": interpretation.enforcement.value if interpretation else "",
                "Confidence": interpretation.confidence.value if interpretation else "",
                "Baseline Room": _assignment_room_text(baseline),
                "Baseline Day/Time": (
                    f"{baseline.timeslot.day} {baseline.timeslot.start_time}" if baseline.timeslot else ""
                ),
                "Enhanced Failure Reason": _failure_reason(enhanced),
                "Responsible Remark Rule": interpretation.rule_name if category != "suspected false positive" and interpretation else category,
                "Explicit Interpretation": "Yes" if interpretation and interpretation.parameters.get("explicit") else "No",
                "Manual Review Required": "Yes" if manual_review else "No",
                "Recommended Action": _recommended_action(category),
                "Attribution Category": category,
            }
        )
    return rows


def compare_remark_runs(
    courses: list[Course],
    baseline_assignments: list[Assignment],
    enhanced_assignments: list[Assignment],
    input_course_records: int | None = None,
) -> RemarksComparison:
    """Compare baseline and remarks-enabled schedules using one demand pool."""
    baseline_metrics = build_demand_metrics(courses, baseline_assignments, input_course_records=input_course_records)
    enhanced_metrics = build_demand_metrics(courses, enhanced_assignments, input_course_records=input_course_records)
    baseline_scheduled = _scheduled_occurrences(baseline_assignments)
    enhanced_scheduled = _scheduled_occurrences(enhanced_assignments)
    enhanced_unscheduled = _unscheduled_occurrences(enhanced_assignments)
    rows = _newly_unscheduled_rows(baseline_scheduled, enhanced_scheduled, enhanced_unscheduled)
    counts = Counter(str(row["Attribution Category"]) for row in rows)
    attribution = {category: int(counts.get(category, 0)) for category in ATTRIBUTION_CATEGORIES}
    return RemarksComparison(
        baseline_metrics=baseline_metrics,
        enhanced_metrics=enhanced_metrics,
        newly_unscheduled_rows=rows,
        rule_attribution=attribution,
        scheduled_hard_violations=_scheduled_hard_violations(enhanced_assignments),
        remark_related_hard_violations=sum(1 for row in rows if row["Attribution Category"] != "suspected false positive"),
    )


def _summary_df(comparison: RemarksComparison) -> pd.DataFrame:
    """Return summary metrics for the comparison workbook."""
    baseline = comparison.baseline_metrics
    enhanced = comparison.enhanced_metrics
    coverage_difference = enhanced.coverage_rate_percent - baseline.coverage_rate_percent
    values = {
        "Baseline required": baseline.required_teaching_occurrences,
        "Baseline scheduled": baseline.scheduled_teaching_occurrences,
        "Baseline unscheduled": baseline.unscheduled_teaching_occurrences,
        "Enhanced required": enhanced.required_teaching_occurrences,
        "Enhanced scheduled": enhanced.scheduled_teaching_occurrences,
        "Enhanced unscheduled": enhanced.unscheduled_teaching_occurrences,
        "Coverage difference": coverage_difference,
        "Additional unscheduled occurrences": len(comparison.newly_unscheduled_rows),
        "Scheduled hard violations": comparison.scheduled_hard_violations,
        "Remark-related hard violations": comparison.remark_related_hard_violations,
        "Attribution total": comparison.attribution_total,
        "Attribution reconciliation status": "PASS" if comparison.attribution_reconciles else "FAIL",
    }
    return pd.DataFrame([{"Metric": key, "Value": value} for key, value in values.items()])


def _rule_attribution_df(comparison: RemarksComparison) -> pd.DataFrame:
    """Return attribution counts by required rule bucket."""
    return pd.DataFrame(
        [{"Rule Attribution": category, "Count": comparison.rule_attribution.get(category, 0)} for category in ATTRIBUTION_CATEGORIES],
        columns=["Rule Attribution", "Count"],
    )


def export_remarks_coverage_comparison(
    courses: list[Course],
    baseline_assignments: list[Assignment],
    enhanced_assignments: list[Assignment],
    output_path: Path,
    input_course_records: int | None = None,
) -> RemarksComparison:
    """Export baseline versus remarks-enabled coverage attribution."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison = compare_remark_runs(
        courses,
        baseline_assignments,
        enhanced_assignments,
        input_course_records=input_course_records,
    )
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _summary_df(comparison).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(comparison.newly_unscheduled_rows, columns=NEWLY_UNSCHEDULED_COLUMNS).to_excel(
            writer,
            sheet_name="Newly Unscheduled",
            index=False,
        )
        _rule_attribution_df(comparison).to_excel(writer, sheet_name="Rule Attribution", index=False)
    return comparison
