# Presentation Evidence

## Core Evidence Slide

Use these as the current scheduling-safety headline figures:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3046
Scheduler search failures: 114
Scheduled hard-constraint violations: 0
Coverage of schedulable demand: 96.39%
Coverage of total recorded demand: 85.51%
```

Speaking note:

```text
The scheduler placed 96.39% of schedulable teaching demand while keeping scheduled hard-constraint violations at zero. The lower 85.51% total-recorded-demand figure includes source records quarantined for staff review, so it is not the algorithm success rate.
```

## Template 2 Readiness Slide

```text
Proposed timetable rows: 2838
All-valid scheduled Template 2 rows: 2817
Submission-ready Template 2 rows: 111
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 17
Minimum required programme-year schedules: 20
Template 2 readiness: FAIL
```

Key framing:

- The proposed timetable contains valid scheduled rows for review.
- The submission-ready workbook is stricter and excludes incomplete or unresolved programme-years.
- Unresolved demand remains visible in reports rather than being hidden in Template 2.
- The current completeness gate is not release-ready because `17` qualifying programme-years is below the required `20`.

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
Programme visual sheets: 80
Tutor visual sheets: 221
Room visual sheets: 43
Programme visual entries: 608
Tutor visual entries: 554
Room visual entries: 471
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
