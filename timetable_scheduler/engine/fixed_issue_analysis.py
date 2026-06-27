"""Evidence reports for fixed-session readiness triage."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from config import DEFAULT_TEMPLATE2_FILE
from data.fixed_sessions import FixedSessionLoaderReport
from data.models import Assignment, Course, FixedSession, Room
from engine.constraint_checker import assignments_overlap, check_hard_constraints, course_groups, room_is_exclusive
from engine.fixed_reconciliation import FixedReconciliationReport, normalise_programme_year
from engine.fixed_resolution import export_resolution_audit, export_resolution_template, load_resolution_workbook
from engine.location_mapping import classify_location, export_location_mapping_evidence
from engine.remarks_interpreter import assignment_rooms
from generator.fixed_scheduler import normalise_module_code, normalise_staff_name


def _source_ref(session: FixedSession) -> str:
    """Return a compact source reference for one fixed source row."""
    return f"{session.source_file}:{session.source_sheet}:{session.source_row}"


def _source_refs_from_assignment(assignment: Assignment) -> list[str]:
    """Return all fixed source references attached to one assignment."""
    return [part.strip() for part in str(assignment.fixed_source or "").split("|") if part.strip()]


def _parse_source_ref(ref: str) -> tuple[str, str, int | str]:
    """Split a source reference into workbook, sheet and row."""
    parts = ref.split(":")
    if len(parts) < 3:
        return ref, "", ""
    try:
        row: int | str = int(parts[-1])
    except ValueError:
        row = parts[-1]
    return parts[0], parts[1], row


def _session_lookup(fixed_sessions: list[FixedSession], loader_report: FixedSessionLoaderReport) -> dict[str, dict[str, object]]:
    """Return source rows keyed by fixed source reference."""
    rows = {
        _source_ref(session): {
            "source workbook": session.source_file,
            "source sheet": session.source_sheet,
            "source row": session.source_row,
            "programme/year": session.programme_year,
            "normalised programme/year": normalise_programme_year(session.programme_year),
            "module code": session.module_code,
            "normalised module code": normalise_module_code(session.module_code),
            "group": session.group_id,
            "group size": session.group_size,
            "day": session.day,
            "start time": session.start_time,
            "duration": session.duration_hours,
            "teaching weeks": ", ".join(str(week) for week in session.teaching_weeks),
            "location": "; ".join(session.locations),
            "staff": "; ".join(session.staff_names),
        }
        for session in fixed_sessions
    }
    for audit in loader_report.audit_rows:
        ref = f"{audit.get('source workbook')}:{audit.get('source sheet')}:{audit.get('source row')}"
        rows.setdefault(
            ref,
            {
                "source workbook": audit.get("source workbook", ""),
                "source sheet": audit.get("source sheet", ""),
                "source row": audit.get("source row", ""),
                "programme/year": audit.get("programme/year", ""),
                "normalised programme/year": normalise_programme_year(str(audit.get("programme/year", ""))),
                "module code": audit.get("module code", ""),
                "normalised module code": normalise_module_code(str(audit.get("module code", ""))),
                "group": audit.get("group", ""),
                "group size": audit.get("group size", ""),
                "day": audit.get("day", ""),
                "start time": audit.get("start time", ""),
                "duration": audit.get("duration", ""),
                "teaching weeks": audit.get("teaching weeks", ""),
                "location": audit.get("location", ""),
                "staff": audit.get("staff", ""),
            },
        )
    return rows


def _category(issue: dict[str, object]) -> str:
    """Classify one readiness issue into a stakeholder-readable category."""
    field = str(issue.get("field") or "").casefold()
    problem = str(issue.get("problem") or "").casefold()
    if "week" in field or "week" in problem and "missing" in problem:
        return "missing teaching weeks"
    if "partial fixed/non-fixed" in problem:
        return "fixed/non-fixed mapping failure"
    if "ambiguous fixed/non-fixed" in problem:
        return "ambiguous mapping"
    if "exact fixed room" in problem:
        return "exact-room name mismatch"
    if "external venue" in problem or "generic request" in problem:
        return "generic-room interpretation issue"
    if "room capacity" in problem:
        return "room-capacity issue"
    if "room clash" in problem:
        return "fixed room clash"
    if "staff clash" in problem:
        return "fixed tutor clash"
    if "student group clash" in problem or "lunch block" in problem:
        return "fixed programme/group clash"
    if "blocked time" in problem or "term break" in problem:
        return "blocked-period conflict"
    if "invalid" in problem or "ends after" in problem or "duration" in problem or "day" in problem:
        return "invalid day/time/duration"
    return "other"


def _issue_rows(
    loader_report: FixedSessionLoaderReport,
    reconciliation_report: FixedReconciliationReport,
    mapping_issues: list[dict[str, object]],
    conflict_issues: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build one row per critical or warning issue instance."""
    rows: list[dict[str, object]] = []
    for issue in loader_report.issues:
        ref = f"{Path(str(loader_report.workbook_path)).name}:{issue.get('sheet')}:{issue.get('row')}"
        rows.append({**issue, "source refs": ref, "category": _category(issue), "issue origin": "fixed loader"})
    for row in reconciliation_report.partial_matches:
        issue = {
            "severity": "critical",
            "problem": "Partial fixed/non-fixed reconciliation requires a reviewed split to avoid duplicate demand.",
            "source refs": row.get("fixed source", ""),
            "category": "fixed/non-fixed mapping failure",
            "issue origin": "reconciliation",
            "recommendation": row.get("manual-review reason", ""),
        }
        rows.append(issue)
    for row in reconciliation_report.ambiguous_matches:
        issue = {
            "severity": "critical",
            "problem": "Ambiguous fixed/non-fixed reconciliation could duplicate demand.",
            "source refs": row.get("fixed source", ""),
            "category": "ambiguous mapping",
            "issue origin": "reconciliation",
            "recommendation": row.get("manual-review reason", ""),
        }
        rows.append(issue)
    for row in reconciliation_report.invalid_fixed_rows:
        issue = {
            "severity": row.get("severity", "critical"),
            "problem": row.get("manual-review reason", "Invalid fixed source row."),
            "source refs": row.get("fixed source", ""),
            "category": "missing teaching weeks" if "week" in str(row.get("manual-review reason", "")).casefold() else "source row incomplete",
            "issue origin": "reconciliation",
            "recommendation": "Correct or clarify the fixed-session source row.",
        }
        rows.append(issue)
    for issue in mapping_issues:
        rows.append({**issue, "source refs": f"{issue.get('source')}:{issue.get('sheet')}:{issue.get('row')}", "category": _category(issue), "issue origin": "fixed room mapping"})
    for issue in conflict_issues:
        rows.append({**issue, "source refs": issue.get("source refs", f"{issue.get('source')}:{issue.get('sheet')}:{issue.get('row')}"), "category": _category(issue), "issue origin": "fixed conflict"})
    return rows


