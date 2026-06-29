# Demo Script

## Opening

```text
This prototype supports SIT Engineering timetabling staff by converting consolidated scheduling requirements into a proposed timetable, validating hard constraints, separating unresolved records, and exporting review workbooks.
```

Do not describe the prototype as replacing timetabling staff. Staff remain responsible for exception review and final approval.

## Run Command

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

## Evidence To Point Out

After the run completes, show:

1. `generated/guarded_generation_report.xlsx`
2. `generated/run_summary.xlsx`
3. `generated/template2_submission_validation.xlsx`
4. `generated/timetable_visualisation_validation.xlsx`
5. `output_files/Template2_Submission_Ready.xlsx`
6. `output_files/Programme_Timetable_Visuals.xlsx`
7. `output_files/Tutor_Timetable_Visuals.xlsx`
8. `output_files/Room_Timetable_Visuals.xlsx`

## Suggested Narration

```text
The current run contains 3562 recorded teaching occurrences. Of these, 3323 are schedulable after input validation and 239 are quarantined for staff review. The scheduler places 3214 schedulable occurrences, leaving 109 search failures visible rather than forcing invalid allocations.
```

```text
The main safety result is that scheduled hard-constraint violations remain zero. The scheduling-performance coverage is 3214 out of 3323 schedulable occurrences, or 96.72%.
```

```text
The lower 90.23% total-recorded-demand figure includes quarantined source records. We report it for transparency, but it is not the algorithm success rate.
```

## Template 2 Segment

Point out:

- proposed timetable rows: `3006`;
- all-valid scheduled Template 2 rows: `2817`;
- submission-ready Template 2 rows: `212`;
- invalid Template 2 rows: `0`;
- qualifying submission-ready programme-years: `23`;
- minimum required programme-year schedules: `20`;
- Template 2 readiness: `PASS`.

Suggested narration:

```text
The submission-ready Template 2 workbook is stricter than the proposed timetable. The current completeness gate is release-ready because 23 programme-years qualify against the required 20; unresolved demand remains in exception reports instead of being hidden.
```

## Visual Timetable Segment

Open the visual workbooks:

1. `Programme_Timetable_Visuals.xlsx`
2. `Tutor_Timetable_Visuals.xlsx`
3. `Room_Timetable_Visuals.xlsx`

Suggested narration:

```text
The visual workbooks are generated from the validated scheduled assignments. They do not run a second scheduler and they do not change Template 2. They simply make the same timetable easier to inspect by programme-year, tutor and room.
```

Point out:

- incomplete programme-years have warning banners;
- fixed sessions use a stronger border;
- online and external sessions have distinct labels;
- every block contains a traceable assignment ID;
- validation reports `Visual export status: PASS`;
- missing visual entries, unexpected entries and invalid overlaps are all `0`.

## Closing

```text
The prototype demonstrates the potential to reduce manual placement, checking, formatting and reporting effort while keeping exceptional and policy-based decisions under staff control.
```
