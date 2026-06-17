# AGENTS.md - DSC2204 ITP Timetabling Project

## Project Overview

This repository contains a Python prototype for the DSC2204 Integrative Team Project.

Project title: **Timetabling System for SIT Engineering Cluster**

The system reads Excel-based input data, models courses/rooms/timeslots, generates a feasible timetable, checks hard and soft constraints, applies optional optimisation, and exports results back to Excel.

Treat this as an operations and supply chain resource-allocation prototype, not just a programming exercise.

## Current Phase

Current phase: **Engineering Cluster Schedule Completion**

Main deliverable: generate a usable Engineering cluster timetable, including DSC.

DSC-only mode remains useful for testing and regression checks, but Engineering scope is the final target.

Scenario comparison and what-if analysis are on hold. Do not add extra innovation features until Engineering scheduling readiness is stronger.

## Current Validated State

The core prototype is complete through:

1. Data modelling and Excel loading
2. Constraint checker
3. Greedy schedule generator
4. Local search optimiser
5. Excel exporter and full pipeline
6. Engineering controlled demo safety controls
7. Preflight validation and run summary reporting

Current validated result:

- Tests: `54 passed`
- DSC demo: runs successfully with `0` hard violations on scheduled assignments
- Engineering controlled demo: runs successfully
- Previous Engineering controlled demo output:
  - Scheduled assignments: `2093`
  - Unscheduled assignments: `307`
  - Hard violations on scheduled assignments: `0`

Preflight report and run summary report now exist and should be preserved.

## Coding Rules

Follow these rules for all future code changes:

- Use Python with type hints.
- Keep functions small and single-purpose.
- Add short docstrings for new functions.
- Use existing dataclasses from `data/models.py`.
- Do not redefine `Course`, `Room`, `TimeSlot`, or `Assignment`.
- Use constants from `config.py`; do not hardcode timetable rules.
- Do not change Excel timetable output formats unless explicitly requested or required for report clarity.
- Do not rename existing public functions unless tests and call sites are updated.
- Avoid broad rewrites. Make small, reviewable changes.

## Hard Constraint Rule

Hard constraints must never be weakened.

The scheduler and optimiser must never accept scheduled assignments with hard violations.

If a class cannot be scheduled safely, leave it unscheduled and report the reason. Do not force invalid assignments into the timetable.

This framing is important for the final presentation:

> The prototype prioritises feasibility. It schedules only assignments that satisfy all hard constraints and leaves the remaining classes unscheduled instead of hiding conflicts.

## Engineering Readiness Rules

For Engineering scope:

- `--scope eng` must include the Engineering cluster and DSC data/modules when present in the Engineering input folder.
- Hard violations on scheduled assignments must remain `0`.
- Unscheduled assignments must not be hidden.
- If full scheduling is not possible, reports must clearly explain what remains unscheduled and why.
- Improve coverage only through safe ordering, filtering, reporting, and retry controls that preserve hard constraints.

## Engineering Final Validation

- The final deliverable is Engineering scope, not DSC-only.
- `--scope eng` must include DSC.
- Scheduled assignments must have `0` hard violations.
- Unscheduled assignments must remain visible.
- Results must be numerically consistent: total assignments = scheduled assignments + unscheduled assignments.
- If result totals change between runs, the report must explain why.
- Do not claim improvement using scheduled count alone unless the total assignment pool is the same.
- Preserve `preflight_report.xlsx` and `run_summary.xlsx`.
- Scenario comparison is still on hold.

## Engineering Coverage and Bottleneck Resolution

- Current validated Engineering result:
  - Total assignments: `2593`
  - Scheduled assignments: `2119`
  - Unscheduled assignments: `474`
  - Hard violations on scheduled assignments: `0`
- Current tests: `61 passed`
- The next goal is to reduce unscheduled assignments safely.
- Never reduce the unscheduled count by accepting hard violations.
- Preserve `preflight_report.xlsx`, `run_summary.xlsx`, `Validation Checks`, `Run Metadata`, `Programme Breakdown`, and DSC evidence.
- Before changing scheduling behaviour, produce a reason and bottleneck breakdown.
- Scenario comparison remains on hold.
- Any scheduling improvement must be measured against the same input dataset and command.
- Total assignments must remain comparable between baseline and improved runs.

## Evidence-Driven Coverage Improvement

- Current comparable baseline:
  - Total assignments: `2593`
  - Scheduled assignments: `2119`
  - Unscheduled assignments: `474`
  - Hard violations on scheduled assignments: `0`
  - Tests: `67 passed`
- All future comparisons must use the same input dataset and total assignment count of `2593`.
- Update only one scheduling behaviour per iteration.
- Select the behaviour based on the largest category in `Unscheduled Breakdown`.
- Do not claim an improvement if the total assignment pool changes.
- Do not reduce unscheduled assignments by accepting hard violations.
- Preserve original unscheduled reasons and all reporting sheets.
- Scenario comparison remains on hold.