def _unique_affected_rows(issue_rows: list[dict[str, object]], sessions: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Aggregate issue instances to unique fixed source rows."""
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in issue_rows:
        refs = [part.strip() for part in str(row.get("source refs") or "").split("|") if part.strip()]
        for ref in refs or [""]:
            grouped[ref].append(row)
    result: list[dict[str, object]] = []
    for ref, rows in sorted(grouped.items()):
        source = sessions.get(ref, {})
        result.append(
            {
                "source ref": ref,
                **source,
                "issue instances": len(rows),
                "critical instances": sum(1 for row in rows if row.get("severity") == "critical"),
                "warning instances": sum(1 for row in rows if row.get("severity") == "warning"),
                "categories": "; ".join(sorted({str(row.get("category", "")) for row in rows if row.get("category")})),
                "problems": "; ".join(sorted({str(row.get("problem", "")) for row in rows if row.get("problem")})),
            }
        )
    return result


def _candidate_requirements(session: FixedSession, courses: list[Course]) -> str:
    """Return concise matching evidence for nearby non-fixed requirements."""
    fixed_module = normalise_module_code(session.module_code)
    fixed_programme = normalise_programme_year(session.programme_year)
    fixed_staff = {normalise_staff_name(staff) for staff in (*session.staff_ids, *session.staff_names) if staff}
    scored: list[tuple[int, str]] = []
    for course in courses:
        course_staff = {normalise_staff_name(staff) for staff in (*course.staff_ids, *course.staff_names) if staff}
        module_match = normalise_module_code(course.module_code) == fixed_module
        programme_match = normalise_programme_year(course.prog_yr) == fixed_programme
        week_overlap = bool(set(session.teaching_weeks) & set(course.teaching_weeks))
        staff_overlap = not fixed_staff or not course_staff or bool(fixed_staff & course_staff)
        duration_match = abs(float(course.duration_hrs) - float(session.duration_hours)) < 0.01
        score = sum([module_match, programme_match, week_overlap, staff_overlap, duration_match])
        if module_match or (programme_match and score >= 3):
            scored.append(
                (
                    score,
                    f"{course.source_file} row {course.source_row}: {course.prog_yr} {course.module_code} "
                    f"{course.activity}, weeks {course.teaching_weeks}, duration {course.duration_hrs}, score {score}",
                )
            )
    return "\n".join(text for _score, text in sorted(scored, reverse=True)[:5])


def _mapping_rows(
    mapping_issues: list[dict[str, object]],
    fixed_sessions: list[FixedSession],
    courses: list[Course],
    sessions: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Return detailed mapping issue rows."""
    fixed_by_ref = {_source_ref(session): session for session in fixed_sessions}
    rows: list[dict[str, object]] = []
    for issue in mapping_issues:
        ref = f"{issue.get('source')}:{issue.get('sheet')}:{issue.get('row')}"
        source = sessions.get(ref, {})
        session = fixed_by_ref.get(ref)
        rows.append(
            {
                "source ref": ref,
                **source,
                "candidate non-fixed requirements": _candidate_requirements(session, courses) if session else "",
                "match scores or evidence": "Room code/location could not be mapped to supplied venue data.",
                "why rejected": issue.get("problem", ""),
                "recommended treatment": issue.get("recommendation", ""),
            }
        )
    return rows


def _same_group(left: Course, right: Course) -> bool:
    """Return True if two courses share a programme/group identity."""
    left_groups = course_groups(left)
    right_groups = course_groups(right)
    if left_groups & right_groups:
        return True
    return any(left.startswith(f"{right}/") or right.startswith(f"{left}/") for left in left_groups for right in right_groups)


def _overlap_weeks(left: Assignment, right: Assignment) -> str:
    """Return overlapping week text for two assignments."""
    if left.timeslot is None or right.timeslot is None:
        return ""
    return str(left.timeslot.week) if left.timeslot.week == right.timeslot.week else ""


def conflict_triage_rows(assignments: list[Assignment]) -> list[dict[str, object]]:
    """Return detailed pairwise and individual fixed-conflict rows."""
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        individual = check_hard_constraints(assignment, [], enable_remark_interpretation=False)
        for problem in individual:
            if "clash" in problem.casefold():
                continue
            rows.append(_conflict_row("Placement rule", assignment, None, problem))
    for index, left in enumerate(assignments):
        for right in assignments[index + 1 :]:
            if not assignments_overlap(left, right):
                continue
            left_rooms = {room.room_id for room in assignment_rooms(left) if room_is_exclusive(room)}
            right_rooms = {room.room_id for room in assignment_rooms(right) if room_is_exclusive(room)}
            if left_rooms & right_rooms:
                rows.append(_conflict_row("Room conflict", left, right, f"Shared room(s): {', '.join(sorted(left_rooms & right_rooms))}"))
            staff = set(left.course.staff_ids) & set(right.course.staff_ids)
            if staff:
                rows.append(_conflict_row("Tutor conflict", left, right, f"Shared tutor(s): {', '.join(sorted(staff))}"))
            if _same_group(left.course, right.course):
                rows.append(_conflict_row("Programme conflict", left, right, "Overlapping programme/group identity"))
    return rows


def _conflict_row(conflict_type: str, left: Assignment, right: Assignment | None, problem: str) -> dict[str, object]:
    """Build one fixed-conflict triage row."""
    left_refs = " | ".join(_source_refs_from_assignment(left))
    right_refs = " | ".join(_source_refs_from_assignment(right)) if right else ""
    return {
        "conflict type": conflict_type,
        "assignment A source": left_refs,
        "assignment B source": right_refs,
        "day and time": f"{left.timeslot.day} {left.timeslot.start_time}" if left.timeslot else "",
        "overlapping weeks": _overlap_weeks(left, right) if right else (left.timeslot.week if left.timeslot else ""),
        "room": "; ".join(room.room_id for room in assignment_rooms(left)),
        "lecturer": "; ".join(left.course.staff_names or left.course.staff_ids),
        "programme/group": "; ".join(left.course.group_ids),
        "module": left.course.module_code,
        "appears same shared session": "Yes" if right and left.fixed_source == right.fixed_source else "No",
        "duplicate row candidate": "Yes" if " | " in left_refs and not right_refs else "No",
        "normalisation caused clash": "No",
        "problem": problem,
        "recommended resolution": _recommended_conflict_resolution(conflict_type, problem),
        "automatic resolution allowed": "No",
    }


def _recommended_conflict_resolution(conflict_type: str, problem: str) -> str:
    """Return concise supervisor-facing conflict guidance."""
    text = problem.casefold()
    if "blocked" in text or "18:00" in text or "term break" in text:
        return "Clarify whether the supplied fixed time is allowed or should be corrected in the source."
    if conflict_type == "Room conflict":
        return "Confirm whether these are one shared class or two separate classes needing different rooms/times."
    if conflict_type == "Tutor conflict":
        return "Confirm whether the lecturer is intended to teach one shared class or overlapping separate classes."
    if conflict_type == "Programme conflict":
        return "Confirm whether the affected cohort is duplicated or expected to attend both sessions."
    return "Review the fixed source row before generation."


def _shared_session_rows(assignments: list[Assignment]) -> list[dict[str, object]]:
    """Return grouped shared-session evidence rows."""
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        refs = _source_refs_from_assignment(assignment)
        if len(refs) <= 1:
            continue
        rows.append(
            {
                "classification": "Confirmed shared session",
                "source refs": " | ".join(refs),
                "module": assignment.course.module_code,
                "day": assignment.timeslot.day if assignment.timeslot else "",
                "start": assignment.timeslot.start_time if assignment.timeslot else "",
                "weeks": ", ".join(str(week) for week in assignment.course.teaching_weeks),
                "rooms": "; ".join(room.room_id for room in assignment_rooms(assignment)),
                "staff": "; ".join(assignment.course.staff_names),
                "groups": "; ".join(assignment.course.group_ids),
                "combined class size": assignment.course.class_size,
                "evidence": "Same module, programme/year, day, start, duration, weeks, resolved rooms and staff.",
            }
        )
    return rows


def _normalisation_rows(assignments: list[Assignment], fixed_sessions: list[FixedSession]) -> list[dict[str, object]]:
    """Return automatically applied normalisation evidence rows."""
    by_ref = {_source_ref(session): session for session in fixed_sessions}
    rows: list[dict[str, object]] = []
    for assignment in assignments:
        for ref in _source_refs_from_assignment(assignment):
            session = by_ref.get(ref)
            if session is None:
                continue
            rows.append(
                {
                    "source ref": ref,
                    "field": "programme/year",
                    "original value": session.programme_year,
                    "normalised value": normalise_programme_year(session.programme_year),
                    "normalisation rule": "Collapse Yr/Year labels and slash spacing.",
                    "evidence": "Used only for comparison keys; original source value is retained in audit.",
                }
            )
            for raw_staff, staff_id in zip(session.staff_names, assignment.course.staff_ids, strict=False):
                if raw_staff and normalise_staff_name(raw_staff) != raw_staff:
                    rows.append(
                        {
                            "source ref": ref,
                            "field": "staff",
                            "original value": raw_staff,
                            "normalised value": normalise_staff_name(raw_staff),
                            "normalisation rule": "Collapse whitespace, uppercase and remove trailing standalone punctuation.",
                            "evidence": "Used only for fixed-staff identity; original staff name is retained for output.",
                        }
                    )
            for location, room in zip(session.locations, assignment_rooms(assignment), strict=False):
                if location != room.room_id:
                    rows.append(
                        {
                            "source ref": ref,
                            "field": "room",
                            "original value": location,
                            "normalised value": room.room_id,
                            "normalisation rule": "Exact venue-code prefix matched official room ID.",
                            "evidence": "Official venue ID starts with the fixed-source room code.",
                        }
                    )
    return rows


def _summary(issue_rows: list[dict[str, object]], unique_rows: list[dict[str, object]], shared_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return root-cause summary metrics."""
    critical = [row for row in issue_rows if row.get("severity") == "critical"]
    by_category = Counter(str(row.get("category", "other")) for row in critical)
    rows = [
        {"Metric": "Total issue instances", "Value": len(issue_rows)},
        {"Metric": "Critical issue instances", "Value": len(critical)},
        {"Metric": "Unique affected rows", "Value": len(unique_rows)},
        {"Metric": "Confirmed shared sessions", "Value": len(shared_rows)},
    ]
    rows.extend({"Metric": f"Critical category: {category}", "Value": count} for category, count in sorted(by_category.items()))
    return rows


def _supervisor_queries(
    issue_rows: list[dict[str, object]],
    sessions: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Return concise supervisor clarification questions."""
    unique = _unique_affected_rows([row for row in issue_rows if row.get("severity") == "critical"], sessions)
    rows: list[dict[str, object]] = []
    for index, row in enumerate(unique, start=1):
        problem = str(row.get("problems", ""))
        rows.append(
            {
                "query ID": f"FIX-{index:03d}",
                "source workbook": row.get("source workbook", ""),
                "sheet": row.get("source sheet", ""),
                "row": row.get("source row", ""),
                "programme/year": row.get("programme/year", ""),
                "module": row.get("module code", ""),
                "group": row.get("group", ""),
                "day": row.get("day", ""),
                "time": row.get("start time", ""),
                "weeks": row.get("teaching weeks", ""),
                "room": row.get("location", ""),
                "staff": row.get("staff", ""),
                "exact problem": problem,
                "why the scheduler cannot safely decide": "The fixed-session readiness gate cannot move or reinterpret official fixed rows without traceable evidence.",
                "available options": _options_for_problem(problem),
                "recommended clarification question": _question_for_problem(problem),
                "impact if unresolved": "Engineering generation remains blocked until this critical issue is clarified or corrected.",
            }
        )
    return rows


def _teaching_occurrences(row: dict[str, object]) -> int:
    """Return teaching occurrence count from a source-row teaching-week string."""
    weeks = str(row.get("teaching weeks") or "")
    return len([part for part in re.split(r"[,;\s]+", weeks) if part.isdigit()])


def _query_key(row: dict[str, object]) -> tuple[str, str, str]:
    """Return the grouping key for supervisor decision summaries."""
    category = str(row.get("categories") or "other")
    problems = str(row.get("problems") or "")
    if "Exact fixed room" in problems:
        match = re.search(r"'([^']+)'", problems)
        return ("Location", f"Confirm venue {match.group(1) if match else ''}", "Location Queries")
    if "ENG External Venue" in problems:
        return ("Location", "Confirm external venue treatment", "Location Queries")
    if "weeks" in problems.casefold():
        return ("Missing weeks", "Which teaching weeks apply?", "Missing Weeks")
    if "Ambiguous fixed/non-fixed" in problems:
        return ("Reconciliation", "Resolve ambiguous fixed/non-fixed mapping", "Shared Session Queries")
    if "Partial fixed/non-fixed" in problems:
        return ("Reconciliation", "Confirm fixed/non-fixed split", "Shared Session Queries")
    if "Room clash" in problems:
        return ("Conflict", _normalise_problem(problems, "Room clash"), "Room Conflicts")
    if "Staff clash" in problems:
        return ("Conflict", _normalise_problem(problems, "Staff clash"), "Tutor Conflicts")
    if "Student group" in problems or "lunch block" in problems:
        return ("Conflict", _normalise_problem(problems, "Programme clash"), "Programme Conflicts")
    if "Blocked time" in problems or "18:00" in problems or "term break" in problems:
        return ("Placement rule", _normalise_problem(problems, "Blocked or invalid fixed time"), "Room Conflicts")
    return ("Other", _normalise_problem(problems, "Clarify source row"), "Shared Session Queries")


def _normalise_problem(problem: str, fallback: str) -> str:
    """Collapse a problem string into a concise decision label."""
    text = re.sub(r"\s+", " ", str(problem or "")).strip()
    return text[:120] if text else fallback


def grouped_supervisor_queries(issue_rows: list[dict[str, object]], sessions: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return grouped supervisor decisions plus linked affected rows."""
    unique_rows = _unique_affected_rows([row for row in issue_rows if row.get("severity") == "critical"], sessions)
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in unique_rows:
        grouped[_query_key(row)].append(row)

    summary: list[dict[str, object]] = []
    affected: list[dict[str, object]] = []
    for index, ((category, label, sheet_group), rows) in enumerate(sorted(grouped.items()), start=1):
        query_id = f"Q{index:03d}"
        occurrences = sum(_teaching_occurrences(row) for row in rows)
        problem_text = "; ".join(sorted({str(row.get("problems", "")) for row in rows if row.get("problems")}))
        summary.append(
            {
                "query ID": query_id,
                "issue category": category,
                "decision group": sheet_group,
                "number of affected rows": len(rows),
                "number of affected teaching occurrences": occurrences,
                "plain-language explanation": label,
                "recommended question": _question_for_problem(problem_text),
                "safe available options": _options_for_problem(problem_text),
                "system recommendation": _system_recommendation(problem_text),
                "impact if unresolved": "Engineering generation remains blocked for linked critical rows.",
            }
        )
        for row in rows:
            affected.append({"query ID": query_id, **row})
    return summary, affected


def _system_recommendation(problem: str) -> str:
    """Return system recommendation only where evidence supports one."""
    text = problem.casefold()
    if "eng external venue" in text:
        return "Template 2 recognises ENG External Venue; confirm external-venue treatment."
    if "week" in text:
        return "No safe automatic recovery found; request approved teaching weeks."
    if "room clash" in text or "staff clash" in text:
        return "Do not move fixed sessions; confirm shared versus separate classes."
    return "Supervisor clarification required."


def _options_for_problem(problem: str) -> str:
    """Return source-owner options for one problem."""
    text = problem.casefold()
    if "room" in text or "location" in text:
        return "Confirm room alias, add venue to official room data, or mark as external/manual."
    if "week" in text:
        return "Provide teaching weeks or confirm an exact linked requirement that supplies them."
    if "shared" in text or "clash" in text:
        return "Confirm shared class, duplicate row, or separate sessions requiring source correction."
    return "Correct the source row or confirm the intended treatment."


def _question_for_problem(problem: str) -> str:
    """Return a recommended clarification question."""
    text = problem.casefold()
    if "week" in text:
        return "Which teaching weeks apply to this fixed session?"
    if "exact fixed room" in text or "external venue" in text:
        return "Is this room name/code valid, and how should it map to the official venue list?"
    if "room clash" in text or "staff clash" in text:
        return "Are these rows one shared class or separate classes that currently clash?"
    if "blocked" in text or "18:00" in text:
        return "Should this fixed session override the normal blocked-time rule, or is the source time incorrect?"
    return "What is the intended treatment for this fixed-session row?"


def export_fixed_issue_workbooks(
    *,
    fixed_sessions: list[FixedSession],
    courses: list[Course],
    assignments: list[Assignment],
    rooms: list[Room],
    loader_report: FixedSessionLoaderReport,
    reconciliation_report: FixedReconciliationReport,
    mapping_issues: list[dict[str, object]],
    conflict_issues: list[dict[str, object]],
    root_cause_path: Path,
    conflict_triage_path: Path,
    supervisor_queries_path: Path,
    location_evidence_path: Path | None = None,
    supervisor_pack_path: Path | None = None,
    resolution_template_path: Path | None = None,
    resolution_audit_path: Path | None = None,
    resolution_input_path: Path | None = None,
    template2_path: Path = DEFAULT_TEMPLATE2_FILE,
) -> dict[str, int]:
    """Export fixed-session root-cause, conflict triage and supervisor-query workbooks."""
    sessions = _session_lookup(fixed_sessions, loader_report)
    issue_rows = _issue_rows(loader_report, reconciliation_report, mapping_issues, conflict_issues)
    unique_rows = _unique_affected_rows(issue_rows, sessions)
    mapping_rows = _mapping_rows(mapping_issues, fixed_sessions, courses, sessions)
    shared_rows = _shared_session_rows(assignments)
    normalisation_rows = _normalisation_rows(assignments, fixed_sessions)
    conflict_rows = conflict_triage_rows(assignments)
    supervisor_rows = _supervisor_queries(issue_rows, sessions)
    query_summary, affected_rows = grouped_supervisor_queries(issue_rows, sessions)
    location_rows = _location_evidence_rows(mapping_issues, sessions, rooms, template2_path)

    root_cause_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(root_cause_path, engine="openpyxl") as writer:
        pd.DataFrame(_summary(issue_rows, unique_rows, shared_rows)).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(issue_rows).to_excel(writer, sheet_name="Issue Instances", index=False)
        pd.DataFrame(unique_rows).to_excel(writer, sheet_name="Unique Affected Rows", index=False)
        pd.DataFrame(mapping_rows).to_excel(writer, sheet_name="Mapping Issues", index=False)
        pd.DataFrame([row for row in conflict_rows if "conflict" in str(row.get("conflict type", "")).casefold()]).to_excel(
            writer,
            sheet_name="Clash Issues",
            index=False,
        )
        pd.DataFrame(shared_rows).to_excel(writer, sheet_name="Possible Shared Sessions", index=False)
        pd.DataFrame(normalisation_rows).to_excel(writer, sheet_name="Safe Normalisation Candidates", index=False)
        pd.DataFrame(query_summary).to_excel(writer, sheet_name="Supervisor Queries", index=False)

    conflict_triage_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(conflict_triage_path, engine="openpyxl") as writer:
        pd.DataFrame(_conflict_summary(conflict_rows, shared_rows)).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame([row for row in conflict_rows if row["conflict type"] == "Room conflict"]).to_excel(writer, sheet_name="Room Conflicts", index=False)
        pd.DataFrame([row for row in conflict_rows if row["conflict type"] == "Tutor conflict"]).to_excel(writer, sheet_name="Tutor Conflicts", index=False)
        pd.DataFrame([row for row in conflict_rows if row["conflict type"] == "Programme conflict"]).to_excel(writer, sheet_name="Programme Conflicts", index=False)
        pd.DataFrame([row for row in shared_rows if row["classification"] == "Confirmed shared session"]).to_excel(writer, sheet_name="Duplicate Candidates", index=False)
        pd.DataFrame(shared_rows).to_excel(writer, sheet_name="Shared-Session Candidates", index=False)
        pd.DataFrame([row for row in conflict_rows if row["automatic resolution allowed"] == "No"]).to_excel(writer, sheet_name="Genuine Source Conflicts", index=False)
        pd.DataFrame([row for row in conflict_rows if row["automatic resolution allowed"] == "No"]).to_excel(writer, sheet_name="Unresolved Cases", index=False)

    supervisor_queries_path.parent.mkdir(parents=True, exist_ok=True)
    _export_grouped_supervisor_queries(supervisor_queries_path, query_summary, affected_rows)
    if location_evidence_path is not None:
        export_location_mapping_evidence(mapping_issues, location_rows, location_evidence_path)
    if supervisor_pack_path is not None:
        _export_supervisor_pack(supervisor_pack_path, query_summary, affected_rows, location_rows, conflict_rows, loader_report, shared_rows, issue_rows)
    if resolution_template_path is not None:
        export_resolution_template(resolution_template_path, [str(row["query ID"]) for row in query_summary])
    if resolution_audit_path is not None:
        resolution = load_resolution_workbook(resolution_input_path or resolution_template_path or Path(""), {str(row["query ID"]) for row in query_summary})
        export_resolution_audit(resolution, resolution_audit_path)
    return {
        "issue_instances": len(issue_rows),
        "critical_issue_instances": sum(1 for row in issue_rows if row.get("severity") == "critical"),
        "unique_affected_rows": len(unique_rows),
        "mapping_issues": len(mapping_rows),
        "shared_sessions": len(shared_rows),
        "conflict_rows": len(conflict_rows),
        "supervisor_queries": len(supervisor_rows),
        "supervisor_decisions": len(query_summary),
        "location_evidence_rows": len(location_rows),
    }


def _location_evidence_rows(
    mapping_issues: list[dict[str, object]],
    sessions: dict[str, dict[str, object]],
    rooms: list[Room],
    template2_path: Path,
) -> list[dict[str, object]]:
    """Return evidence rows for fixed-session location mapping issues."""
    rows: list[dict[str, object]] = []
    for issue in mapping_issues:
        ref = f"{issue.get('source')}:{issue.get('sheet')}:{issue.get('row')}"
        source = sessions.get(ref, {})
        original = str(source.get("location") or "")
        evidence = classify_location(original, rooms, template2_path)
        rows.append(
            {
                "source ref": ref,
                "original value": evidence.original_value,
                "normalised value": evidence.normalised_value,
                "source workbook": source.get("source workbook", ""),
                "source sheet": source.get("source sheet", ""),
                "source row": source.get("source row", ""),
                "candidate venue code": evidence.candidate_venue_code,
                "authoritative evidence source": evidence.authoritative_evidence_source,
                "capacity": evidence.capacity,
                "room type": evidence.room_type,
                "host key": evidence.host_key,
                "confidence": evidence.confidence,
                "treatment": evidence.treatment,
                "blocking status": evidence.blocking_status,
                "current problem": issue.get("problem", ""),
            }
        )
    return rows


def _export_grouped_supervisor_queries(path: Path, query_summary: list[dict[str, object]], affected_rows: list[dict[str, object]]) -> None:
    """Export grouped supervisor query workbook."""
    categories = {
        "Location Queries": [row for row in query_summary if row.get("decision group") == "Location Queries"],
        "Missing Weeks": [row for row in query_summary if row.get("decision group") == "Missing Weeks"],
        "Shared Session Queries": [row for row in query_summary if row.get("decision group") == "Shared Session Queries"],
        "Room Conflicts": [row for row in query_summary if row.get("decision group") == "Room Conflicts"],
        "Tutor Conflicts": [row for row in query_summary if row.get("decision group") == "Tutor Conflicts"],
        "Programme Conflicts": [row for row in query_summary if row.get("decision group") == "Programme Conflicts"],
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(query_summary).to_excel(writer, sheet_name="Query Summary", index=False)
        pd.DataFrame(affected_rows).to_excel(writer, sheet_name="Affected Source Rows", index=False)
        for sheet, rows in categories.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame(_resolution_options()).to_excel(writer, sheet_name="Resolution Options", index=False)


def _resolution_options() -> list[dict[str, str]]:
    """Return supported supervisor resolution options."""
    return [
        {"Decision": "CONFIRM_SHARED_SESSION", "Use": "Rows are one shared class."},
        {"Decision": "CONFIRM_SEPARATE_SESSIONS", "Use": "Rows are separate classes and source data must avoid clashes."},
        {"Decision": "CONFIRM_ROOM_ALIAS", "Use": "Approved venue alias or official room code."},
        {"Decision": "CONFIRM_EXTERNAL_VENUE", "Use": "Approved external venue label."},
        {"Decision": "PROVIDE_TEACHING_WEEKS", "Use": "Approved teaching-week expression such as 1-6,8-13."},
        {"Decision": "CONFIRM_PROGRAMME_GROUP", "Use": "Approved programme/group relationship."},
        {"Decision": "REMOVE_DUPLICATE_SOURCE_ROW", "Use": "Source row is a duplicate and should not add demand."},
        {"Decision": "SOURCE_DATA_REQUIRES_CORRECTION", "Use": "Raw source file needs correction before generation."},
    ]


def _export_supervisor_pack(
    path: Path,
    query_summary: list[dict[str, object]],
    affected_rows: list[dict[str, object]],
    location_rows: list[dict[str, object]],
    conflict_rows: list[dict[str, object]],
    loader_report: FixedSessionLoaderReport,
    shared_rows: list[dict[str, object]],
    issue_rows: list[dict[str, object]],
) -> None:
    """Export a plain-language supervisor clarification package."""
    critical_count = sum(1 for row in issue_rows if row.get("severity") == "critical")
    executive = [
        {"Topic": "Purpose", "Detail": "The scheduler detected inconsistent fixed-session data before generating the Engineering timetable."},
        {"Topic": "Safety rule", "Detail": "Fixed sessions cannot be moved automatically, and raw institutional workbooks are unchanged."},
        {"Topic": "Fixed source rows", "Detail": loader_report.source_rows},
        {"Topic": "Valid fixed rows", "Detail": loader_report.fixed_rows_loaded},
        {"Topic": "Fixed teaching occurrences", "Detail": "See fixed-session audit for occurrence-level detail."},
        {"Topic": "Safely grouped shared sessions", "Detail": len(shared_rows)},
        {"Topic": "Unresolved critical issues", "Detail": critical_count},
        {"Topic": "Unique supervisor decisions required", "Detail": len(query_summary)},
    ]
    instructions = [
        {"Step": 1, "Instruction": "Review the Decisions Required sheet first."},
        {"Step": 2, "Instruction": "Use Affected Rows to see every source row linked to each decision."},
        {"Step": 3, "Instruction": "Enter approved decisions only in fixed_session_resolution_template.xlsx."},
        {"Step": 4, "Instruction": "Do not edit raw source workbooks for automated overrides."},
    ]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(executive).to_excel(writer, sheet_name="Executive Summary", index=False)
        pd.DataFrame(query_summary).to_excel(writer, sheet_name="Decisions Required", index=False)
        pd.DataFrame(affected_rows).to_excel(writer, sheet_name="Affected Rows", index=False)
        pd.DataFrame(location_rows).to_excel(writer, sheet_name="Location Evidence", index=False)
        pd.DataFrame(conflict_rows).to_excel(writer, sheet_name="Conflict Evidence", index=False)
        pd.DataFrame([row for row in affected_rows if "week" in str(row.get("problems", "")).casefold()]).to_excel(
            writer,
            sheet_name="Missing Information",
            index=False,
        )
        pd.DataFrame(_resolution_options()).to_excel(writer, sheet_name="Proposed Resolutions", index=False)
        pd.DataFrame(instructions).to_excel(writer, sheet_name="Instructions", index=False)


def _conflict_summary(conflict_rows: list[dict[str, object]], shared_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return fixed-conflict summary rows."""
    counts = Counter(str(row.get("conflict type", "")) for row in conflict_rows)
    rows = [
        {"Metric": "Conflict rows", "Value": len(conflict_rows)},
        {"Metric": "Confirmed shared sessions", "Value": len(shared_rows)},
    ]
    rows.extend({"Metric": conflict_type, "Value": count} for conflict_type, count in sorted(counts.items()))
    return rows
