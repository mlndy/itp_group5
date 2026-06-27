# Report Evidence

## Final System Evidence

The final v1.1 evidence is produced by the Engineering guarded-generation run. It validates scheduling safety, fixed-session handling, Template 2 readiness and stakeholder visual timetable exports.

Final scheduling evidence:

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

The report should use `97.15%` as the scheduling-performance coverage because it measures scheduled occurrences against schedulable demand. The `86.19%` total-recorded-demand figure includes quarantined input records and should be explained as an input-quality and readiness measure.

## Template 2 Evidence

```text
Proposed timetable rows: 2868
Submission-ready Template 2 rows: 1183
Template 2 invalid rows: 0
Template 2 complete programme-years: 30
Submission-ready programme-years: 23
Minimum required programme-year schedules: 20
Template 2 readiness: PASS
```

Evidence workbooks:

- `timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx`
- `timetable_scheduler/output_files/Template2_Submission_Ready.xlsx`
- `timetable_scheduler/generated/template2_submission_validation.xlsx`
- `timetable_scheduler/generated/guarded_generation_report.xlsx`

## Visual Timetable Evidence

The scheduler exports calendar-style programme, tutor and room views from validated scheduled assignments. This is an output feature only; it does not reinterpret requirements, rerun the scheduler, change fixed-session handling or modify Template 2.

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

Evidence workbooks:

- `timetable_scheduler/output_files/Programme_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Tutor_Timetable_Visuals.xlsx`
- `timetable_scheduler/output_files/Room_Timetable_Visuals.xlsx`
- `timetable_scheduler/generated/timetable_visualisation_validation.xlsx`

Visual entries exceed proposed timetable rows because one scheduled assignment may appear in multiple stakeholder views.

## Final Validation Record

The final integration branch was tested with two consecutive guarded Engineering runs. Both runs produced the same headline metrics:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3160
Quarantined input occurrences: 402
Scheduled occurrences: 3070
Scheduler search failures: 90
Scheduled hard-constraint violations: 0
Submission-ready Template 2 rows: 1183
Submission-ready programme-years: 23
Template 2 readiness: PASS
Visual export status: PASS
```

Final generated artefact hashes from the second validation run:

| Artefact | SHA-256 | Timestamp/order-insensitive content fingerprint |
| --- | --- | --- |
| `run_summary.xlsx` | `beddbdc5791e4e10d8075a3870b60cc1fa408c38fcd237af04cfeafb00bdf715` | `5eb61a92bff98fe46fd7664a06aebcb62832382d71b19a3b7787a2a9dfb51a98` |
| `guarded_generation_report.xlsx` | `cc6001538f2205c944121dcae4f8fd3f47e6fea6d932c1f9b1820a75faf71916` | `44d891d012268c255ae1470f710bd71e530d40ab4c784dc256b81e5fcbff877b` |
| `template2_submission_validation.xlsx` | `1de1eb8a9aca7eb44c330e3d0ab82a48c4960b0ce7cfd73cd7f0cf678e1bc582` | `8ab3201c8593f17777e1a5e2ba1bfcc2890ad83df3bf2bcf42745742fa486558` |
| `timetable_visualisation_validation.xlsx` | `104c5534b1c79a8752d85f704f8ece07fba4d5f166becd7ffacb4c87572521c1` | `9f708c9d1822f1e7a72c4f0bf74fab91be9ff6445700dd17d4c51028c84885d1` |
| `run_manifest.xlsx` | `4416b1277ecab400bc7194ff49d0426900366f3d1cc5c8fd6c5120a733b7522f` | `6fdbccb84e978ae26e72325945115694b36322f6837200b916fa053721195345` |
| `final_timetable_engineering_cluster.xlsx` | `dd6e9eaac0c087f9f2ff0189eccc1e50d14c20276148e349b4ba9f1fa9c74de8` | `d04a85988be6cc4cdba733ed1098c771338661370742feec367ff5bca191d731` |
| `Template2_Submission_Ready.xlsx` | `d9ee4e01c69435ba0b967087b8495d9ac005c236955646eb0f6c06b92a418a66` | `c2edd4a8ecc4a92367cde0d973aba772964214a2899fe75c72033406b160df9d` |
| `Programme_Timetable_Visuals.xlsx` | `22d853467ee994eb7744b983cc579c7e7b8d4caace3083b8997ce7a0d9ab910d` | `5a9236176cdd5c2c345eeba487a053454ef3d45602df5e8b2a8a9ae15daf2fd6` |
| `Tutor_Timetable_Visuals.xlsx` | `f9f35669c24c67499af50f16dfe4d50b180c7c21fab7f954d520c26884097471` | `17895b58927f6fd1a4335bf4d69e88cb9fd2e66df80f99e08a97a42252863464` |
| `Room_Timetable_Visuals.xlsx` | `cc968f37b39fc050a98b1bb62fac5ba347eadf3f45bf03c85b47717b83bb8c35` | `bb92f33db498987ee522f4620061c2d8e928e14ec2d1c954637cd8c8a6db3ab2` |

## Project Narrative For Report

The prototype is intended to improve the quality of life of timetabling staff by automating repetitive placement, checking, formatting and reporting work while keeping staff in control of exceptions and final approval.

Do not claim global optimality or exact time savings. The results demonstrate the potential to reduce manual effort, but no formal timing study was performed.

## Historical Evidence

Earlier pre-fixed-session v1.0 validation produced `2777` required occurrences, `2747` scheduled occurrences, `30` unscheduled occurrences and `98.92%` baseline coverage. These values should be labelled as historical development evidence, not the final v1.1 result.
