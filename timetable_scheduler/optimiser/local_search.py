"""Local-search optimiser for reducing soft timetable violations."""

from __future__ import annotations

import copy
import random
from typing import Iterable

from config import VALID_DAYS, VALID_START_TIMES
from data.models import Assignment, Room, TimeSlot
from engine.constraint_checker import annotate_schedule_violations, count_hard_violations, count_soft_violations
from generator.scheduler import get_candidate_rooms


def score_schedule(assignments: list[Assignment]) -> int:
    """Return a weighted timetable score; lower is better."""
    annotate_schedule_violations(assignments)
    hard = sum(len(item.hard_violations) for item in assignments)
    soft = sum(len(item.soft_violations) for item in assignments)
    unscheduled = sum(1 for item in assignments if item.room is None or item.timeslot is None)
    return hard * 10_000 + unscheduled * 5_000 + soft


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
            annotate_schedule_violations(candidate_schedule)
            hard_count = sum(len(item.hard_violations) for item in candidate_schedule)
            if hard_count != 0:
                continue
            soft_count = sum(len(item.soft_violations) for item in candidate_schedule)
            candidate_score = soft_count
            if candidate_score < best_score:
                best_schedule = candidate_schedule
                best_score = candidate_score
    return best_schedule


def optimise_schedule(
    assignments: list[Assignment],
    rooms: list[Room],
    max_iterations: int = 10,
    seed: int = 42,
) -> list[Assignment]:
    """Improve a feasible timetable using local search."""
    rng = random.Random(seed)
    best = copy.deepcopy(assignments)
    annotate_schedule_violations(best)

    if count_hard_violations(best) != 0:
        return best

    best_score = score_schedule(best)
    for _ in range(max_iterations):
        indices = list(range(len(best)))
        rng.shuffle(indices)
        improved = False
        for index in indices:
            candidate = try_move_assignment(index, best, rooms, rng)
            annotate_schedule_violations(candidate)
            hard_count = sum(len(item.hard_violations) for item in candidate)
            soft_count = sum(len(item.soft_violations) for item in candidate)
            candidate_score = hard_count * 10_000 + soft_count
            if hard_count == 0 and candidate_score < best_score:
                best = candidate
                best_score = candidate_score
                improved = True
                break
        if not improved:
            break
    annotate_schedule_violations(best)
    return best


def optimisation_summary(before: list[Assignment], after: list[Assignment]) -> dict[str, int]:
    """Return before/after violation counts."""
    return {
        "hard_before": count_hard_violations(before),
        "soft_before": count_soft_violations(before),
        "hard_after": count_hard_violations(after),
        "soft_after": count_soft_violations(after),
    }
