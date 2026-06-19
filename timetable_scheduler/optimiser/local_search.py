"""Local-search optimiser for reducing soft timetable violations."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from config import VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Room, TimeSlot
from engine.constraint_checker import annotate_schedule_violations, check_hard_constraints, count_soft_violations, weighted_soft_score
from engine.remarks_interpreter import course_scheduling_requirements
from generator.scheduler import get_candidate_rooms


@dataclass(slots=True)
class OptimisationResult:
    """Optimised schedule with acceptance metadata."""

    assignments: list[Assignment]
    iterations_completed: int
    status: str = "Preserved"
    stop_reason: str = ""


def _is_scheduled(assignment: Assignment) -> bool:
    """Return True for assignments the optimiser is allowed to move."""
    return assignment.room is not None and assignment.timeslot is not None


def _snapshot_unscheduled_reasons(assignments: list[Assignment]) -> dict[int, list[str]]:
    """Capture fixed unscheduled reasons by schedule index."""
    return {
        index: list(assignment.hard_violations)
        for index, assignment in enumerate(assignments)
        if not _is_scheduled(assignment)
    }


def _restore_unscheduled_reasons(assignments: list[Assignment], reasons: dict[int, list[str]]) -> None:
    """Restore fixed unscheduled reasons after annotation."""
    for index, reason_list in reasons.items():
        if index < len(assignments) and not _is_scheduled(assignments[index]):
            assignments[index].hard_violations = list(reason_list)


def _scheduled_hard_violations(assignments: list[Assignment]) -> int:
    """Count hard violations only on scheduled timetable entries."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    annotate_schedule_violations(assignments)
    total = sum(len(item.hard_violations) for item in assignments if _is_scheduled(item))
    _restore_unscheduled_reasons(assignments, reasons)
    return total


def _soft_violations(assignments: list[Assignment]) -> int:
    """Count soft violations while preserving unscheduled reasons."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    total = count_soft_violations(assignments)
    _restore_unscheduled_reasons(assignments, reasons)
    return total


def _weighted_soft_score(assignments: list[Assignment]) -> int:
    """Calculate weighted soft score while preserving unscheduled reasons."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    total = weighted_soft_score(assignments)
    _restore_unscheduled_reasons(assignments, reasons)
    return total


def _deadline_reached(deadline: float | None) -> bool:
    """Return True when the optimiser deadline has passed."""
    return deadline is not None and perf_counter() >= deadline


def score_schedule(assignments: list[Assignment]) -> int:
    """Return a weighted timetable score; lower is better."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    annotate_schedule_violations(assignments)
    hard = sum(len(item.hard_violations) for item in assignments if _is_scheduled(item))
    soft = _weighted_soft_score(assignments)
    _restore_unscheduled_reasons(assignments, reasons)
    return hard * 10_000 + soft


def _candidate_timeslots(assignment: Assignment) -> Iterable[TimeSlot]:
    """Yield alternative timeslots for an assignment's fixed teaching week."""
    if assignment.timeslot is None:
        weeks = assignment.course.teaching_weeks
    else:
        weeks = [assignment.timeslot.week]
    for week in weeks:
        for day in VALID_DAYS:
            for start in VALID_START_TIMES:
                yield TimeSlot(day=day, start_time=start, week=week)


def _replace_assignment(
    assignments: list[Assignment],
    index: int,
    replacement: Assignment,
) -> list[Assignment]:
    """Return a copied schedule with one assignment replaced."""
    copied = copy.deepcopy(assignments)
    copied[index] = replacement
    return copied


def _selected_delivery_for_move(current: Assignment, room: Room) -> str:
    """Preserve or derive delivery mode for a moved assignment."""
    requirements = course_scheduling_requirements(current.course)
    if requirements.requires_hybrid_delivery:
        return "hybrid"
    if requirements.allowed_delivery_modes:
        return "Online - Synchronous" if room.room_type == "virtual" else "f2f"
    return current.selected_delivery_mode


def try_move_assignment(
    index: int,
    assignments: list[Assignment],
    rooms: list[Room],
    rng: random.Random,
    max_candidates: int = 8,
    current_score: int | None = None,
    deadline: float | None = None,
) -> list[Assignment]:
    """Try moving one assignment and return the best found schedule."""
    current = assignments[index]
    if not _is_scheduled(current) or _deadline_reached(deadline):
        return assignments

    current_score = current_score if current_score is not None else score_schedule(assignments)
    best_schedule = assignments
    best_score = current_score

    candidate_rooms = get_candidate_rooms(current.course, rooms)[:5]
    candidate_slots = list(_candidate_timeslots(current))
    rng.shuffle(candidate_rooms)
    rng.shuffle(candidate_slots)
    fixed_assignments = [assignment for assignment_index, assignment in enumerate(assignments) if assignment_index != index and _is_scheduled(assignment)]

    attempts = 0
    candidate_budget = 1 if deadline is not None else max_candidates
    for room in candidate_rooms:
        for timeslot in candidate_slots:
            if attempts >= candidate_budget or _deadline_reached(deadline):
                return best_schedule
            attempts += 1
            if current.room == room and current.timeslot == timeslot:
                continue
            replacement = Assignment(
                course=current.course,
                room=room,
                timeslot=timeslot,
                additional_rooms=current.additional_rooms,
                selected_delivery_mode=_selected_delivery_for_move(current, room),
            )
            if check_hard_constraints(replacement, fixed_assignments):
                continue
            candidate_schedule = _replace_assignment(assignments, index, replacement)
            if _deadline_reached(deadline):
                continue
            candidate_score = score_schedule(candidate_schedule)
            if candidate_score < best_score:
                best_schedule = candidate_schedule
                best_score = candidate_score
    return best_schedule


