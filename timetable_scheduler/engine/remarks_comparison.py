"""Compare baseline and remarks-enabled schedules for coverage attribution."""

from __future__ import annotations

import hashlib
import json
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
    "indirect search displacement",
    "other direct remark effect",
]

EFFECT_COLUMNS = [
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
    "Enhanced Room",
    "Enhanced Day/Time",
    "Failure Reason",
    "Responsible Remark Rule",
    "Explicit Interpretation",
    "Attribution Category",
    "Attribution Evidence",
    "Recommended Action",
]

FINGERPRINT_COLUMNS = ["Run", "Metric", "Value"]
OVERALL_COLUMNS = ["Metric", "Baseline", "Enhanced", "Difference"]
RECONCILIATION_COLUMNS = ["Metric", "Value", "Status", "Notes"]


@dataclass(slots=True)
class RemarksComparison:
    """Baseline versus remarks-enabled schedule comparison."""

    baseline_metrics: DemandMetrics
    enhanced_metrics: DemandMetrics
    direct_remark_effect_rows: list[dict[str, object]]
    indirect_remark_effect_rows: list[dict[str, object]]
    unchanged_unscheduled_rows: list[dict[str, object]]
    enhanced_improvement_rows: list[dict[str, object]]
    rule_attribution: dict[str, int]
    scheduled_hard_violations: int
    baseline_fingerprint: dict[str, object]
    enhanced_fingerprint: dict[str, object]

    @property
    def newly_unscheduled_rows(self) -> list[dict[str, object]]:
        """Return all enhanced-only unscheduled occurrences."""
        return [*self.direct_remark_effect_rows, *self.indirect_remark_effect_rows]

    @property
    def attribution_total(self) -> int:
        """Return total attributed newly unscheduled occurrences."""
        return len(self.newly_unscheduled_rows)

    @property
    def attribution_reconciles(self) -> bool:
        """Return True when attribution matches the enhanced unscheduled count equation."""
        baseline_unscheduled = self.baseline_metrics.unscheduled_teaching_occurrences
        direct = len(self.direct_remark_effect_rows)
        indirect = len(self.indirect_remark_effect_rows)
        recoveries = len(self.enhanced_improvement_rows)
        return baseline_unscheduled + direct + indirect - recoveries == self.enhanced_metrics.unscheduled_teaching_occurrences

    @property
    def remark_related_hard_violations(self) -> int:
        """Return direct explicit remark-effect count for legacy callers."""
        return len(self.direct_remark_effect_rows)


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


def _assignment_room_text(assignment: Assignment | None) -> str:
    """Return assigned room text."""
    if assignment is None:
        return ""
    return ", ".join(room.room_id for room in assignment.all_rooms)


def _assignment_time_text(assignment: Assignment | None) -> str:
    """Return assigned day/time text."""
    if assignment is None or assignment.timeslot is None:
        return ""
    return f"{assignment.timeslot.day} {assignment.timeslot.start_time}"


def _failure_reason(assignment: Assignment | None) -> str:
    """Return unscheduled failure reason text."""
    if assignment is None:
        return "No unscheduled placeholder found for this occurrence."
    return " | ".join(assignment.hard_violations) or "Unscheduled without recorded reason"


def _primary_interpretation(course: Course, assignment: Assignment | None) -> RemarkInterpretation | None:
    """Return the interpretation most likely responsible for an enhanced difference."""
    requirements = course_remark_requirements(course)
    hard_items = hard_enforceable_interpretations(requirements)
    if assignment is not None and _has_direct_remark_failure(assignment):
        return hard_items[0] if hard_items else None
    return hard_items[0] if hard_items else (requirements.interpretations[0] if requirements.interpretations else None)


def _has_direct_remark_failure(assignment: Assignment | None) -> bool:
    """Return True when an unscheduled row records an explicit remark reason."""
    if assignment is None:
        return False
    return bool(assignment.remark_unscheduled_reason) or any(
        "explicit" in reason.casefold() for reason in assignment.hard_violations
    )


def _attribution_category(interpretation: RemarkInterpretation | None, assignment: Assignment | None) -> str:
    """Map one difference to a deterministic attribution bucket."""
    if not _has_direct_remark_failure(assignment):
        return "indirect search displacement"
    if interpretation is None:
        return "other direct remark effect"
    if interpretation.rule_name in {"multiple_room_requirement", "concurrent_parallel_groups"}:
        return "multiple-room requirement"
    if interpretation.rule_name in {"hybrid_delivery", "recording_capable_room"}:
        return "hybrid-capable room requirement"
    if interpretation.rule_name == "fixed_day_time":
        if interpretation.parameters.get("fixed_start_times"):
            return "fixed time"
        if interpretation.parameters.get("fixed_days"):
            return "fixed day"
        return "other direct remark effect"
    if interpretation.rule_name == "room_type":
        return "required room type"
    if interpretation.rule_name == "flexible_delivery_mode":
        return "delivery-mode requirement"
    if interpretation.rule_name == "activity_sequence":
        return "sequencing"
    return "other direct remark effect"


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
    if category == "indirect search displacement":
        return "Review as an indirect enhanced-run displacement, not a direct explicit request failure."
    return "Review the remark and scheduler evidence manually."


