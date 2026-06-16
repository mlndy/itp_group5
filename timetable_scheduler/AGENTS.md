Read AGENTS.md first.

Task: Step 0 update AGENTS.md, then implement Engineering cluster scheduling readiness.

Important priority update:
Put scenario comparison and extra innovation on hold.

The final product must focus on creating a usable timetabling schedule for the Engineering cluster, including DSC.

Step 0 — Update AGENTS.md first

Before changing code, update AGENTS.md to reflect this current priority:

* Current phase: Engineering Cluster Schedule Completion
* Main deliverable: generate a usable Engineering cluster timetable, including DSC
* DSC-only mode remains useful for testing, but Engineering scope is the final target
* Hard violations on scheduled assignments must remain 0
* Unscheduled assignments must not be hidden
* If full scheduling is not possible, the system must clearly report what remains unscheduled and why
* Scenario comparison / what-if analysis is on hold
* Do not add extra innovation features until Engineering scheduling readiness is stronger
* Preflight report and run summary report now exist and should be preserved
* Normal validation command is:
  py -m pytest -q
* Engineering final test command should use:
  py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25

After updating AGENTS.md, continue with the implementation below.

Current validated state:

* Tests pass: 54 passed.
* DSC mode works.
* Engineering controlled demo works.
* Previous Engineering controlled demo result:

  * Scheduled assignments: 2093
  * Unscheduled assignments: 307
  * Hard violations on scheduled assignments: 0
* Preflight validation exists.
* Run summary export exists.
* Scheduling behaviour must remain hard-constraint safe.

Goal:
Make Engineering scope the primary final deliverable.

Requirements:

1. Confirm that --scope eng includes DSC data/modules.
2. Improve Engineering scheduling coverage where safely possible.
3. Keep hard violations on scheduled assignments at 0.
4. Do not hide unscheduled assignments.
5. If some assignments cannot be scheduled, produce clear reasons in the run summary/preflight/unscheduled reports.
6. Do not add scenario comparison yet.

Rules:

* Do not weaken hard constraints.
* Do not redefine dataclasses.
* Do not change existing Excel timetable output format unless required for report clarity.
* Do not force invalid assignments into the timetable.
* Keep functions small with type hints and short docstrings.
* Add tests for new behaviour.

Investigate first:

1. Run Engineering with:
   py main.py --scope eng --skip-optimisation --max-candidate-patterns 150 --max-retry-assignments 20 --skip-unscheduled-diagnostics --progress-interval 25

2. Inspect generated/run_summary.xlsx.

3. Identify why assignments remain unscheduled.

4. Check whether unscheduled assignments are mainly due to:

   * candidate-pattern demo limit
   * room capacity
   * delivery mode / virtual room mismatch
   * blocked timeslots
   * common module grouping
   * tutor clashes
   * student group clashes

Implementation focus:
Prioritise safe improvements that increase Engineering scheduled coverage without changing the meaning of constraints.

Possible safe improvements:

1. Better course ordering:

   * Schedule most constrained courses first.
   * Prioritise common modules, larger class sizes, fewer suitable rooms, longer durations, and fewer teaching weeks.

2. Better room ordering:

   * Prefer rooms that fit capacity closely.
   * Avoid using very large rooms for small classes if smaller suitable rooms exist.
   * Keep virtual rooms for online classes only.

3. Candidate filtering:

   * Pre-filter rooms by delivery mode and capacity before checking timeslots.
   * Avoid checking impossible candidates repeatedly.

4. Candidate limit reporting:

   * If max_candidate_patterns stops a course, make the reason clear in run_summary.xlsx.

5. Engineering evidence:
   Ensure run_summary.xlsx clearly shows:

   * total scheduled
   * total unscheduled
   * hard violations on scheduled assignments
   * unscheduled reason breakdown
   * programme breakdown, including DSC if available from current data

Do not:

* Add OR-Tools.
* Replace the whole scheduler.
* Add web app/UI.
* Add scenario comparison.
* Remove existing demo safety controls.
* Count unscheduled assignments as scheduled.
* Suppress unscheduled reasons.

Add/update tests:

* Engineering scope includes DSC indicator, or programme summary includes DSC if this is available from current data.
* Course ordering prioritises more constrained courses.
* Room ordering prefers closest suitable capacity.
* Candidate-limit unscheduled reason appears in run summary.
* Existing tests still pass.

Run:
py -m pytest -q

Then test:
py main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25

Expected:

* Tests pass.
* Engineering run completes.
* Hard violations on scheduled assignments remain 0.
* Scheduled assignment count should be equal to or higher than the previous 2093 if possible.
* run_summary.xlsx explains any remaining unscheduled assignments.
