# Demo Guide

## Engineering Demo Command

Run from Windows PowerShell:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

## Visual Timetable Outputs

The scheduler automatically exports calendar-style programme, tutor and room timetable views from the validated scheduled assignments.

These are supplementary operational outputs:

- `timetable_scheduler/output_files/Programme_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Tutor_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Room_Timetable_Visuals.xlsx`
- `timetable_scheduler/generated/timetable_visualisation_validation.xlsx`

The visual workbooks do not create or change the timetable. They display only valid scheduled assignments. Quarantined and unscheduled requirements remain visible in the exception and guarded-generation reports.

## Expected Evidence

```text
Scheduled hard violations: 0
Template 2 readiness: PASS
Visual export status: PASS
Programme visual sheets: 81
Tutor visual sheets: 225
Room visual sheets: 43
Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
```

Use the visual files to demonstrate how the same validated timetable can be reviewed by programme/year, tutor and room without altering the official proposed timetable workbook.
