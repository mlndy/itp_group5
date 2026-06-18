# Timetabling System Demo

## Project Overview

This repository contains a Python prototype for the DSC2204 Integrative Team Project: a timetabling system for the SIT Engineering Cluster.

The system loads Excel-based course and room data, models timetable requirements, generates feasible assignments, checks hard and soft constraints, optionally optimises the schedule, and exports Excel reports.

The prototype prioritises feasibility. Classes are scheduled only when they satisfy hard constraints. If a class cannot be scheduled safely, it remains unscheduled and is reported instead of being hidden or forced into an invalid slot.

## Local Setup

Run these commands in Windows PowerShell from the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
py -m venv .venv
.\.venv\Scripts\Activate.ps1
cd timetable_scheduler
py -m pip install -r requirements.txt
```

## Run Tests

Run tests from inside the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Expected result:

```text
47 passed
```

## DSC Demo

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py main.py --scope dsc --max-iterations 2
```

Expected DSC result:

```text
Final hard violations on scheduled assignments: 0
```

## Engineering Controlled Demo

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py main.py --scope eng --skip-optimisation --max-candidate-patterns 150 --max-retry-assignments 20 --skip-unscheduled-diagnostics --progress-interval 25
```

Expected Engineering result:

- Scheduled assignments may be partial.
- Unscheduled assignments are allowed.
- Hard violations on scheduled assignments must be `0`.

Unscheduled assignments are intentionally reported, not hidden. They represent classes that could not be placed safely within the controlled demo search limits, input data, room availability, or current scheduling strategy.

## Recommended Live Engineering Demo

For the live presentation, use the non-optimised Engineering command. It generates the final feasible timetable evidence without the long optimiser runtime:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Expected live Engineering result:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`
- Online coverage: `813 / 813`
- DSC inclusion: `PASS`

This keeps the hard-constraint safety rule while allowing a wider candidate search and retry pass than the shorter demo command. The remaining F2F demand stays visible for operational review.

## Controlled Optimiser Evidence Run

The controlled optimiser run is evidence for report submission, not the recommended live-demo command:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py main.py --scope eng --max-iterations 5 --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

This may take approximately 17 minutes and is not recommended for the live presentation.

Verified optimiser evidence:

- Baseline soft violations: `3030`
- Optimised soft violations: `3019`
- Improvement: `11`
- Required teaching occurrences preserved: `2777`
- Scheduled teaching occurrences preserved: `2747`
- Scheduled hard violations preserved: `0`
- Online coverage preserved: `813 / 813`

If no improvement is found within the controlled iteration limit, the acceptable result is: optimisation preserved feasibility but did not find an improvement within the controlled iteration limit.

## Stakeholder Reports

Running the pipeline creates additional decision-support workbooks in `timetable_scheduler/generated/`.

`preflight_report.xlsx` lists input data issues found before scheduling, such as invalid class sizes, missing teaching weeks, delivery-mode concerns, or room capacity problems. These checks do not block scheduling; they help explain input risks before reviewing the timetable.

`run_summary.xlsx` summarises the completed run with headline schedule counts, hard and soft violations, unscheduled reasons, room utilisation, and programme breakdown. The programme breakdown includes a DSC indicator so stakeholders can confirm DSC is part of the Engineering cluster run. This gives stakeholders a compact view of feasibility, unresolved scheduling demand, and resource use without changing the Template 2 timetable export.

The `Unscheduled Analysis` sheet keeps each original scheduler reason and adds a category, programme, activity, delivery mode, class-size band, duration, failed week when available, common-module indicator, and candidate-limit indicator. The `Unscheduled Breakdown` sheet groups those rows into counts so the remaining Engineering bottlenecks can be explained without hiding unresolved assignments.

## How to Read the Engineering Result

The main feasibility success metric is `Hard violations on scheduled assignments = 0`. This means every assignment that received a room and timeslot satisfies the hard constraints.

Unscheduled assignments are not hidden. They remain visible in the summary and unscheduled reason breakdown so the project can explain what still needs more search time, better input data, more rooms, or manual review.

`Hard violations on all assignments` includes unscheduled feasibility failures. Do not confuse those with invalid scheduled timetable entries. The important safety distinction is that scheduled hard violations must remain `0`.

The `Programme Breakdown` sheet proves DSC inclusion in the Engineering run through the `DSC Indicator` column.

The `Validation Checks` sheet is the evidence page for presentation and reporting. It checks total consistency, scheduled hard-constraint safety, DSC inclusion, and unscheduled visibility.

The `Optimisation Summary` sheet records whether optimisation was enabled, runtime, iteration count, before/after teaching occurrence coverage, before/after hard and soft violations, soft-violation improvement, and acceptance statuses.

Use the unscheduled analysis tabs to explain why remaining assignments were not placed. Compare scheduled-count improvements only when the total assignment pool and command settings are the same.

## Online Delivery Resource Policy

The raw venue file contains physical rooms. The loader adds `ONLINE_ROOM` as a synthetic delivery-mode placeholder for fully online teaching.

Fully online lectures do not require physical venue allocation. Multiple unrelated online classes may therefore share `ONLINE_ROOM` at the same time.

This does not weaken hard constraints. Tutor clashes, student-group clashes, calendar blocks, duration checks, teaching-week rules, and all physical room clashes still apply.

The selected policy is defined in `timetable_scheduler/config.py` and appears in the `Resource Audit` sheet of `generated/run_summary.xlsx`.

## Troubleshooting

- Activate the virtual environment before running commands:

```powershell
.\.venv\Scripts\Activate.ps1
```

- Run pytest from the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

- Generated folders should not be committed:

```text
timetable_scheduler/generated/
timetable_scheduler/output_files/
```
