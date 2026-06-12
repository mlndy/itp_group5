"""Local-search optimiser for reducing soft timetable violations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Iterable

from config import VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Room, TimeSlot
from engine.constraint_checker import annotate_schedule_violations, count_hard_violations, count_soft_violations, soft_score
from generator.scheduler import get_candidate_rooms, schedulable_weeks


@dataclass(slots=True)
class OptimisationReport:
    """Summary of a local-search optimisation run."""

    accepted_moves: int = 0
    iterations_run: int = 0
    soft_score_before: int = 0
    soft_score_after: int = 0


def score_schedule(assignments: list[Assignment]) -> int:
    """Return a weighted timetable score; lower is better."""
    annotate_schedule_violations(assignments)
    hard = sum(len(item.hard_violations) for item in assignments)
    soft = soft_score(assignments)
    unscheduled = sum(1 for item in assignments if item.room is None or item.timeslot is None)
    return hard * 100_000 + unscheduled * 50_000 + soft


def _candidate_timeslots(assignment: Assignment) -> Iterable[TimeSlot]:
    """Yield deterministic alternative timeslots for an assignment."""
    if assignment.timeslot is None:
        weeks = schedulable_weeks(assignment.course.teaching_weeks)
    else:
        weeks = schedulable_weeks([assignment.timeslot.week])
    for week in weeks:
        for day in VALID_DAYS:
            for start in VALID_START_TIMES:
                yield TimeSlot(day=day, start_time=start, week=week)


def _timeslot_sort_key(timeslot: TimeSlot) -> tuple[int, int, int]:
    """Sort timeslots deterministically by week, day, and start time."""
    day_index = VALID_DAYS.index(timeslot.day) if timeslot.day in VALID_DAYS else len(VALID_DAYS)
    start_index = VALID_START_TIMES.index(timeslot.start_time) if timeslot.start_time in VALID_START_TIMES else len(VALID_START_TIMES)
    return (timeslot.week, day_index, start_index)


def _sorted_candidate_timeslots(assignment: Assignment) -> list[TimeSlot]:
    """Return deterministic candidate slots for one assignment."""
    return sorted(_candidate_timeslots(assignment), key=_timeslot_sort_key)


def _replace_assignment(
    assignments: list[Assignment],
    index: int,
    replacement: Assignment,
) -> list[Assignment]:
    """Return a copied schedule with one assignment replaced."""
    copied = copy.deepcopy(assignments)
    copied[index] = replacement
    return copied


def _candidate_priority(assignment: Assignment, index: int) -> tuple[int, int, str, str, int, str, str]:
    """Order likely-problematic assignments first."""
    timeslot = assignment.timeslot
    return (
        -len(assignment.soft_violations),
        index,
        assignment.course.module_code,
        assignment.course.activity,
        timeslot.week if timeslot else 0,
        timeslot.day if timeslot else "",
        timeslot.start_time if timeslot else "",
    )


def _is_scheduled(assignment: Assignment) -> bool:
    """Return True if an assignment already has both room and timeslot."""
    return assignment.room is not None and assignment.timeslot is not None


def _evaluate_candidate(
    assignments: list[Assignment],
    index: int,
    room: Room,
    timeslot: TimeSlot,
) -> tuple[list[Assignment], int] | None:
    """Return a hard-feasible candidate schedule and its score, if it improves."""
    current = assignments[index]
    if current.room == room and current.timeslot == timeslot:
        return None

    replacement = Assignment(course=current.course, room=room, timeslot=timeslot)
    candidate_schedule = _replace_assignment(assignments, index, replacement)
    annotate_schedule_violations(candidate_schedule)
    hard_count = sum(len(item.hard_violations) for item in candidate_schedule)
    if hard_count != 0:
        return None
    candidate_score = score_schedule(candidate_schedule)
    return candidate_schedule, candidate_score


def try_move_assignment(
    index: int,
    assignments: list[Assignment],
    rooms: list[Room],
    max_candidates: int | None = None,
) -> list[Assignment]:
    """Try moving one scheduled assignment and return the best found schedule."""
    current = assignments[index]
    if not _is_scheduled(current):
        return assignments

    current_score = score_schedule(assignments)
    best_schedule = assignments
    best_score = current_score

    candidate_rooms = get_candidate_rooms(current.course, rooms)
    candidate_slots = _sorted_candidate_timeslots(current)

    attempts = 0
    for room in candidate_rooms:
        for timeslot in candidate_slots:
            if max_candidates is not None and attempts >= max_candidates:
                return best_schedule
            attempts += 1
            evaluated = _evaluate_candidate(assignments, index, room, timeslot)
            if evaluated is None:
                continue
            candidate_schedule, candidate_score = evaluated
            if candidate_score < best_score:
                best_schedule = candidate_schedule
                best_score = candidate_score

    return best_schedule


def optimise_schedule_with_report(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
) -> tuple[list[Assignment], OptimisationReport]:
    """Improve a feasible timetable using deterministic local search."""
    _ = seed  # Kept for API stability; ordering is deterministic.
    best = copy.deepcopy(assignments)
    annotate_schedule_violations(best)

    report = OptimisationReport()
    report.soft_score_before = soft_score(best)

    if count_hard_violations(best) != 0:
        report.soft_score_after = report.soft_score_before
        return best, report

    best_score = score_schedule(best)
    for iteration in range(1, max_iterations + 1):
        report.iterations_run = iteration
        ordered_indices = sorted(range(len(best)), key=lambda idx: _candidate_priority(best[idx], idx))
        improved = False
        for index in ordered_indices:
            candidate = try_move_assignment(index, best, rooms)
            if candidate is best:
                continue
            annotate_schedule_violations(candidate)
            hard_count = sum(len(item.hard_violations) for item in candidate)
            if hard_count != 0:
                continue
            candidate_score = score_schedule(candidate)
            if candidate_score < best_score:
                best = candidate
                best_score = candidate_score
                report.accepted_moves += 1
                improved = True
                break
        if not improved:
            break

    annotate_schedule_violations(best)
    report.soft_score_after = soft_score(best)
    return best, report


def optimise_schedule(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
) -> list[Assignment]:
    """Compatibility wrapper returning only the optimised schedule."""
    schedule, _ = optimise_schedule_with_report(assignments, rooms, max_iterations=max_iterations, seed=seed)
    return schedule


def optimisation_summary(before: list[Assignment], after: list[Assignment]) -> dict[str, int]:
    """Return before/after violation counts."""
    return {
        "hard_before": count_hard_violations(before),
        "soft_before": count_soft_violations(before),
        "hard_after": count_hard_violations(after),
        "soft_after": count_soft_violations(after),
    }
