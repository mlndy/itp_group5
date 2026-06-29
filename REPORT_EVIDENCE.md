# Report Evidence

## Current Completeness-Gate Evidence

The current evidence is produced by the Engineering guarded-generation run. It validates scheduling safety, fixed-session handling and stakeholder visual timetable exports, but the stricter Template 2 completeness gate is blocked.

Final scheduling evidence:

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

The report should use `96.39%` as the scheduling-performance coverage because it measures scheduled occurrences against schedulable demand. The `85.51%` total-recorded-demand figure includes quarantined input records and should be explained as an input-quality and readiness measure.

## Template 2 Evidence

```text
Proposed timetable rows: 2838
All-valid scheduled Template 2 rows: 2817
Submission-ready Template 2 rows: 111
Template 2 invalid rows: 0
Qualifying submission-ready programme-years: 17
Minimum required programme-year schedules: 20
Template 2 readiness: FAIL
```

The readiness failure is intentional evidence: unresolved demand is reported rather than hidden or forced into the upload workbook.

Evidence workbooks:

- `timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx`
- `timetable_scheduler/output_files/Template2_All_Valid_Scheduled_Rows.xlsx`
- `timetable_scheduler/output_files/Template2_Submission_Ready.xlsx`
- `timetable_scheduler/generated/template2_submission_validation.xlsx`
- `timetable_scheduler/generated/template2_programme_year_reconciliation.xlsx`
- `timetable_scheduler/generated/template2_exclusion_audit.xlsx`
- `timetable_scheduler/generated/guarded_generation_report.xlsx`

## Visual Timetable Evidence

The scheduler exports calendar-style programme, tutor and room views from validated scheduled assignments. This is an output feature only; it does not reinterpret requirements, rerun the scheduler, change fixed-session handling or modify Template 2.

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

Evidence workbooks:

- `timetable_scheduler/output_files/Programme_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Tutor_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Room_Timetable_Visuals.xlsx`
- `timetable_scheduler/generated/timetable_visualisation_validation.xlsx`

Visual entries exceed proposed timetable rows because one scheduled assignment may appear in multiple stakeholder views.

## Final Validation Record

The Template 2 all-years hotfix branch was tested with a regenerated guarded Engineering run. The direct saved-workbook audit produced these headline metrics:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3046
Scheduler search failures: 114
Scheduled hard-constraint violations: 0
Submission-ready Template 2 rows: 111
Qualifying submission-ready programme-years: 17
Template 2 readiness: FAIL
Visual export status: PASS
```

Generated artefact hashes from the earlier all-years hotfix validation run are historical and must be regenerated before release because the completeness gate changed the strict Template 2 readiness result:

| Artefact | SHA-256 |
| --- | --- |
| `run_summary.xlsx` | `a5697ea2acce89090c08a4b207ab0d0943229d9f34c429cead8f01e4c0447bbf` |
| `guarded_generation_report.xlsx` | `0a106695c3557f4efef8b6886c7e642d78f15396b6a03cf18aefa8559078eac6` |
| `template2_submission_validation.xlsx` | `1f2f0d1c84ccce2726278489740c4e785722c535a66d30864b359876d0acc35f` |
| `template2_programme_year_reconciliation.xlsx` | `cc99ab096d6bad7564481ede7becb3bb9502bd2eec358e46e97790f5d9b66dfd` |
| `template2_exclusion_audit.xlsx` | `63ced983aa70166b388e42c6725d4737b359d320896deec0b96c90bb7f9baa5d` |
| `timetable_visualisation_validation.xlsx` | `ffa07edfe820830fefa33f73609477af7cb15b5283320b987d1213bd6b5f2498` |
| `run_manifest.xlsx` | `525af6c4ef738a4a16bb45e69bef3870ad1223b0b3a080a4e0e6a9817ac2f21a` |
| `final_timetable_engineering_cluster.xlsx` | `b83ec0c1f9d3d9b35a9462e2610d29bca215fe2dd72dffd7cf670382c6e1eefc` |
| `Template2_Submission_Ready.xlsx` | `193a765d959a1be5890cf68eea74bf59e4c3431808eefda54bc81a9aa8512078` |
| `Template2_All_Valid_Scheduled_Rows.xlsx` | `c1ee159d885ea144723c2c54610c43d60754deb096ec79b5bbbba9dd9b9fbb2f` |
| `Programme_Timetable_Visuals.xlsx` | `376a1ebf91d3800eb342285e7f6310be3eeac9ddc1b1e711f282f51d6f8de057` |
| `Tutor_Timetable_Visuals.xlsx` | `dfaf4fafa4aa8238a86cf04dbb2f5a80a30bae768b643526d2472a21154b1eeb` |
| `Room_Timetable_Visuals.xlsx` | `e1ccdd6e6502d6a05eb96effcdfa0206fa262789775b00aaec6b97e270b35310` |

## Project Narrative For Report

The prototype is intended to improve the quality of life of timetabling staff by automating repetitive placement, checking, formatting and reporting work while keeping staff in control of exceptions and final approval.

Do not claim global optimality or exact time savings. The results demonstrate the potential to reduce manual effort, but no formal timing study was performed.

## Historical Evidence

Earlier pre-fixed-session v1.0 validation produced `2777` required occurrences, `2747` scheduled occurrences, `30` unscheduled occurrences and `98.92%` baseline coverage. These values should be labelled as historical development evidence, not the final v1.1 result.