## Demand Metric Integrity and Coverage Audit

- Current tests: `68 passed`.
- Current Engineering result:
  - Reported scheduled assignments: `2119`
  - Reported unscheduled assignments: `474`
  - Reported total: `2593`
  - Hard violations on scheduled assignments: `0`
- A virtual-room resource experiment changed the reported total to `2753`.
- Input teaching demand must not change when room availability changes.
- Before further scheduler optimisation, define invariant demand metrics.
- Do not compare scheduling improvements using raw `Assignment` object counts if scheduled and unscheduled objects represent different units.
- Preserve all existing hard-safety and DSC-inclusion checks.
- Scenario comparison remains on hold.

## Virtual Room Semantics and Resource Capacity Validation

- Current tests: `78 passed`.
- Current stable Engineering demand baseline:
  - Input course records: `507`
  - Consolidated requirements: `465`
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2119`
  - Unscheduled teaching occurrences: `658`
  - Coverage rate: `76.31%`
  - Hard violations on scheduled assignments: `0`
- The dominant bottleneck is incomplete multi-week placement, especially for online synchronous two-hour lectures.
- Before adding or changing virtual-room capacity, verify how virtual rooms are represented in the source data and loader.
- Required teaching occurrences must remain `2777` for all comparable runs.
- Do not weaken room-conflict constraints unless the project requirements clearly show that virtual rooms are non-exclusive.
- Do not automatically create virtual rooms without evidence.
- Scenario comparison remains on hold.

## Online Delivery Resource Semantics

- Current tests: `85 passed`.
- Stable Engineering teaching demand:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2119`
  - Unscheduled teaching occurrences: `658`
  - Coverage rate: `76.31%`
  - Hard violations on scheduled assignments: `0`
- Resource audit:
  - Raw venue rows: `169`
  - Loaded physical rooms: `169`
  - Loaded virtual rooms: `1`
  - Virtual room ID: `ONLINE_ROOM`
  - Required online occurrences: `813`
  - Scheduled online occurrences: `196`
  - Unscheduled online occurrences: `617`
  - Online coverage: `24.11%`
- `ONLINE_ROOM` is created by the loader and is not one of the raw venue rows.
- The supplied TTConstraints workbook states that fully online lectures require no physical venue allocation.
- `ONLINE_ROOM` should be treated as a delivery-mode placeholder, not as one exclusive physical resource.
- Online classes must still respect tutor, student-group, time, calendar, duration, and week-pattern constraints.
- Physical room clashes must remain unchanged.
- Required teaching occurrences must remain `2777`.
- Do not add artificial virtual rooms.
- Scenario comparison remains on hold.

## Important Commands

Run tests from inside the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Expected result:

```text
54 passed
```

Run DSC demo:

```powershell
py main.py --scope dsc --max-iterations 2
```

Expected key result:

```text
Final hard violations on scheduled assignments: 0
```

Run Engineering final test:

```powershell
py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25
```

Expected key result:

```text
Hard violations on scheduled Engineering assignments: 0
```

Scheduled and unscheduled counts may vary after scheduling-readiness changes, but scheduled hard violations must remain `0`.

## Generated Files

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

## Workflow Rules

Before merging any branch:

1. Run `py -m pytest -q`
2. Run the DSC demo command
3. Run the Engineering final test command
4. Confirm scheduled hard violations are `0`
5. Check `git status --short`
6. Ensure generated output folders are not staged
7. Review `git diff`

Do not merge if tests fail or scheduled hard violations are introduced.

## Report and Presentation Framing

Use this framing in documentation and presentation:

- The problem is a real-world academic timetabling problem.
- The system models rooms, tutors, student groups, time slots, and course requirements.
- Hard constraints are treated as non-negotiable.
- Soft constraints are treated as quality improvements.
- The prototype is transparent: unresolved classes remain unscheduled and visible.
- Engineering mode is controlled with demo safety limits to avoid excessive search time.
- Unscheduled classes are not hidden; they represent cases requiring more search time, better input data, more rooms, or manual review.

Important phrasing:

> In Engineering controlled demo mode, the system schedules as many assignments as it can while keeping 0 hard violations on scheduled assignments. Remaining assignments are intentionally left unscheduled because the system refuses to force invalid allocations into the timetable.

## Do Not Do Unless Explicitly Requested

Do not:

- Replace the greedy scheduler with a completely new algorithm.
- Add OR-Tools or other heavy solver dependencies.
- Change the dataclasses.
- Change Template 2 output structure.
- Commit generated Excel outputs.
- Hide unscheduled assignments.
- Count unscheduled assignments as successful scheduled classes.
- Add scenario comparison or what-if analysis.
