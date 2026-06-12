# AGENTS.md

## Project

DSC2204 ITP — Timetabling System for SIT Engineering Cluster.

This is an academic timetabling prototype. Treat it as an operations/resource-allocation decision-support system, not just a coding task.

## Core Architecture

Keep this pipeline:

```text
Loader → Dataclasses → Constraint Engine → Greedy Scheduler → Local Search Optimiser → Excel Exporter → Diagnostics
```

Do not rewrite the architecture unless explicitly instructed.

## Current Milestone

The current focus is given in the user’s milestone prompt.

Only work on the milestone requested. Do not mix unrelated changes.

## Repository Inspection Policy

Always read this file first.

Then start with only the paths listed in the milestone prompt.

Do not scan the whole repository by default.

You may inspect additional files if needed for correctness, architecture consistency, tests, imports, or debugging. If you do, mention why in your summary.

Correctness is more important than token saving.

## Hard Rule

The scheduler and optimiser must never knowingly accept a scheduled assignment with hard violations.

If a class cannot be scheduled without breaking hard constraints, keep it unscheduled and report the reason clearly.

## Hard Constraints

Always preserve these:

```text
No room clash
No tutor clash
No student group clash
Room capacity >= enrolment
ONLINE uses virtual room only
F2F does not use virtual room
ODD courses run only on odd weeks
EVEN courses run only on even weeks
No public holiday / term break weeks
No classes before 09:00 or after 18:00
No Wednesday from 13:00
No Friday 12:00-14:00
No Friday after 17:00
No Saturday
Each group needs at least 1 free lunch hour between 11:00 and 14:00
```

Do not weaken hard constraints.

## Soft Constraints

Optimise these only when hard constraints remain valid:

```text
Avoid Online/F2F adjacent switches
Avoid tutor idle gaps > 2 hours
Avoid long group consecutive teaching hours
Cluster tutor classes
Prefer room utilisation >= 60%
Avoid first/last slots where possible
Prefer classes ending by 17:00
```

## Common Modules

Common modules shared by multiple cohorts must be scheduled at the same time.

Use combined enrolment.

Do not split common-module cohorts unless the data explicitly states a special request.

## Engineering Mode

Engineering mode may have unscheduled assignments.

This is acceptable only if:

```text
Scheduled assignments have 0 hard violations
Unscheduled assignments are reported separately
Reasons are diagnosed clearly
```

Do not hide unscheduled assignments.

Do not assign fake rooms or fake timeslots.

## Generated Files

Do not commit generated runtime files.

These should remain ignored:

```text
timetable_scheduler/generated/
timetable_scheduler/output_files/
```

## Testing

Before finishing a milestone, run:

```bash
python main.py
python -m pytest
```

For Engineering-related milestones, also run:

```bash
python main.py --scope eng --skip-optimisation
```

On Windows, the user may run:

```bash
py main.py
py -m pytest
py main.py --scope eng --skip-optimisation
```

The `openpyxl` data validation warning is acceptable.

## Branch Workflow

For each milestone:

```text
Create a branch
Modify only relevant files
Run tests
Summarise files changed
Report test results
Report remaining risks
Do not merge automatically
```

## Completion Standard

A milestone is complete only when:

```text
Relevant tests pass
DSC mode still runs
Scheduled DSC assignments have 0 hard violations
Engineering-related milestones run Engineering mode
Scheduled Engineering assignments have 0 hard violations
Generated files are not committed
Risks are stated honestly
```

## Current Milestone

Current focus:

```text
Milestone 5: Optimiser tuning and soft-score improvement

Key rule:

```text
Room1 must contain the assigned room ID from assignment.room.room_id.
```

Milestone 4 must not modify scheduler, optimiser, loader, diagnostics, or constraint logic unless strictly required for export compatibility.

Start with these files only:

```text
timetable_scheduler/output/exporter.py
timetable_scheduler/config.py
timetable_scheduler/main.py
timetable_scheduler/data/models.py
timetable_scheduler/tests/
timetable_scheduler/input/Upload template_System (Template 2).xlsx
```

If additional files are needed, explain why before inspecting them.

Generated Excel output files must not be committed.
