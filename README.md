# Engineering Timetable Scheduler

## Overview

This repository contains a local Python prototype for generating a proposed SIT Engineering Cluster timetable, including DSC.

The system:

- reads consolidated scheduling requirements and bundled Engineering data;
- validates workbook structure and source records;
- separates fixed and non-fixed sessions;
- anchors valid fixed sessions exactly as supplied;
- quarantines unsafe records instead of guessing missing information;
- schedules non-fixed classes around fixed reservations;
- checks hard constraints and reports unresolved cases;
- applies bounded soft-constraint optimisation when requested;
- exports the proposed timetable and submission-ready Template 2 workbook;
- creates programme, tutor and room visual timetable workbooks;
- generates validation, exception and traceability evidence.

The prototype is intended to improve the quality of life of timetabling staff by automating repetitive placement, checking, formatting and reporting work while keeping staff in control of exceptions and final approval.

## User Workflow

1. Open the desktop application.
2. Select the **Consolidated Schedule**.
3. Click **Generate Timetable**.
4. Review the **Proposed Timetable**.
5. Open the submission-ready workbook, evidence reports and visual timetables.
6. Review unscheduled or quarantined cases.
7. Approve or manually resolve exceptions.

## Installation

Run from Windows PowerShell at the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run The Desktop Application

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe run_ui.py
```

## Command-Line Validation Run

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

## Outputs

Generated outputs are written under `timetable_scheduler/generated/` and `timetable_scheduler/output_files/`. These folders are intentionally ignored by Git.

Main outputs:

- `output_files/final_timetable_engineering_cluster.xlsx`: proposed Engineering timetable.
- `output_files/Template2_Submission_Ready.xlsx`: submission-ready Template 2 workbook.
- `generated/guarded_generation_report.xlsx`: demand split, quarantined records and programme completeness.
- `generated/run_summary.xlsx`: scheduling summary, validation checks, run metadata and unscheduled reasons.
- `generated/template2_submission_validation.xlsx`: Template 2 readiness and source-to-output validation.
- `generated/timetable_visualisation_validation.xlsx`: visual workbook reconciliation.
- `output_files/Programme_Timetable_Visuals.xlsx`: programme-year visual timetables.
- `output_files/Tutor_Timetable_Visuals.xlsx`: tutor visual timetables.
- `output_files/Room_Timetable_Visuals.xlsx`: room visual timetables.

## Final Verified Results

Final v1.1 scheduling metrics:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3070
Scheduler search failures: 90
Scheduled hard-constraint violations: 0
Coverage of schedulable demand: 3070 / 3160 = 97.15%
Coverage of total recorded demand: 3070 / 3562 = 86.19%
```

The `86.19%` total-recorded-demand figure includes quarantined source records. The primary scheduling-performance measure is `97.15%` coverage of schedulable demand.

Template 2 evidence:

```text
Proposed timetable rows: 2868
Submission-ready Template 2 rows: 1183
Template 2 invalid rows: 0
Template 2 complete programme-years: 30
Submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

Visual timetable evidence:

```text
Programme visual sheets: 81
Tutor visual sheets: 225
Room visual sheets: 43
Programme visual entries: 3454
Tutor visual entries: 4255
Room visual entries: 2367
Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
Visual export status: PASS
```

Earlier pre-fixed-session v1.0 validation produced `2777` required, `2747` scheduled, `30` unscheduled and `98.92%` baseline coverage. Those values are historical development evidence only, not the final v1.1 result.

## Testing

Run from the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result:

```text
259 passed
```

Run release validation after generating evidence:

```powershell
.\.venv\Scripts\python.exe validate_release.py
```

Expected result:

```text
FINAL RELEASE VALIDATION: PASS
```

## Release ZIP

Build a clean source ZIP from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\build_clean_release.py
```

The ZIP is written to `dist/itp_group5_prototype_v1.1.0.zip` and excludes Git metadata, virtual environments, caches, generated outputs, old ZIP files, editor folders and temporary files.

Generated assessment evidence is packaged separately so source control remains clean.

## Implementation Notes

Workbook-role detection is structure-based. A workbook is accepted or rejected based on worksheets and headers, not filename alone.

The Engineering dataset is stored under `Data/`, including Engineering requirement workbooks, common-module data, venue data, timetable constraints, university-wide modules and the output workbook template.

The heuristic scheduler does not prove global mathematical optimality. It prioritises hard feasibility: scheduled assignments must have zero hard-constraint violations, while unresolved cases remain visible for staff review.

## AI Collaboration

AI-assisted development is documented transparently in [AI_USAGE_LOG.md](AI_USAGE_LOG.md) and [AI_ASSISTANCE_STATEMENT.md](AI_ASSISTANCE_STATEMENT.md). Group 5 defined the problem, requirements, architecture, validation criteria and final decisions. ChatGPT and Codex supported implementation, debugging, automated testing, documentation refinement and code review.
