# Timetabling System Demo

## Demo Goal

Show a local desktop prototype that generates a hard-feasible Engineering Cluster timetable, including DSC, from one consolidated scheduling workbook. The key message is feasibility and transparency: scheduled classes have zero hard conflicts, and unresolved classes remain visible for review.

## Preparation

Before the live demo:

- install dependencies using the README instructions;
- keep a valid consolidated Engineering schedule workbook ready;
- keep a generated proposed timetable and summary workbook available as fallback evidence;
- confirm the final generated evidence matches `FINAL_RESULTS.md`;
- do not commit generated workbooks.

## Demo Flow

1. Launch the dark desktop application.
2. Select a valid **Consolidated Schedule** workbook.
3. Show that a generated timetable workbook is rejected as input.
4. Click **Generate Timetable**.
5. Show the loading screen while the Engineering pipeline runs.
6. Show the completion summary.
7. Open **Proposed Timetable**.
8. Open **Timetable Views**.
9. Review **Unscheduled Classes**.
10. Review **Special Requests**.
11. Explain baseline versus remarks-aware results.
12. Explain zero hard conflicts.

## What To Say

Suggested opening:

> This prototype schedules the Engineering Cluster, including DSC. It treats hard constraints as non-negotiable. If a class cannot be placed safely, the system reports it for review instead of forcing an invalid timetable.

Suggested feasibility explanation:

> The main feasibility metric is scheduled hard conflicts. A value of zero means every class that received a room and time satisfies the hard constraints.

Suggested transparency explanation:

> Unscheduled classes are not hidden. They appear in the exception review outputs so timetabling staff can decide whether more rooms, delivery-mode changes, split sessions, or manual handling are needed.

## Completion Summary

Point out:

- coverage percentage;
- scheduled classes;
- classes needing review;
- hard conflicts.

The completion screen uses plain-language output buttons so non-technical users do not need to know internal workbook names.

## Proposed Timetable

Show that the timetable contains scheduled teaching activities with room, day, start time, end time, staff, group and remarks information. Explain that the output workbook structure is preserved for the downstream workflow.

## Timetable Views

Open the stakeholder views and show:

- programme timetable;
- tutor timetable;
- room timetable;
- exception queue;
- special requests review.

These views support operational review without changing the generated timetable itself.

## Unscheduled Classes

Show the exception queue. Explain that unresolved classes are part of the result, not a hidden failure.

Key framing:

> The system refuses to reduce the unscheduled count by accepting hard violations.

## Special Requests

Show the special requests review. Explain that the system interprets only supported, clear free-text remarks. Ambiguous remarks remain visible for staff confirmation instead of being guessed.

Examples to mention:

- multiple-room requirements;
- hybrid-capable room requests;
- delivery-mode flexibility;
- room-type preferences;
- unsupported or ambiguous remarks requiring manual review.

## Baseline Versus Remarks-Aware Results

Use this distinction carefully:

- The core baseline disables remarks enforcement and shows restored structured scheduling behaviour.
- The remarks-aware enhanced run enables deterministic interpretation of supported remarks.
- Both runs use the same Engineering teaching-demand denominator of `2777` occurrences.
- The enhanced run may schedule fewer occurrences because additional explicit requirements are enforced, not because hard constraints were weakened.

Core baseline:

```text
Required occurrences: 2777
Scheduled occurrences: 2747
Unscheduled occurrences: 30
Coverage: 98.92%
Scheduled hard violations: 0
Online scheduled: 813 / 813
```

Remarks-aware enhanced run:

```text
Required occurrences: 2777
Scheduled occurrences: 2715
Unscheduled occurrences: 62
Coverage: 97.77%
Scheduled hard violations: 0
```

Attribution:

```text
30 unchanged baseline exceptions
13 direct explicit remark effects
19 indirect displacements
0 unexplained occurrences
```

## Zero Hard Conflicts

Show the scheduling summary or validation checks and point out that scheduled hard conflicts are zero.

Suggested wording:

> The system is not claiming a perfect timetable. It is claiming a hard-feasible timetable for the classes it schedules, plus a transparent exception list for the remaining demand.

## Fallback Plan

If the full Engineering run takes too long during presentation:

1. Explain that Engineering scheduling is computationally heavier than the pilot checks.
2. Open the pre-generated proposed timetable.
3. Open the pre-generated scheduling summary.
4. Walk through Summary, Validation Checks, Programme Breakdown, Resource Audit, Residual F2F Analysis and Special Requests Review.
5. State that generated files are local artefacts and are excluded from Git.

## Troubleshooting

- Activate the project virtual environment before running the application.
- Run tests from the `timetable_scheduler` folder.
- Generated folders such as `generated/`, `output_files/` and `dist/` should not be committed.
- If a workbook is rejected, confirm it is a valid consolidated scheduling requirements workbook rather than a generated timetable.
