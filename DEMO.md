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
