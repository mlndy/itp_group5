# Assessment Evidence Package

This package contains generated output workbooks from the final v1.1 Engineering Timetable Scheduler validation run.

## Official Timetable Outputs

- `final_timetable_engineering_cluster.xlsx`: proposed Engineering cluster timetable generated from the validated schedule.
- `Template2_Submission_Ready.xlsx`: official submission-ready Template 2 workbook containing only validated rows from complete submission-ready programme-year schedules.

## Supplementary Visual Timetables

- `Programme_Timetable_Visuals.xlsx`: programme-year timetable views for stakeholder review.
- `Tutor_Timetable_Visuals.xlsx`: tutor timetable views for workload and clash review.
- `Room_Timetable_Visuals.xlsx`: room timetable views for venue utilisation review.

The visual workbooks are supplementary. They are generated from validated scheduled assignments and do not alter Template 2.

## Validation Evidence

- `guarded_generation_report.xlsx`: demand split, quarantined records, search failures, programme completeness and guarded-generation readiness.
- `run_summary.xlsx`: scheduling summary, validation checks, run metadata, unscheduled reasons, resource audit and residual analysis.
- `template2_submission_validation.xlsx`: Template 2 field validation, source-to-output reconciliation, programme schedule coverage and readiness status.
- `timetable_visualisation_validation.xlsx`: reconciliation checks confirming that visual workbooks contain expected scheduled entries with no missing entries, unexpected entries or invalid overlaps.

## Final v1.1 Metrics

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

The `86.19%` total-recorded-demand coverage includes quarantined source records. The primary scheduling-performance measure is `97.15%` coverage of schedulable demand.

## Template 2 Metrics

```text
Proposed timetable rows: 2868
Submission-ready Template 2 rows: 1183
Template 2 invalid rows: 0
Template 2 complete programme-years: 30
Submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

## Known Limitations

- The scheduler is heuristic and does not prove global optimality.
- Quarantined records require source-data correction or stakeholder clarification.
- Scheduler search failures remain visible for manual review.
- The prototype supports timetabling staff and does not replace staff judgement or final approval.
