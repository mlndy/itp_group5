# Live Demo Script

## Cross-Check Note

This checkout does not contain `FINAL_RESULTS.md` or `RELEASE_CHECKLIST.md`, and `DEMO.md` currently contains an older Engineering final command that omits `--audit-demand-metrics`. The script below follows the verified live-demo command supplied in the report-phase task prompt.

## Demo Length

Target duration: 5 to 7 minutes.

Use the non-optimised Engineering command for the live demo. The optimiser evidence is pre-generated because the controlled five-iteration optimiser run took approximately `1047` seconds.

## 1. Opening Explanation

Suggested wording:

> This prototype solves an Engineering cluster timetabling problem, including DSC. The key principle is that hard constraints are never weakened. If a class cannot be placed safely, the system reports it as unscheduled instead of forcing an invalid timetable entry.

Point out:

- This is an operations resource-allocation problem.
- Rooms, tutors, student groups, teaching weeks, and delivery modes all constrain the schedule.
- The final result is partial but hard-feasible.

## 2. Input Folder

Show:

```text
timetable_scheduler/input/Requirements_ENG/
```

Explain:

> This folder contains the Engineering requirement workbooks. Engineering scope includes DSC where present in the Engineering input folder.

Optional source reference:

- `timetable_scheduler/main.py::load_courses`
- `timetable_scheduler/data/loader.py::load_courses_from_folder`

## 3. Command to Run

Run from `timetable_scheduler`:

```powershell
py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

If `py` is unavailable in the local shell, use the installed Python executable and keep the same arguments.

## 4. Console Metrics to Point Out

Point out these expected figures:

- Input course records: `507`
- Consolidated scheduling requirements: `465`
- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`

Suggested wording:

> The main feasibility result is not raw scheduled row count. We use teaching occurrences as the stable denominator. The system schedules 2747 of 2777 occurrences and keeps scheduled hard violations at zero.

## 5. Generated Timetable Output

Open:

```text
timetable_scheduler/output_files/final_timetable_engineering_cluster.xlsx
```

Point out:

- This is the Template 2-compatible timetable output.
- F2F assignments show physical room IDs.
- Online assignments use `ONLINE_ROOM`.
- Unscheduled rows remain identifiable and are not counted as successful scheduled classes.

## 6. Summary Sheet

Open:

```text
timetable_scheduler/generated/run_summary.xlsx
```

Show the Summary sheet.

Point out:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Hard violations on scheduled assignments: `0`

Suggested wording:

> This is the headline evidence page. It shows that the system is feasible where it schedules classes, and transparent about the 30 teaching occurrences that remain unresolved.

## 7. Validation Checks

Show the Validation Checks sheet.

Point out:

- Demand consistency: `PASS`
- Hard-constraint safety: `PASS`
- DSC inclusion: `PASS`
- Unscheduled visibility: `PASS`

Suggested wording:

> Validation Checks is the presentation evidence page. It confirms the result is numerically consistent and that scheduled assignments have zero hard violations.

## 8. Programme Breakdown Showing DSC

Show the Programme Breakdown sheet.

Point out:

- `DSC Indicator` column.
- DSC rows marked `Yes`.

Suggested wording:

> This proves the Engineering run includes DSC. DSC is not only tested separately; it appears inside the Engineering cluster evidence.

## 9. Resource Audit

Show Resource Audit if available in the generated final workbook.

Point out:

- Online required occurrences: `813`
- Online scheduled occurrences: `813`
- Online unscheduled occurrences: `0`
- Virtual room policy: shared delivery placeholder.

Exact wording for online semantics:

> `ONLINE_ROOM` is not a physical venue. It is a synthetic placeholder for fully online teaching. Multiple unrelated online classes may share it because they do not compete for a physical room.

Exact wording for why this remains safe:

> Sharing `ONLINE_ROOM` does not permit tutor clashes or student-group clashes. Those constraints still apply. Calendar, duration, teaching-week, and physical room rules also still apply.

## 10. Residual F2F Analysis

Show Residual F2F Analysis if available in the generated final workbook.

Point out:

- Remaining unscheduled demand is F2F.
- Main issue is large `ENG1001` common-module requirements.
- The issue is physical-room capacity pressure, not hidden scheduling success.

Exact wording:

> The 30 remaining teaching occurrences are not hidden. They are F2F operational exceptions, mainly very large ENG1001 common-module sessions. The correct next step is an operational decision: add suitable venue capacity, approve another delivery mode, split sessions if policy allows, or manually review the programme timetable.

## 11. Release Validation

Run if available in the final release branch:

```powershell
py validate_release.py
```

Expected:

```text
FINAL RELEASE VALIDATION: PASS
```

If the release validator file is not present in this checkout, say:

> This checkout does not include the release validator file, but the final release evidence expects it to validate the generated workbooks without regenerating the timetable.

## 12. Optimiser Evidence

Do not run the optimiser live.

Show Optimisation Summary from the pre-generated workbook if available.

Point out:

- Initial soft violations: `3030`
- Final soft violations: `3019`
- Improvement: `11`
- Runtime: approximately `1047` seconds
- Coverage and hard safety preserved.

Exact wording:

> The optimiser is shown as pre-generated evidence because the controlled run takes about 17 minutes. It improved soft violations by 11 while preserving required occurrences, scheduled coverage, online coverage, and zero scheduled hard violations.

Do not describe the optimiser improvement as large.

## 13. Fallback Plan

If the live run is slow:

1. Stop waiting for the command after explaining that Engineering scheduling is computationally heavier than DSC.
2. Open the pre-generated `run_summary.xlsx`.
3. Open the pre-generated `final_timetable_engineering_cluster.xlsx`.
4. Walk through Summary, Validation Checks, Programme Breakdown, Resource Audit, Residual F2F Analysis, and Optimisation Summary.
5. Explain that generated files are not committed to Git but are copied into the submission package.

Suggested wording:

> The live run is useful for showing repeatability, but the final evidence is in the generated workbooks. If the run takes longer than the demo window, we use the pre-generated validated artefacts.

## Closing

Suggested wording:

> The prototype provides a hard-constraint-safe Engineering timetable including DSC. It schedules 2747 of 2777 required teaching occurrences, fully schedules online demand, keeps scheduled hard violations at zero, and transparently reports the remaining 30 F2F occurrences for operational decision-making.
