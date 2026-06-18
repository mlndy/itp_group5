# Final Results

## 1. Final Engineering Result

The final deliverable is the Engineering cluster timetable, including DSC.

- Input course records: `507`
- Consolidated requirements: `465`
- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`

The prototype does not claim that all classes were scheduled. It schedules only hard-feasible assignments and leaves unresolved demand visible.

## 2. Stable Teaching-Demand Denominator

The stable denominator is `2777` required teaching occurrences. This is calculated from consolidated course requirements, not from raw output row counts.

This matters because scheduled rows and unscheduled placeholders can represent different units. Final comparisons should use teaching occurrences:

```text
required teaching occurrences = scheduled teaching occurrences + unscheduled teaching occurrences
2777 = 2747 + 30
```

## 3. DSC Inclusion Evidence

Engineering scope includes DSC input data. The `Programme Breakdown` sheet in `generated/run_summary.xlsx` contains DSC rows and a `DSC Indicator` column.

The `Validation Checks` sheet reports DSC inclusion as `PASS`.

## 4. Shared Online Delivery-Resource Policy

`ONLINE_ROOM` is a synthetic delivery-mode placeholder created by the loader. It is not one of the raw physical venue rows.

Fully online teaching does not require physical venue allocation. Multiple unrelated online classes may share `ONLINE_ROOM` concurrently, while tutor clashes, student-group clashes, calendar rules, duration rules, teaching-week rules, and physical room clashes remain hard constraints.

Online result:

- Online required: `813`
- Online scheduled: `813`
- Online unscheduled: `0`

## 5. Remaining F2F Operational Exceptions

The remaining `30` unscheduled teaching occurrences are F2F. They are primarily caused by physical-room capacity pressure for very large `ENG1001` common-module requirements with enrolments of approximately `1035` and `1110`.

These should be treated as operational exceptions unless the source requirements support another delivery arrangement.

Possible operational responses:

- Additional large physical-room availability
- Approved online or hybrid delivery for very large common-module sessions
- Programme-level timetable review
- Revised common-module grouping or enrolment assumptions
- Manual exception handling for affected weeks

## 6. Optimiser Result

The controlled optimiser run preserved teaching demand, coverage, online coverage, and hard feasibility.

- Baseline soft violations: `3030`
- Optimised soft violations: `3019`
- Optimiser improvement: `11`
- Optimiser runtime: approximately `1047` seconds

The optimiser is useful as pre-generated evidence. The non-optimised Engineering command is recommended for the live presentation because the optimiser runtime is too long for a live demo.

## 7. Test Result

Final test result:

```text
104 passed
```

## 8. Exact Commands Used

Run tests:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Recommended live Engineering demo:

```powershell
py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Controlled optimiser evidence run:

```powershell
py main.py --scope eng --max-iterations 5 --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Release validation:

```powershell
py validate_release.py
```

## 9. Known Limitations

- The prototype does not schedule every F2F occurrence because hard constraints are not weakened.
- Very large common-module F2F sessions exceed available physical-room capacity in the loaded room data.
- The optimiser run is intentionally controlled and can take approximately 17 minutes for five iterations.
- The system does not perform scenario comparison or what-if analysis.
- Generated Excel workbooks are local artefacts and remain ignored by Git.

## 10. Suggested Operational Improvements

- Review large common-module delivery policies.
- Confirm whether very large common-module sessions should be online, hybrid, split, or assigned to external venues.
- Add or identify suitable large physical venues if F2F delivery is mandatory.
- Review source data rows skipped by the loader report.
- Use `preflight_report.xlsx`, `run_summary.xlsx`, and `Residual F2F Analysis` as the decision trail for final stakeholder review.
