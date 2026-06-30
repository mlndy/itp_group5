# Optimiser Evidence

The final live Engineering evidence uses the non-optimised command because the optimiser is too slow for a predictable presentation run. Optimiser behaviour was not changed during the finishing-touch work.

Evidence source: `timetable_scheduler/generated/run_summary.xlsx`, sheet `Optimisation Summary`.

## Final Run Summary

| Measure | Before | After | Result |
|---|---:|---:|---|
| Hard violations | 0 | 0 | PASS |
| Soft violations | 4676 | 4676 | No change because optimisation was skipped |
| Weighted soft score | 6824 | 6824 | No change because optimisation was skipped |
| Tutor idle gaps | 103 | 103 | No change because optimisation was skipped |
| Student long-day measure | 69 | 69 | No change because optimisation was skipped |
| Online/F2F transition measure | 246 | 246 | No change because optimisation was skipped |
| Short campus-day measure | 804 | 804 | No change because optimisation was skipped |
| Assignments moved by optimiser | 0 | 0 | Optimisation skipped |
| Fixed assignments moved by optimiser | 0 | 0 | PASS |

## Interpretation

The final release evidence proves that skipping optimisation preserves hard feasibility and final coverage. It does not claim a final-run soft-score improvement.

Historical optimiser evidence in project notes recorded a small improvement on an earlier controlled run, but those values are not the active final Engineering evidence. The defensible final claim is:

- optimisation logic exists and is tested;
- the final release run skips optimisation for demo reliability;
- hard violations remain `0`;
- fixed assignments are not moved.

## Known Limitation

The current final evidence does not include a completed full Engineering optimiser run with before-and-after moved-assignment counts. Those values should not be invented for report or presentation use.
