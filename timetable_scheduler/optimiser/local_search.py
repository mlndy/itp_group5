"""Local-search optimiser for reducing soft timetable violations."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Iterable

from config import VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Room, TimeSlot
from engine.constraint_checker import annotate_schedule_violations, count_soft_violations
from generator.scheduler import get_candidate_rooms


@dataclass(slots=True)
class OptimisationResult:
    """Optimised schedule with acceptance metadata."""

    assignments: list[Assignment]
    iterations_completed: int


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


def score_schedule(assignments: list[Assignment]) -> int:
    """Return a weighted timetable score; lower is better."""
    reasons = _snapshot_unscheduled_reasons(assignments)
    annotate_schedule_violations(assignments)
    hard = sum(len(item.hard_violations) for item in assignments if _is_scheduled(item))
    soft = sum(len(item.soft_violations) for item in assignments)
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


def try_move_assignment(
    index: int,
    assignments: list[Assignment],
    rooms: list[Room],
    rng: random.Random,
    max_candidates: int = 8,
) -> list[Assignment]:
    """Try moving one assignment and return the best found schedule."""
    current = assignments[index]
    if not _is_scheduled(current):
        return assignments

    current_score = score_schedule(assignments)
    best_schedule = assignments
    best_score = current_score

    candidate_rooms = get_candidate_rooms(current.course, rooms)[:5]
    candidate_slots = list(_candidate_timeslots(current))
    rng.shuffle(candidate_rooms)
    rng.shuffle(candidate_slots)

    attempts = 0
    for room in candidate_rooms:
        for timeslot in candidate_slots:
            if attempts >= max_candidates:
                return best_schedule
            attempts += 1
            if current.room == room and current.timeslot == timeslot:
                continue
            replacement = Assignment(course=current.course, room=room, timeslot=timeslot)
            candidate_schedule = _replace_assignment(assignments, index, replacement)
            hard_count = _scheduled_hard_violations(candidate_schedule)
            if hard_count != 0:
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
) -> OptimisationResult:
    """Improve scheduled assignments using local search and report iterations."""
    rng = random.Random(seed)
    best = copy.deepcopy(assignments)
    reasons = _snapshot_unscheduled_reasons(best)
    annotate_schedule_violations(best)
    _restore_unscheduled_reasons(best, reasons)

    if _scheduled_hard_violations(best) != 0:
        return OptimisationResult(best, 0)

    best_score = score_schedule(best)
    baseline = copy.deepcopy(best)
    baseline_score = best_score
    iterations_completed = 0
    for _ in range(max_iterations):
        iterations_completed += 1
        indices = [index for index, assignment in enumerate(best) if _is_scheduled(assignment)]
        rng.shuffle(indices)
        improved = False
        for index in indices:
            candidate = try_move_assignment(index, best, rooms, rng)
            hard_count = _scheduled_hard_violations(candidate)
            candidate_score = score_schedule(candidate)
            if hard_count == 0 and candidate_score < best_score:
                best = candidate
                best_score = candidate_score
                improved = True
                break
        if not improved:
            break

    if best_score > baseline_score:
        best = baseline
    reasons = _snapshot_unscheduled_reasons(best)
    annotate_schedule_violations(best)
    _restore_unscheduled_reasons(best, reasons)
    return OptimisationResult(best, iterations_completed)


def optimise_schedule(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
) -> list[Assignment]:
    """Improve a feasible timetable using local search."""
    return optimise_schedule_with_stats(assignments, rooms, max_iterations=max_iterations, seed=seed).assignments


def optimisation_summary(before: list[Assignment], after: list[Assignment]) -> dict[str, int]:
    """Return before/after violation counts."""
    return {
        "hard_before": _scheduled_hard_violations(before),
        "soft_before": _soft_violations(before),
        "hard_after": _scheduled_hard_violations(after),
        "soft_after": _soft_violations(after),
    }