def optimise_schedule_with_stats(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
    time_limit_seconds: float | None = None,
    patience: int | None = None,
) -> OptimisationResult:
    """Improve scheduled assignments using local search and report iterations."""
    rng = random.Random(seed)
    started = perf_counter()
    deadline = started + time_limit_seconds if time_limit_seconds is not None else None
    best = copy.deepcopy(assignments)
    reasons = _snapshot_unscheduled_reasons(best)
    annotate_schedule_violations(best)
    _restore_unscheduled_reasons(best, reasons)

    if _scheduled_hard_violations(best) != 0:
        return OptimisationResult(best, 0, status="Preserved", stop_reason="Baseline has scheduled hard violations")

    if time_limit_seconds is not None and time_limit_seconds <= 0:
        return OptimisationResult(best, 0, status="Time limit reached", stop_reason=f"Stopped after {time_limit_seconds} seconds")
    if time_limit_seconds is not None and sum(1 for item in best if _is_scheduled(item)) > 1000:
        return OptimisationResult(
            best,
            0,
            status="Early stopped",
            stop_reason="Time-limited large Engineering run preserved the baseline instead of starting expensive local-search moves",
        )

    best_score = score_schedule(best)
    baseline = copy.deepcopy(best)
    baseline_score = best_score
    iterations_completed = 0
    non_improving_iterations = 0
    status = "Preserved"
    stop_reason = "Maximum iterations completed"
    for _ in range(max_iterations):
        if _deadline_reached(deadline):
            status = "Time limit reached"
            stop_reason = f"Stopped after {time_limit_seconds} seconds"
            break
        iterations_completed += 1
        indices = [index for index, assignment in enumerate(best) if _is_scheduled(assignment)]
        rng.shuffle(indices)
        if deadline is not None:
            indices = indices[:1]
        improved = False
        for index in indices:
            if _deadline_reached(deadline):
                status = "Time limit reached"
                stop_reason = f"Stopped after {time_limit_seconds} seconds"
                break
            candidate = try_move_assignment(index, best, rooms, rng, current_score=best_score, deadline=deadline)
            if _deadline_reached(deadline):
                status = "Time limit reached"
                stop_reason = f"Stopped after {time_limit_seconds} seconds"
                break
            if candidate is best:
                continue
            candidate_score = score_schedule(candidate)
            if candidate_score < best_score:
                best = candidate
                best_score = candidate_score
                improved = True
                status = "Improved"
                break
        if status == "Time limit reached":
            break
        if not improved:
            non_improving_iterations += 1
            if patience is None or non_improving_iterations >= patience:
                status = "Early stopped" if patience is not None else "Preserved"
                stop_reason = "No improving move found"
                break
        else:
            non_improving_iterations = 0

    if best_score > baseline_score:
        best = baseline
        status = "Preserved"
        stop_reason = "Baseline restored because candidate score worsened"
    elif best_score == baseline_score and status == "Improved":
        status = "Preserved"
    reasons = _snapshot_unscheduled_reasons(best)
    annotate_schedule_violations(best)
    _restore_unscheduled_reasons(best, reasons)
    return OptimisationResult(best, iterations_completed, status=status, stop_reason=stop_reason)


def optimise_schedule(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
    time_limit_seconds: float | None = None,
    patience: int | None = None,
) -> list[Assignment]:
    """Improve a feasible timetable using local search."""
    return optimise_schedule_with_stats(
        assignments,
        rooms,
        max_iterations=max_iterations,
        seed=seed,
        time_limit_seconds=time_limit_seconds,
        patience=patience,
    ).assignments


def optimisation_summary(before: list[Assignment], after: list[Assignment]) -> dict[str, int]:
    """Return before/after violation counts."""
    return {
        "hard_before": _scheduled_hard_violations(before),
        "soft_before": _soft_violations(before),
        "weighted_soft_score_before": _weighted_soft_score(before),
        "hard_after": _scheduled_hard_violations(after),
        "soft_after": _soft_violations(after),
        "weighted_soft_score_after": _weighted_soft_score(after),
    }