def _attribution_evidence(category: str, assignment: Assignment | None) -> str:
    """Return concise evidence explaining one attribution."""
    if category == "indirect search displacement":
        return (
            "Baseline scheduled this occurrence, but the enhanced run did not. "
            "No explicit remark failure was recorded on this occurrence, so it is not counted as a direct remark failure."
        )
    reason = _failure_reason(assignment)
    return f"Enhanced unscheduled reason records an explicit interpreted request: {reason}"


def _effect_row(
    key: OccurrenceKey,
    baseline: Assignment | None,
    enhanced: Assignment | None,
    category: str,
) -> dict[str, object]:
    """Return a comparison row for one occurrence difference."""
    course = (enhanced or baseline).course  # type: ignore[union-attr]
    interpretation = _primary_interpretation(course, enhanced)
    return {
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
        "Baseline Day/Time": _assignment_time_text(baseline),
        "Enhanced Room": _assignment_room_text(enhanced),
        "Enhanced Day/Time": _assignment_time_text(enhanced),
        "Failure Reason": _failure_reason(enhanced),
        "Responsible Remark Rule": interpretation.rule_name if category != "indirect search displacement" and interpretation else category,
        "Explicit Interpretation": "Yes" if interpretation and interpretation.parameters.get("explicit") else "No",
        "Attribution Category": category,
        "Attribution Evidence": _attribution_evidence(category, enhanced),
        "Recommended Action": _recommended_action(category),
    }


def _unchanged_row(key: OccurrenceKey, baseline: Assignment, enhanced: Assignment) -> dict[str, object]:
    """Return one occurrence that remained unscheduled in both runs."""
    row = _effect_row(key, baseline, enhanced, "unchanged unscheduled")
    row["Attribution Evidence"] = "This occurrence was unscheduled in both baseline and enhanced runs."
    row["Recommended Action"] = "Treat as unchanged residual demand, not a new remark effect."
    return row


def _improvement_row(key: OccurrenceKey, baseline: Assignment, enhanced: Assignment) -> dict[str, object]:
    """Return one baseline-unscheduled occurrence recovered in the enhanced run."""
    row = _effect_row(key, baseline, enhanced, "enhanced recovery")
    row["Failure Reason"] = _failure_reason(baseline)
    row["Attribution Evidence"] = "This occurrence was unscheduled in the baseline but scheduled in the enhanced run."
    row["Recommended Action"] = "No exception action required unless programme review is requested."
    return row


def _scheduled_hard_violations(assignments: list[Assignment]) -> int:
    """Count hard violations on scheduled rows only."""
    return sum(
        len(assignment.hard_violations)
        for assignment in assignments
        if assignment.room is not None and assignment.timeslot is not None
    )


