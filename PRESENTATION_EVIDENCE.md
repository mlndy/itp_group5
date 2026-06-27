# Presentation Evidence

## Core Evidence Slide

Use these as the final v1.1 headline figures:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3070
Scheduler search failures: 90
Scheduled hard-constraint violations: 0
Coverage of schedulable demand: 97.15%
Coverage of total recorded demand: 86.19%
```

Speaking note:

```text
The scheduler placed 97.15% of schedulable teaching demand while keeping scheduled hard-constraint violations at zero. The lower 86.19% total-recorded-demand figure includes source records quarantined for staff review, so it is not the algorithm success rate.
```

## Template 2 Readiness Slide

```text
Proposed timetable rows: 2868
Submission-ready Template 2 rows: 1183
Template 2 invalid rows: 0
Template 2 complete programme-years: 30
Submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

Key framing:

- The proposed timetable contains valid scheduled rows for review.
- The submission-ready workbook is stricter and excludes incomplete or unresolved programme-years.
- Unresolved demand remains visible in reports rather than being hidden in Template 2.

## Visual Timetable Workbooks

The prototype creates three operational visual workbooks after a successful Engineering run:

- `Programme_Timetable_Visuals.xlsx`
- `Tutor_Timetable_Visuals.xlsx`
- `Room_Timetable_Visuals.xlsx`

Presentation framing:

```text
The timetable is generated once, validated for hard constraints, and then exported into multiple review formats. The visual workbooks make the validated schedule easier to read; they do not change the timetable.
```

## Final Visual Counts

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

## Human-Control Message

Use this line in the presentation:

```text
The system supports timetabling staff by automating repetitive placement, checking, formatting and reporting work while leaving exceptions and final approval under staff control.
```

Avoid claims that the prototype replaces staff, proves global mathematical optimality or reduces workload by a specific measured percentage.
