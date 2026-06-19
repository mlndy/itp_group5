# Presentation Evidence Map

## Cross-Check Note

This checkout has been reconciled with the release-ready prototype state. `FINAL_RESULTS.md`, `RELEASE_CHECKLIST.md`, and the final demo flow are present. Baseline and remarks-aware figures must be presented separately.

## Slide 1: Problem and Current Manual Workflow

Slide objective: Explain the timetabling problem and why the current process is difficult.

Talking points:

- Engineering timetabling must coordinate rooms, tutors, student groups, teaching weeks, and delivery modes.
- Manual spreadsheet planning is slow and error-prone.
- A feasible timetable must respect non-negotiable hard constraints.
- The prototype keeps unresolved classes visible instead of hiding them.

Proposed screenshot or chart: Input folder and sample requirement workbook.

Exact verified figure to show: `507` input course records.

Source workbook/report sheet: Loader report or console output.

Likely lecturer question: Why is this more than a simple timetable?

Short answer: It is an operations problem because limited resources must be allocated to teaching demand under capacity and availability constraints.

## Slide 2: Why Timetabling Is an Operations Problem

Slide objective: Link the project to operations and supply-chain thinking.

Talking points:

- Demand is represented by teaching occurrences.
- Capacity is represented by rooms, time windows, and staff availability.
- Bottlenecks appear where demand exceeds feasible supply.
- Remaining F2F exceptions are operational decisions, not software failures.

Proposed screenshot or chart: Demand versus scheduled teaching occurrence bar chart.

Exact verified figure to show: baseline `2777` required, `2747` scheduled, `30` unscheduled.

Source workbook/report sheet: `run_summary.xlsx`, Summary sheet.

Likely lecturer question: What is the bottleneck?

Short answer: The final bottleneck is F2F demand, mainly very large `ENG1001` common-module sessions affected by physical-room capacity.

## Slide 3: System Architecture

Slide objective: Show the pipeline from input files to output workbooks.

Talking points:

- Load Excel and CSV input files.
- Convert rows into dataclass objects.
- Check constraints and generate a timetable.
- Export Template 2 timetable and stakeholder reports.

Proposed screenshot or chart: Architecture diagram.

Exact verified figure to show: `465` consolidated scheduling requirements.

Source workbook/report sheet: Summary sheet or Engineering demand metric output.

Likely lecturer question: Where does DSC enter Engineering scope?

Short answer: `main.py::load_courses` loads the Engineering input folder, and `Programme Breakdown` confirms DSC rows.

## Slide 4: Data Input and Modelling

Slide objective: Explain the core data objects.

Talking points:

- `Course` stores teaching requirement details.
- `Room` stores physical or virtual room supply.
- `TimeSlot` stores day, start time, and week.
- `Assignment` stores each scheduling decision and its violations.

Proposed screenshot or chart: Dataclass table.

Exact verified figure to show: `507` input records become `465` consolidated requirements.

Source workbook/report sheet: Summary sheet.

Likely lecturer question: Why are records consolidated?

Short answer: Common modules are merged so affected cohorts share one combined requirement instead of being scheduled separately.

## Slide 5: Hard and Soft Constraints

Slide objective: Distinguish feasibility from quality.

Talking points:

- Hard constraints are non-negotiable.
- Soft constraints measure timetable quality.
- Scheduled assignments must have `0` hard violations.
- Soft violations can be reduced by optimisation only after feasibility is preserved.

Proposed screenshot or chart: Hard versus soft constraint table.

Exact verified figure to show: Scheduled hard violations = `0`.

Source workbook/report sheet: Validation Checks.

Likely lecturer question: Are unscheduled feasibility failures hard violations?

Short answer: They are reported separately. The key feasibility metric is hard violations on scheduled assignments, which is `0`.

## Slide 6: Schedule Generator

Slide objective: Explain how the timetable is produced.

Talking points:

- The greedy generator schedules constrained requirements first.
- Candidate rooms are filtered by delivery mode and capacity.
- Candidate placements are checked before acceptance.
- Failed assignments remain unscheduled with reasons.

Proposed screenshot or chart: Generator flow diagram.

Exact verified figure to show: baseline coverage rate `98.92%`; remarks-aware coverage rate `97.77%`.

Source workbook/report sheet: Summary sheet.

Likely lecturer question: Why not force the remaining 30?

Short answer: Forcing them would create hard violations, so the system reports them as exceptions instead.

## Slide 7: Engineering Bottleneck Investigation

