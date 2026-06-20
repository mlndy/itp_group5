# Final Results

## Dataset

The final validated scope is the SIT Engineering Cluster, including DSC.

- Engineering requirements workbooks recognised: `35`
- Input course records: `507`
- Consolidated scheduling requirements: `465`
- Required teaching occurrences: `2777`
- Supporting data: common modules, venue information, timetable constraints, university-wide modules and the proposed-timetable output template

Teaching occurrences are the stable reporting denominator. They are used instead of raw assignment-object counts because one unscheduled placeholder can represent several missing weeks, while scheduled assignments are week-level occurrences.

## Core Baseline Result

The core baseline disables remarks enforcement and confirms the restored structured scheduling behaviour.

```text
Required teaching occurrences: 2777
Scheduled teaching occurrences: 2747
Unscheduled teaching occurrences: 30
Coverage: 98.92%
Scheduled hard violations: 0
Online scheduled: 813 / 813
```

The baseline does not claim that every Engineering occurrence is scheduled. It schedules only hard-feasible occurrences and leaves remaining demand visible.

## Remarks-Aware Result

The remarks-aware enhanced run enables deterministic interpretation of supported free-text scheduling remarks.

```text
Required teaching occurrences: 2777
Scheduled teaching occurrences: 2715
Unscheduled teaching occurrences: 62
Coverage: 97.77%
Scheduled hard violations: 0
```

The enhanced run has lower coverage because it enforces additional explicit supported requirements from remarks. It does not reduce unscheduled demand by accepting hard violations.

## Attribution

Occurrence-level attribution for the remarks-aware comparison:

```text
30 unchanged unscheduled
13 direct explicit remark effects
19 indirect displacements
0 recoveries
0 unexplained
```

This reconciles the enhanced result against the baseline. No enhanced-only unscheduled occurrence is left unexplained.

## Remarks Handling

Course-level handling counts:

```text
Total non-empty remarks: 226
Applied automatically: 5
Preferences considered: 4
Scheduled needing confirmation: 95
Unscheduled due to explicit request: 5
Unsupported non-blocking: 105
No scheduling action required: 12
```

These course-level handling counts are different from occurrence-level scheduling attribution. A single course-level remark can affect multiple teaching occurrences, and some remarks are review notes rather than scheduling blockers.

## Shared Online Delivery-Resource Policy

`ONLINE_ROOM` is a synthetic delivery-mode placeholder, not a scarce physical venue. Fully online classes may share it when they do not share tutors or student groups.

This policy does not weaken hard constraints. Tutor clashes, student-group clashes, calendar rules, duration rules, teaching-week rules and physical room clashes remain enforced.

Validated online baseline result:

```text
Online required: 813
Online scheduled: 813
Online unscheduled: 0
```

## Remaining Operational Exceptions

The baseline leaves `30` F2F teaching occurrences unscheduled. The remaining demand is mainly associated with very large common-module F2F requirements affected by physical-room capacity.

These are operational exceptions. Appropriate next actions include:

- reviewing large-room availability;
- approving an alternate delivery mode where policy allows;
- splitting very large sessions where academically valid;
- manually reviewing affected programme timetables;
- confirming any source-data assumptions with stakeholders.

## Optimiser Evidence

The controlled optimiser run preserved teaching demand, coverage, online coverage and hard feasibility.

```text
Baseline soft violations: 3030
Optimised soft violations: 3019
Improvement: 11
Runtime: approximately 1047 seconds
```

The optimiser is useful as evidence, but it should not be overstated and is too slow for a live presentation run.

## Testing

Final expected test result:

```text
220 passed
```

If this count changes after final cleanup tests are added, the newer full-suite result should be recorded before submission.

## Release Validation

Expected final validation result after generating the final remarks-aware Engineering evidence:

```text
FINAL RELEASE VALIDATION: PASS
```

Release validation checks the generated evidence workbooks without regenerating the timetable.

## Exact Validation Commands

Run tests:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
..\.venv\Scripts\python.exe -m pytest -q
```

Core baseline command:

```powershell
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics --disable-remark-interpretation
```

Remarks-aware final command:

```powershell
..\.venv\Scripts\python.exe main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Release validation:

```powershell
..\.venv\Scripts\python.exe validate_release.py
```

## Known Limitations

- The scheduler is heuristic and does not prove global optimality.
- Remaining F2F demand needs operational review.
- Recording capability is used as the available proxy for hybrid support.
- Ambiguous free-text remarks are not guessed; they remain visible for review.
- Scenario comparison and internal-system upload are outside the prototype scope.
- Generated Excel workbooks are local artefacts and remain ignored by Git.
