# Demo Guide

## Local Setup

Run from Windows PowerShell at the repository root:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Test Command

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result:

```text
314 passed
```

## Engineering Demo Command

Run from Windows PowerShell:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

## Expected Engineering Result

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3323
Quarantined input occurrences: 239
Scheduled occurrences: 3214
Scheduler search failures: 109
Scheduled hard-constraint violations: 0
Coverage of schedulable demand: 96.72%
Coverage of total recorded demand: 90.23%
```

The main feasibility success metric is `0` scheduled hard-constraint violations. The primary scheduling-performance metric is `96.72%` coverage of schedulable demand.

The `90.23%` total-recorded-demand figure includes quarantined input records. Those records are deliberately reported for staff review and are not hidden as scheduled classes.

## Template 2 Evidence

```text
Proposed timetable rows: 3006
All-valid scheduled Template 2 rows: 2980
Submission-ready Template 2 rows: 212
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

The saved submission-ready workbook is intentionally strict. This branch demonstrates safe scheduling and evidence reporting, and it is release-ready because `23` programme-years meet the full completeness gate.

Open:

- `timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx`
- `timetable_scheduler/output_files/Template2_All_Valid_Scheduled_Rows.xlsx`
- `timetable_scheduler/output_files/Template2_Submission_Ready.xlsx`
- `timetable_scheduler/generated/template2_submission_validation.xlsx`
- `timetable_scheduler/generated/template2_programme_year_reconciliation.xlsx`
- `timetable_scheduler/generated/template2_exclusion_audit.xlsx`

## Visual Timetable Outputs

The scheduler automatically exports calendar-style programme, tutor and room timetable views from the validated scheduled assignments.

These are supplementary operational outputs:

- `timetable_scheduler/output_files/Programme_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Tutor_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Room_Timetable_Visuals.xlsx`
- `timetable_scheduler/generated/timetable_visualisation_validation.xlsx`

Expected visual evidence:

```text
Programme visual sheets: 86
Tutor visual sheets: 235
Room visual sheets: 48
Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
Visual export status: PASS
```

## How To Read The Engineering Result

- Scheduled hard-constraint violations = `0` is the main feasibility success metric.
- Unscheduled assignments and quarantined records are intentionally reported, not hidden.
- Quarantined input occurrences are source records that need clarification or correction before scheduling.
- Scheduler search failures are schedulable occurrences the heuristic could not place within the configured search.
- Programme, tutor and room visual workbooks are review views, not separate schedules.
- `Validation Checks`, `guarded_generation_report.xlsx`, `template2_submission_validation.xlsx` and `timetable_visualisation_validation.xlsx` are the evidence pages for report and presentation use.

## Troubleshooting

- Activate or call the project virtual environment before running commands.
- Run pytest from the repository root for final validation.
- Generated folders such as `timetable_scheduler/generated/`, `timetable_scheduler/output_files/` and `dist/` should not be committed.
- If `validate_release.py` fails, rerun the Engineering demo command first so local generated evidence is fresh.
