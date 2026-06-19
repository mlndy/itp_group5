"""Diagnostics for unscheduled timetable assignments."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE, ENABLE_REMARK_INTERPRETATION
from data.models import Assignment, Room, TimeSlot
from engine.constraint_checker import (
    check_blocked_time,
    check_delivery_mode_room,
    check_room_capacity,
    check_time_window,
    check_week_pattern,
    is_online_course,
)
from generator import scheduler
from generator.scheduler import (
    MAX_CANDIDATE_PATTERN_LIMIT_REASON,
    ScheduleIndex,
    _candidate_precheck,
    build_schedule_index,
    get_candidate_rooms,
    schedulable_weeks,
)

REASON_NO_COMPATIBLE_ROOM_TYPE = "no compatible room type"
REASON_NO_ROOM_LARGE_ENOUGH = "no room large enough"
REASON_NO_VALID_WEEK = "no valid teaching week after blocked weeks"
REASON_ROOM_CONFLICT = "all candidate slots blocked by room conflict"
REASON_TUTOR_CONFLICT = "all candidate slots blocked by tutor conflict"
REASON_GROUP_CONFLICT = "all candidate slots blocked by group conflict"
REASON_LUNCH_CONFLICT = "lunch constraint conflict"
REASON_DELIVERY_COMPATIBILITY = "delivery mode / room compatibility issue"
REASON_DURATION_WINDOW = "duration cannot fit valid day window"
REASON_UNKNOWN = "unknown feasibility issue"


@dataclass(slots=True)
class UnscheduledDiagnostic:
    """Structured explanation for one unscheduled assignment."""

    module_code: str
    activity: str
    prog_yr: str
    source_file: str
    reasons: list[str] = field(default_factory=list)
    compatible_room_count: int = 0
    schedulable_week_count: int = 0
    candidate_count: int = 0


@dataclass(slots=True)
class UnscheduledDiagnosticsReport:
    """Collection of unscheduled diagnostics and summary counts."""

    diagnostics: list[UnscheduledDiagnostic] = field(default_factory=list)
    scheduled_assignments: int = 0
    unscheduled_assignments: int = 0
    hard_violations_on_scheduled_assignments: int = 0
    diagnosed_assignments: int = 0
    undiagnosed_assignments: int = 0

    def add(self, diagnostic: UnscheduledDiagnostic) -> None:
        """Append one diagnostic row."""
        self.diagnostics.append(diagnostic)

    def reason_counts(self) -> Counter[str]:
        """Count primary reasons across all unscheduled assignments."""
        counter: Counter[str] = Counter()
        for diagnostic in self.diagnostics:
            for reason in diagnostic.reasons:
                counter[reason] += 1
        return counter

    def summary_rows(self) -> list[dict[str, object]]:
        """Return summary rows for spreadsheet export."""
        reasons = self.reason_counts().most_common(5)
        rows: list[dict[str, object]] = [
            {"Metric": "Scheduled assignments", "Value": self.scheduled_assignments},
            {"Metric": "Unscheduled assignments", "Value": self.unscheduled_assignments},
            {"Metric": "Hard violations on scheduled assignments", "Value": self.hard_violations_on_scheduled_assignments},
            {"Metric": "Fully diagnosed assignments", "Value": self.diagnosed_assignments},
            {"Metric": "Not fully diagnosed assignments", "Value": self.undiagnosed_assignments},
            {"Metric": "Unique unscheduled reasons", "Value": len(self.reason_counts())},
        ]
        for position, (reason, count) in enumerate(reasons, start=1):
            rows.append({"Metric": f"Top reason {position}", "Value": reason, "Count": count})
        return rows


def _scheduled_assignments(assignments: list[Assignment]) -> list[Assignment]:
    """Return assignments that already have both a room and a timeslot."""
    return [assignment for assignment in assignments if assignment.room is not None and assignment.timeslot is not None]


def _base_reason_for_room_type(assignment: Assignment, rooms: list[Room]) -> list[str]:
    """Return immediate room-availability reasons before slot search."""
    course = assignment.course
    if is_online_course(course):
        virtual_rooms = [room for room in rooms if room.room_type == "virtual"]
        if not virtual_rooms:
            return [REASON_NO_COMPATIBLE_ROOM_TYPE, REASON_DELIVERY_COMPATIBILITY]
        if not any(room.capacity >= course.class_size for room in virtual_rooms):
            return [REASON_NO_ROOM_LARGE_ENOUGH]
        return []

    physical_rooms = [room for room in rooms if room.room_type == "physical"]
    if not physical_rooms:
        return [REASON_NO_COMPATIBLE_ROOM_TYPE, REASON_DELIVERY_COMPATIBILITY]
    if not any(room.capacity >= course.class_size for room in physical_rooms):
        return [REASON_NO_ROOM_LARGE_ENOUGH]
    return []


def _categorise_violations(violations: list[str]) -> set[str]:
    """Map hard-constraint messages to higher-level diagnostic labels."""
    categories: set[str] = set()
    for violation in violations:
        text = violation.lower()
        if "room clash" in text:
            categories.add(REASON_ROOM_CONFLICT)
        elif "staff clash" in text:
            categories.add(REASON_TUTOR_CONFLICT)
        elif "student group clash" in text:
            categories.add(REASON_GROUP_CONFLICT)
        elif "no free lunch block" in text:
            categories.add(REASON_LUNCH_CONFLICT)
        elif "online class must use a virtual room" in text or "face-to-face class must not use a virtual room" in text:
            categories.add(REASON_DELIVERY_COMPATIBILITY)
        elif "room capacity too small" in text:
            categories.add(REASON_NO_ROOM_LARGE_ENOUGH)
        elif "class starts before" in text or "class ends after" in text or "blocked time used" in text:
            categories.add(REASON_DURATION_WINDOW)
        elif "blocked academic week" in text or "public holiday week" in text or "term break week" in text:
            categories.add(REASON_NO_VALID_WEEK)
    return categories


def _fast_candidate_violations(candidate: Assignment, index: ScheduleIndex) -> list[str]:
    """Return hard-constraint categories for one candidate without scanning the schedule."""
    violations: list[str] = []
    violations.extend(check_room_capacity(candidate))
    violations.extend(check_delivery_mode_room(candidate))
    violations.extend(check_week_pattern(candidate))
    violations.extend(check_time_window(candidate))
    violations.extend(check_blocked_time(candidate))
    violations.extend(_candidate_precheck(candidate, index))
    return violations


def diagnose_unscheduled_assignment(
    assignment: Assignment,
    scheduled: list[Assignment],
    rooms: list[Room],
    index: ScheduleIndex | None = None,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> UnscheduledDiagnostic:
    """Classify why an assignment could not be scheduled."""
    base_reasons = _base_reason_for_room_type(assignment, rooms)
    if base_reasons:
        return UnscheduledDiagnostic(
            module_code=assignment.course.module_code,
            activity=assignment.course.activity,
            prog_yr=assignment.course.prog_yr,
            source_file=assignment.course.source_file,
            reasons=base_reasons,
            compatible_room_count=len(
                get_candidate_rooms(
                    assignment.course,
                    rooms,
                    enable_remark_interpretation=enable_remark_interpretation,
                )
            ),
            schedulable_week_count=len(schedulable_weeks(assignment.course.teaching_weeks)),
            candidate_count=0,
        )

    weeks = schedulable_weeks(assignment.course.teaching_weeks)
    if not weeks:
        return UnscheduledDiagnostic(
            module_code=assignment.course.module_code,
            activity=assignment.course.activity,
            prog_yr=assignment.course.prog_yr,
            source_file=assignment.course.source_file,
            reasons=[REASON_NO_VALID_WEEK],
            compatible_room_count=0,
            schedulable_week_count=0,
            candidate_count=0,
        )

    compatible_rooms = get_candidate_rooms(
        assignment.course,
        rooms,
        enable_remark_interpretation=enable_remark_interpretation,
    )
    if not compatible_rooms:
        return UnscheduledDiagnostic(
            module_code=assignment.course.module_code,
            activity=assignment.course.activity,
            prog_yr=assignment.course.prog_yr,
            source_file=assignment.course.source_file,
            reasons=[REASON_UNKNOWN],
            compatible_room_count=0,
            schedulable_week_count=len(weeks),
            candidate_count=0,
        )

    schedule_index = index if index is not None else build_schedule_index(scheduled)
    category_counts: Counter[str] = Counter()
    candidate_count = 0
    for week in weeks:
        for room in compatible_rooms:
            for day in scheduler.VALID_DAYS:
                for start_time in scheduler.VALID_START_TIMES:
                    candidate_count += 1
                    candidate = Assignment(course=assignment.course, room=room, timeslot=TimeSlot(day, start_time, week))
                    violations = _fast_candidate_violations(candidate, schedule_index)
                    if not violations:
                        return UnscheduledDiagnostic(
                            module_code=assignment.course.module_code,
                            activity=assignment.course.activity,
                            prog_yr=assignment.course.prog_yr,
                            source_file=assignment.course.source_file,
                            reasons=[REASON_UNKNOWN],
                            compatible_room_count=len(compatible_rooms),
                            schedulable_week_count=len(weeks),
                            candidate_count=candidate_count,
                        )
                    category_counts.update(_categorise_violations(violations))

    if not category_counts:
        reasons = [REASON_UNKNOWN]
    else:
        top_count = max(category_counts.values())
        reasons = [reason for reason, count in category_counts.items() if count == top_count]

    return UnscheduledDiagnostic(
        module_code=assignment.course.module_code,
        activity=assignment.course.activity,
        prog_yr=assignment.course.prog_yr,
        source_file=assignment.course.source_file,
        reasons=sorted(dict.fromkeys(reasons)),
        compatible_room_count=len(compatible_rooms),
        schedulable_week_count=len(weeks),
        candidate_count=candidate_count,
    )


def _diagnostic_from_original_reasons(
    assignment: Assignment,
    rooms: list[Room],
    reasons: list[str],
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> UnscheduledDiagnostic:
    """Return a lightweight diagnostic that preserves scheduler reasons."""
    return UnscheduledDiagnostic(
        module_code=assignment.course.module_code,
        activity=assignment.course.activity,
        prog_yr=assignment.course.prog_yr,
        source_file=assignment.course.source_file,
        reasons=reasons,
        compatible_room_count=len(
            get_candidate_rooms(
                assignment.course,
                rooms,
                enable_remark_interpretation=enable_remark_interpretation,
            )
        ),
        schedulable_week_count=len(schedulable_weeks(assignment.course.teaching_weeks)),
        candidate_count=0,
    )


def diagnose_unscheduled_assignments(
    assignments: list[Assignment],
    rooms: list[Room],
    max_diagnostic_assignments: int | None = None,
    enable_remark_interpretation: bool = ENABLE_REMARK_INTERPRETATION,
) -> UnscheduledDiagnosticsReport:
    """Generate bounded diagnostics for unscheduled assignments in a schedule."""
    scheduled = _scheduled_assignments(assignments)
    unscheduled = [assignment for assignment in assignments if assignment.room is None or assignment.timeslot is None]
    report = UnscheduledDiagnosticsReport(
        scheduled_assignments=len(scheduled),
        unscheduled_assignments=len(unscheduled),
        hard_violations_on_scheduled_assignments=sum(len(assignment.hard_violations) for assignment in scheduled),
    )
    schedule_index = build_schedule_index(scheduled)
    diagnosed = 0
    for assignment in unscheduled:
        has_candidate_limit = MAX_CANDIDATE_PATTERN_LIMIT_REASON in assignment.hard_violations
        if has_candidate_limit:
            report.add(
                _diagnostic_from_original_reasons(
                    assignment,
                    rooms,
                    [MAX_CANDIDATE_PATTERN_LIMIT_REASON],
                    enable_remark_interpretation=enable_remark_interpretation,
                )
            )
            report.undiagnosed_assignments += 1
            continue
        if max_diagnostic_assignments is not None and diagnosed >= max_diagnostic_assignments:
            reasons = assignment.hard_violations or ["not diagnosed due to diagnostic assignment limit"]
            report.add(
                _diagnostic_from_original_reasons(
                    assignment,
                    rooms,
                    reasons,
                    enable_remark_interpretation=enable_remark_interpretation,
                )
            )
            report.undiagnosed_assignments += 1
            continue
        report.add(
            diagnose_unscheduled_assignment(
                assignment,
                scheduled,
                rooms,
                schedule_index,
                enable_remark_interpretation=enable_remark_interpretation,
            )
        )
        diagnosed += 1
        report.diagnosed_assignments += 1
    return report


def export_unscheduled_diagnostics(report: UnscheduledDiagnosticsReport, output_path: Path = DEFAULT_UNSCHEDULED_DIAGNOSTICS_FILE) -> None:
    """Export unscheduled diagnostics to an Excel workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df = pd.DataFrame(report.summary_rows())
    assignments_df = pd.DataFrame(
        [
            {
                "Module Code": diagnostic.module_code,
                "Activity": diagnostic.activity,
                "Programme/Year": diagnostic.prog_yr,
                "Source File": diagnostic.source_file,
                "Reasons": ", ".join(diagnostic.reasons),
                "Compatible Rooms": diagnostic.compatible_room_count,
                "Schedulable Weeks": diagnostic.schedulable_week_count,
                "Candidate Count": diagnostic.candidate_count,
            }
            for diagnostic in report.diagnostics
        ]
    )
    reason_df = pd.DataFrame(
        [{"Reason": reason, "Count": count} for reason, count in report.reason_counts().most_common()]
    )
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        assignments_df.to_excel(writer, sheet_name="Unscheduled Assignments", index=False)
        reason_df.to_excel(writer, sheet_name="Reason Counts", index=False)
