# Final Results

## Final Scope

The final validated scope is the SIT Engineering Cluster, including DSC. The prototype operates between consolidated scheduling requirements and the proposed Template 2 timetable output used by timetabling staff for review and upload preparation.

The current completeness-gate branch also includes guarded fixed-session handling and programme, tutor and room visual timetable exports.

## Current Completeness-Gate Scheduling Metrics

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3323
Quarantined input occurrences: 239
Scheduled occurrences: 3214
Scheduler search failures: 109
Scheduled hard-constraint violations: 0
```

Coverage of schedulable demand:

```text
3214 / 3323 = 96.72%
```

Coverage of total recorded demand:

```text
3214 / 3562 = 90.23%
```

The `90.23%` total-demand coverage includes source records that were quarantined because they were incomplete, ambiguous or conflicting. It should not be presented as the scheduler's algorithmic success rate. The primary scheduling-performance measure is `96.72%` coverage of schedulable demand.

Quarantined input records are not hidden and are not counted as algorithm search failures. They remain in generated evidence for staff review.

## Output Metrics

```text
Proposed timetable rows: 3006
All-valid scheduled Template 2 rows: 2980
Submission-ready Template 2 rows: 212
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

`Qualifying submission-ready programme-years` is the strict completeness-gate count from the actual saved `Template2_Submission_Ready.xlsx` Timetable sheet after excluding programme-years with quarantined demand, search failures, invalid rows or ambiguous identity. This branch is release-ready because `23` meets the required minimum of `20`.

## Visualisation Metrics

```text
Programme visual sheets: 86
Tutor visual sheets: 235
Room visual sheets: 48

Programme visual entries: 680
Tutor visual entries: 616
Room visual entries: 535

Missing visual entries: 0
Unexpected visual entries: 0
Invalid overlaps: 0
Visual export status: PASS
```

Visual entries exceed proposed timetable rows because the same scheduled assignment can appear in multiple stakeholder views. For example, a shared class may appear in each affected programme view while still remaining one scheduled assignment.

## Evidence Workbooks

The final metrics are validated through local generated evidence:

- `timetable_scheduler/generated/run_summary.xlsx`
- `timetable_scheduler/generated/guarded_generation_report.xlsx`
- `timetable_scheduler/generated/template2_submission_validation.xlsx`
- `timetable_scheduler/generated/template2_programme_year_reconciliation.xlsx`
- `timetable_scheduler/generated/template2_exclusion_audit.xlsx`
- `timetable_scheduler/generated/timetable_visualisation_validation.xlsx`
- `timetable_scheduler/generated/run_manifest.xlsx`
- `timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx`
- `timetable_scheduler/output_files/Template2_All_Valid_Scheduled_Rows.xlsx`
- `timetable_scheduler/output_files/Template2_Submission_Ready.xlsx`
- `timetable_scheduler/output_files/Programme_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Tutor_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Room_Timetable_Visuals.xlsx`

Generated workbooks remain ignored by Git and are packaged separately for assessment evidence.

## Earlier v1.0 Historical Evidence

Earlier pre-fixed-session v1.0 validation produced:

```text
2777 required
2747 scheduled
30 unscheduled
98.92% baseline coverage
```

Those figures are historical development evidence only. They are not the final v1.1 project result because the final system includes fixed-session reconciliation, guarded quarantining and visual timetable exports.

## Optimiser Evidence

The controlled optimiser evidence from the earlier stable release phase remains useful for showing soft-preference improvement:

```text
Baseline soft violations: 3030
Optimised soft violations: 3019
Improvement: 11
Runtime: approximately 1047 seconds
```

The live demonstration should use the non-optimised Engineering command because the optimiser runtime is too long for a presentation window.

## Testing And Release Validation

Current expected test result:

```text
314 passed
```

Release validation result after generating completeness-gate Engineering evidence:

```text
FINAL RELEASE VALIDATION: PASS
```

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe validate_release.py
```

## Known Limitations

- The scheduler is heuristic and does not prove global mathematical optimality.
- The prototype supports timetabling staff; it does not replace staff judgement or final approval.
- Quarantined records require data correction or stakeholder clarification.
- Scheduler search failures remain visible for operational review.
- No exact staff time-savings claim is made because no formal timing study was performed.
- Generated Excel workbooks are local artefacts and remain ignored by Git.
