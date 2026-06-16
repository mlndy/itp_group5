# AGENTS.md — DSC2204 ITP Timetabling Project

## Project overview

This repository contains a Python prototype for the DSC2204 Integrative Team Project.

Project title: **Timetabling System for SIT Engineering Cluster**

The system reads Excel-based input data, models courses/rooms/timeslots, generates a feasible timetable, checks hard and soft constraints, applies optional optimisation, and exports results back to Excel.

The project should be treated as an operations and supply chain resource-allocation prototype, not just a programming exercise.

## Current project stage

The core prototype is complete.

Completed stages:

1. Data modelling and Excel loading
2. Constraint checker
3. Greedy schedule generator
4. Local search optimiser
5. Excel exporter and full pipeline
6. Engineering controlled demo safety controls

Current validated result:

* Tests: `47 passed`
* DSC demo: runs successfully with `0` hard violations on scheduled assignments
* Engineering controlled demo: runs successfully
* Engineering controlled demo output:

  * Scheduled assignments: `2093`
  * Unscheduled assignments: `307`
  * Hard violations on scheduled assignments: `0`

The next stage is demo, documentation, and report readiness.

## Coding rules

Follow these rules for all future code changes:

* Use Python with type hints.
* Keep functions small and single-purpose.
* Add short docstrings for new functions.
* Use existing dataclasses from `data/models.py`.
* Do not redefine `Course`, `Room`, `TimeSlot`, or `Assignment`.
* Use constants from `config.py`; do not hardcode timetable rules.
* Do not change Excel output formats unless explicitly requested.
* Do not rename existing public functions unless tests and call sites are updated.
* Avoid broad rewrites. Make small, reviewable changes.

## Hard constraint rule

Hard constraints must never be weakened.

The scheduler and optimiser must never accept scheduled assignments with hard violations.

If a class cannot be scheduled safely, leave it unscheduled and report the reason. Do not force invalid assignments into the timetable.

This framing is important for the final presentation:

> The prototype prioritises feasibility. It schedules only assignments that satisfy all hard constraints and leaves the remaining classes unscheduled instead of hiding conflicts.

## Important commands

Run tests from inside the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Expected result:

```text
47 passed
```

Run DSC demo:

```powershell
py main.py --scope dsc --max-iterations 2
```

Expected key result:

```text
Final hard violations on scheduled assignments: 0
```

Run Engineering controlled demo:

```powershell
py main.py --scope eng --skip-optimisation --max-candidate-patterns 150 --max-retry-assignments 20 --skip-unscheduled-diagnostics --progress-interval 25
```

Expected key result:

```text
Hard violations on scheduled Engineering assignments: 0
```

Scheduled and unscheduled counts may vary slightly after future changes, but scheduled hard violations must remain `0`.

## Generated files

Running the prototype may create:

```text
timetable_scheduler/generated/
timetable_scheduler/output_files/
```

These folders are generated outputs and must not be committed unless explicitly requested.

Also do not commit:

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
```

Input Excel files required by the prototype should not be ignored or deleted.

## Workflow rules

Before merging any branch:

1. Run `py -m pytest -q`
2. Run the DSC demo command
3. Run the Engineering controlled demo command
4. Confirm scheduled hard violations are `0`
5. Check `git status --short`
6. Ensure generated output folders are not staged
7. Review `git diff`

Do not merge if tests fail or scheduled hard violations are introduced.

## Report and presentation framing

Use this framing in documentation and presentation:

* The problem is a real-world academic timetabling problem.
* The system models rooms, tutors, student groups, time slots, and course requirements.
* Hard constraints are treated as non-negotiable.
* Soft constraints are treated as quality improvements.
* The prototype is transparent: unresolved classes remain unscheduled and visible.
* Engineering mode is controlled with demo safety limits to avoid excessive search time.
* Unscheduled classes are not hidden; they represent cases requiring more search time, better input data, more rooms, or manual review.

Important phrasing:

> In Engineering controlled demo mode, the system scheduled 2,093 assignments with 0 hard violations on scheduled assignments. 307 assignments were intentionally left unscheduled because the system refuses to force invalid allocations into the timetable.

## Do not do unless explicitly requested

Do not:

* Replace the greedy scheduler with a completely new algorithm.
* Add OR-Tools or other heavy solver dependencies.
* Change the dataclasses.
* Change Template 2 output structure.
* Commit generated Excel outputs.
* Hide unscheduled assignments.
* Count unscheduled assignments as successful scheduled classes.