def _course_fingerprint(courses: list[Course], input_course_records: int | None) -> str:
    """Return a deterministic fingerprint for the shared input demand pool."""
    payload = [
        {
            "module": course.module_code,
            "activity": course.activity,
            "programme": course.prog_yr,
            "class_size": course.class_size,
            "delivery_mode": course.delivery_mode,
            "weeks": list(course.teaching_weeks),
            "duration": course.duration_hrs,
            "source_file": course.source_file,
            "source_sheet": course.source_sheet,
            "source_row": course.source_row,
            "groups": list(course.group_ids),
            "staff": list(course.staff_ids),
            "remarks": course.remarks,
        }
        for course in courses
    ]
    wrapper = {"input_course_records": input_course_records, "courses": payload}
    encoded = json.dumps(wrapper, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scheduler_fingerprint(metadata: dict[str, object] | None, remarks_enabled: bool) -> str:
    """Return a deterministic fingerprint for comparable scheduler settings."""
    payload = dict(metadata or {})
    payload["remark_interpretation_enabled"] = remarks_enabled
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_fingerprint(
    label: str,
    courses: list[Course],
    metrics: DemandMetrics,
    input_course_records: int | None,
    scheduler_metadata: dict[str, object] | None,
    remarks_enabled: bool,
) -> dict[str, object]:
    """Return run fingerprint rows for comparison reproducibility."""
    return {
        "run": label,
        "remark_interpretation_enabled": remarks_enabled,
        "input_course_records": input_course_records,
        "consolidated_requirement_count": metrics.consolidated_course_requirements,
        "required_teaching_occurrences": metrics.required_teaching_occurrences,
        "input_demand_fingerprint": _course_fingerprint(courses, input_course_records),
        "scheduler_settings_fingerprint": _scheduler_fingerprint(scheduler_metadata, remarks_enabled),
        **(scheduler_metadata or {}),
    }


def compare_remark_runs(
    courses: list[Course],
    baseline_assignments: list[Assignment],
    enhanced_assignments: list[Assignment],
    input_course_records: int | None = None,
    scheduler_metadata: dict[str, object] | None = None,
) -> RemarksComparison:
    """Compare baseline and remarks-enabled schedules using one demand pool."""
    baseline_metrics = build_demand_metrics(courses, baseline_assignments, input_course_records=input_course_records)
    enhanced_metrics = build_demand_metrics(courses, enhanced_assignments, input_course_records=input_course_records)
    baseline_scheduled = _scheduled_occurrences(baseline_assignments)
    enhanced_scheduled = _scheduled_occurrences(enhanced_assignments)
    baseline_unscheduled = _unscheduled_occurrences(baseline_assignments)
    enhanced_unscheduled = _unscheduled_occurrences(enhanced_assignments)

    direct_rows: list[dict[str, object]] = []
    indirect_rows: list[dict[str, object]] = []
    for key in sorted(set(baseline_scheduled) - set(enhanced_scheduled)):
        baseline = baseline_scheduled[key]
        enhanced = enhanced_unscheduled.get(key)
        category = _attribution_category(_primary_interpretation((enhanced or baseline).course, enhanced), enhanced)
        row = _effect_row(key, baseline, enhanced, category)
        if category == "indirect search displacement":
            indirect_rows.append(row)
        else:
            direct_rows.append(row)

    unchanged_rows = [
        _unchanged_row(key, baseline_unscheduled[key], enhanced_unscheduled[key])
        for key in sorted(set(baseline_unscheduled) & set(enhanced_unscheduled))
    ]
    improvement_rows = [
        _improvement_row(key, baseline_unscheduled[key], enhanced_scheduled[key])
        for key in sorted(set(baseline_unscheduled) & set(enhanced_scheduled))
    ]

    counts = Counter(str(row["Attribution Category"]) for row in direct_rows + indirect_rows)
    attribution = {category: int(counts.get(category, 0)) for category in ATTRIBUTION_CATEGORIES}
    return RemarksComparison(
        baseline_metrics=baseline_metrics,
        enhanced_metrics=enhanced_metrics,
        direct_remark_effect_rows=direct_rows,
        indirect_remark_effect_rows=indirect_rows,
        unchanged_unscheduled_rows=unchanged_rows,
        enhanced_improvement_rows=improvement_rows,
        rule_attribution=attribution,
        scheduled_hard_violations=_scheduled_hard_violations(enhanced_assignments),
        baseline_fingerprint=_run_fingerprint(
            "Baseline",
            courses,
            baseline_metrics,
            input_course_records,
            scheduler_metadata,
            remarks_enabled=False,
        ),
        enhanced_fingerprint=_run_fingerprint(
            "Enhanced",
            courses,
            enhanced_metrics,
            input_course_records,
            scheduler_metadata,
            remarks_enabled=True,
        ),
    )


def _run_fingerprints_df(comparison: RemarksComparison) -> pd.DataFrame:
    """Return run fingerprint rows."""
    rows: list[dict[str, object]] = []
    for fingerprint in [comparison.baseline_fingerprint, comparison.enhanced_fingerprint]:
        run = str(fingerprint.get("run", ""))
        for key, value in fingerprint.items():
            if key == "run":
                continue
            rows.append({"Run": run, "Metric": key, "Value": value})
    return pd.DataFrame(rows, columns=FINGERPRINT_COLUMNS)


def _overall_metrics_df(comparison: RemarksComparison) -> pd.DataFrame:
    """Return headline baseline and enhanced metrics."""
    baseline = comparison.baseline_metrics
    enhanced = comparison.enhanced_metrics
    values = [
        ("Input course records", baseline.input_course_records, enhanced.input_course_records),
        ("Consolidated requirements", baseline.consolidated_course_requirements, enhanced.consolidated_course_requirements),
        ("Required teaching occurrences", baseline.required_teaching_occurrences, enhanced.required_teaching_occurrences),
        ("Scheduled teaching occurrences", baseline.scheduled_teaching_occurrences, enhanced.scheduled_teaching_occurrences),
        ("Unscheduled teaching occurrences", baseline.unscheduled_teaching_occurrences, enhanced.unscheduled_teaching_occurrences),
        ("Coverage rate percent", baseline.coverage_rate_percent, enhanced.coverage_rate_percent),
        ("Scheduled hard violations", 0, comparison.scheduled_hard_violations),
        ("Direct remark effects", 0, len(comparison.direct_remark_effect_rows)),
        ("Indirect remark effects", 0, len(comparison.indirect_remark_effect_rows)),
        ("Enhanced recoveries", 0, len(comparison.enhanced_improvement_rows)),
    ]
    return pd.DataFrame(
        [
            {
                "Metric": metric,
                "Baseline": baseline_value,
                "Enhanced": enhanced_value,
                "Difference": enhanced_value - baseline_value if isinstance(baseline_value, (int, float)) and isinstance(enhanced_value, (int, float)) else "",
            }
            for metric, baseline_value, enhanced_value in values
        ],
        columns=OVERALL_COLUMNS,
    )


def _attribution_reconciliation_df(comparison: RemarksComparison) -> pd.DataFrame:
    """Return mathematical reconciliation rows for enhanced unscheduled demand."""
    baseline_unscheduled = comparison.baseline_metrics.unscheduled_teaching_occurrences
    direct = len(comparison.direct_remark_effect_rows)
    indirect = len(comparison.indirect_remark_effect_rows)
    recoveries = len(comparison.enhanced_improvement_rows)
    enhanced_unscheduled = comparison.enhanced_metrics.unscheduled_teaching_occurrences
    calculated = baseline_unscheduled + direct + indirect - recoveries
    rows = [
        {"Metric": "Baseline unscheduled occurrences", "Value": baseline_unscheduled, "Status": "INFO", "Notes": "Unscheduled demand with remark interpretation disabled."},
        {"Metric": "Direct remark effects", "Value": direct, "Status": "INFO", "Notes": "Enhanced-only unscheduled occurrences with explicit remark failure reasons."},
        {"Metric": "Indirect remark effects", "Value": indirect, "Status": "INFO", "Notes": "Enhanced-only unscheduled occurrences without direct explicit failure reasons."},
        {"Metric": "Enhanced recoveries", "Value": recoveries, "Status": "INFO", "Notes": "Baseline-unscheduled occurrences scheduled by the enhanced run."},
        {"Metric": "Calculated enhanced unscheduled", "Value": calculated, "Status": "PASS" if calculated == enhanced_unscheduled else "FAIL", "Notes": "Baseline + direct + indirect - recoveries."},
        {"Metric": "Actual enhanced unscheduled", "Value": enhanced_unscheduled, "Status": "INFO", "Notes": "Reported by demand metrics."},
        {"Metric": "Attribution reconciliation", "Value": calculated == enhanced_unscheduled, "Status": "PASS" if comparison.attribution_reconciles else "FAIL", "Notes": "No unexplained or suspected categories remain."},
        {"Metric": "Scheduled hard violations", "Value": comparison.scheduled_hard_violations, "Status": "PASS" if comparison.scheduled_hard_violations == 0 else "FAIL", "Notes": "Enhanced scheduled assignments must remain hard-feasible."},
    ]
    for category in ATTRIBUTION_CATEGORIES:
        rows.append(
            {
                "Metric": f"Rule attribution - {category}",
                "Value": comparison.rule_attribution.get(category, 0),
                "Status": "INFO",
                "Notes": "Deterministic attribution bucket.",
            }
        )
    return pd.DataFrame(rows, columns=RECONCILIATION_COLUMNS)


def _rows_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Return effect rows with stable columns."""
    return pd.DataFrame(rows, columns=EFFECT_COLUMNS)


def export_remarks_coverage_comparison(
    courses: list[Course],
    baseline_assignments: list[Assignment],
    enhanced_assignments: list[Assignment],
    output_path: Path,
    input_course_records: int | None = None,
    scheduler_metadata: dict[str, object] | None = None,
) -> RemarksComparison:
    """Export baseline versus remarks-enabled coverage attribution."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison = compare_remark_runs(
        courses,
        baseline_assignments,
        enhanced_assignments,
        input_course_records=input_course_records,
        scheduler_metadata=scheduler_metadata,
    )
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _run_fingerprints_df(comparison).to_excel(writer, sheet_name="Run Fingerprints", index=False)
        _overall_metrics_df(comparison).to_excel(writer, sheet_name="Overall Metrics", index=False)
        _rows_df(comparison.direct_remark_effect_rows).to_excel(writer, sheet_name="Direct Remark Effects", index=False)
        _rows_df(comparison.indirect_remark_effect_rows).to_excel(writer, sheet_name="Indirect Remark Effects", index=False)
        _rows_df(comparison.unchanged_unscheduled_rows).to_excel(writer, sheet_name="Unchanged Unscheduled", index=False)
        _rows_df(comparison.enhanced_improvement_rows).to_excel(writer, sheet_name="Enhanced Improvements", index=False)
        _attribution_reconciliation_df(comparison).to_excel(writer, sheet_name="Attribution Reconciliation", index=False)
    return comparison