Slide objective: Show how the team investigated unscheduled demand.

Talking points:

- Early raw assignment counts were not a stable denominator.
- Teaching-occurrence metrics were introduced for fair comparison.
- Online bottlenecks were separated from F2F bottlenecks.
- Remaining unresolved demand is visible and classified.

Proposed screenshot or chart: Unscheduled breakdown or Residual F2F Analysis.

Exact verified figure to show: baseline `30` unscheduled teaching occurrences; remarks-aware `62` unscheduled teaching occurrences.

Source workbook/report sheet: Unscheduled Breakdown and Residual F2F Analysis.

Likely lecturer question: Did the project hide unresolved classes?

Short answer: No. Unresolved demand remains visible in summary and residual analysis sheets.

## Slide 8: Correct Online-Resource Semantics

Slide objective: Explain why `ONLINE_ROOM` can be shared.

Talking points:

- `ONLINE_ROOM` is a synthetic delivery placeholder.
- Fully online teaching does not need physical venue allocation.
- Sharing `ONLINE_ROOM` does not allow tutor or student-group clashes.
- Online demand is fully scheduled.

Proposed screenshot or chart: Resource Audit or online coverage row.

Exact verified figure to show: Online coverage `813 / 813`.

Source workbook/report sheet: Resource Audit.

Likely lecturer question: Does sharing `ONLINE_ROOM` weaken constraints?

Short answer: No. Tutor, student-group, calendar, duration, teaching-week, and physical-room rules still apply.

## Slide 9: Final Engineering Results

Slide objective: Present final validated results.

Talking points:

Baseline result:

- Required teaching occurrences: `2777`.
- Scheduled teaching occurrences: `2747`.
- Unscheduled teaching occurrences: `30`.
- Scheduled hard violations: `0`.
- DSC inclusion: `PASS`.

Remarks-aware result:

- Scheduled teaching occurrences: `2715`.
- Unscheduled teaching occurrences: `62`.
- Scheduled hard violations: `0`.
- Attribution: `13` direct explicit effects, `19` indirect displacements, `30` unchanged baseline exceptions, `0` unexplained.

Proposed screenshot or chart: Summary and Validation Checks.

Exact verified figure to show: baseline `2747 / 2777`, `98.92%`; remarks-aware `2715 / 2777`, `97.77%`.

Source workbook/report sheet: Summary and Validation Checks.

Likely lecturer question: Is this complete scheduling?

Short answer: No. It is a hard-feasible partial timetable with unresolved exceptions reported transparently.

## Slide 10: Optimiser Evidence

Slide objective: Show quality improvement after feasibility.

Talking points:

- Optimisation is controlled and not run live.
- It preserves coverage and hard safety.
- Soft violations reduce from `3030` to `3019`.
- Improvement is `11`, so it should not be overstated.

Proposed screenshot or chart: Optimisation Summary.

Exact verified figure to show: Soft improvement `11`.

Source workbook/report sheet: Optimisation Summary.

Likely lecturer question: Why not run the optimiser live?

Short answer: The verified five-iteration run took about `1047` seconds, so it is shown as pre-generated evidence.

## Slide 11: Operational Recommendations and Limitations

Slide objective: Explain next operational decisions.

Talking points:

- Remaining F2F demand needs room-capacity or delivery-policy review.
- Very large `ENG1001` common-module sessions are the main exception.
- The system does not perform scenario comparison.
- Input quality and skipped rows should be reviewed before deployment.

Proposed screenshot or chart: Residual F2F Analysis.

Exact verified figure to show: `30` F2F occurrences remain.

Source workbook/report sheet: Residual F2F Analysis.

Likely lecturer question: What should stakeholders do next?

Short answer: Decide whether to add large venues, approve online/hybrid delivery, split sessions, or manually handle exceptions.

## Slide 12: Conclusion

Slide objective: Close with feasibility, transparency, and decision support.

Talking points:

- The prototype creates an Engineering timetable including DSC.
- It preserves `0` scheduled hard violations.
- It fully schedules online demand.
- It reports unresolved F2F demand transparently.
- It supports operational decision-making rather than hiding exceptions.

Proposed screenshot or chart: Validation Checks PASS rows.

Exact verified figure to show: Release validator `PASS`, tests `220 passed`.

Source workbook/report sheet: Validation Checks and test output.

Likely lecturer question: What is the main achievement?

Short answer: A repeatable, transparent, hard-constraint-safe Engineering timetabling prototype with clear evidence for remaining operational exceptions.
