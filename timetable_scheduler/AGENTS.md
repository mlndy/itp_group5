# AGENTS.md - DSC2204 ITP Timetabling Project

## Project Overview

This repository contains a Python prototype for the DSC2204 Integrative Team Project.

Project title: **Timetabling System for SIT Engineering Cluster**

The system reads Excel-based input data, models courses/rooms/timeslots, generates a feasible timetable, checks hard and soft constraints, applies optional optimisation, and exports results back to Excel.

Treat this as an operations and supply chain resource-allocation prototype, not just a programming exercise.

## Current Phase

Current phase: **Template 2 completeness-gate reconciliation**

Main deliverable: generate a usable Engineering cluster timetable, including DSC.

DSC-only mode remains useful for testing and regression checks, but Engineering scope is the final target.

Scenario comparison and what-if analysis are on hold. Do not add extra innovation features during release integration.

## Current Validated State

The core prototype is complete through:

1. Data modelling and Excel loading
2. Constraint checker
3. Greedy schedule generator
4. Local search optimiser
5. Excel exporter and full pipeline
6. Engineering controlled demo safety controls
7. Preflight validation and run summary reporting
8. Demand-metric audit, resource audit, online-delivery semantics, optimiser validation, and release validation
9. Deterministic remarks interpretation, multi-room scheduling support, hybrid/flexible-delivery handling, and special-request review reporting

Current completeness-gate result:

- Tests: `314 passed`
- Release validator: `PASS` because the strict Template 2 completeness gate finds `23` qualifying programme-year schedules
- Engineering controlled demo: runs successfully with `0` scheduled hard-constraint violations
- Total teaching occurrences: `3562`
- Schedulable occurrences: `3323`
- Quarantined input occurrences: `239`
- Scheduled occurrences: `3214`
- Scheduler search failures: `109`
- Coverage of schedulable demand: `96.72%`
- Coverage of total recorded demand: `90.23%`
- Proposed timetable rows: `3006`
- All-valid scheduled Template 2 rows: `2980`
- Submission-ready Template 2 populated rows: `212`
- Template 2 invalid rows: `0`
- Qualifying submission-ready programme-years: `23`
- Minimum required programme-year schedules: `20`
- Template 2 readiness: `PASS`
- Programme visual sheets: `86`
- Tutor visual sheets: `235`
- Room visual sheets: `48`
- Visual export status: `PASS`
- Fixed-session integrity status: `PASS`
- Microsoft Excel desktop open check: `PASS`

The `90.23%` total-recorded-demand coverage includes quarantined source records and must not be presented as the algorithm's scheduling success rate. The primary scheduling-performance metric is `96.72%` coverage of schedulable demand.

The earlier pre-fixed-session v1.0 baseline had `2777` required occurrences, `2747` scheduled occurrences, `30` unscheduled occurrences, and `98.92%` coverage. Treat those values as historical development evidence only.

Preflight, run summary, guarded-generation, Template 2 validation, Template 2 programme-year reconciliation, Template 2 exclusion audit, run manifest and visualisation validation reports should be preserved. Present release readiness only with the latest evidence showing at least 20 qualifying programme-years without weakening hard constraints.

## Additional DSC2204 Requirements - June 26

- Input errors should be detected before timetable generation.
- Global structural input errors must prevent generation; isolated record-level errors may quarantine only the affected requirements where safe.
- Fixed sessions must be anchored exactly as supplied.
- Non-fixed modules must be scheduled around fixed sessions.
- Fixed sessions must not be silently moved to improve coverage.
- Fixed and non-fixed requirements must not be double-counted.
- Template 2 must be validated for field completeness and accuracy.
- The final submission workbook must contain at least `20` programme-year schedules.
- Programme year is the schedule-counting unit.
- Unscheduled or incomplete rows must not appear in the submission-ready Template 2 workbook.
- Unresolved requirements remain in separate exception reports.
- Existing hard constraints must not be weakened.
- Previous metrics must be revalidated after fixed-session integration.
- The old `2777` demand total is historical once v1.1 guarded fixed-session evidence is used.

## Fixed-Session Conflict Triage and Source Reconciliation

- The readiness gate must not be bypassed.
- Official fixed sessions must not be moved automatically.
- Raw source workbooks must not be edited silently.
- Systematic formatting differences may be normalised only when the identity is unambiguous.
- Duplicate rows and shared sessions must be identified using evidence, not assumptions.
- Multiple rows representing the same shared class must not create false lecturer, room or group clashes.
- Genuine source conflicts must be reported for supervisor clarification.
- Every automatically resolved issue must retain its original value, normalised value, rule applied and evidence.
- Critical-error counts must distinguish unique affected rows from total issue instances.
- Conflicts may overlap, so summary totals must not be added blindly.
- The full Engineering scheduler may run when no global blocking issue remains; unresolved record-level issues must be quarantined and reported.

## Authoritative Resolution and Supervisor Approval Workflow

- Remaining issues must first be checked against all authoritative project files.
- Source values must not be invented.
- Venue aliases may be resolved only using the venue dataset, Template 2 support sheets, or clear exact-code equivalence.
- External venues must not be mapped to arbitrary internal rooms.
- Missing teaching weeks must not receive default values.
- Genuine fixed conflicts require human clarification.
- Approved resolutions must be stored separately from raw source files.
- Raw institutional workbooks must remain unchanged.
- Every approved resolution must record approver, date, reason and original source row.
- The scheduler must support strict mode with no unresolved critical issues.
- Resolution overrides must not silently bypass unrelated validation errors.

## Guarded Partial Generation Policy

- Input validation remains mandatory before generation.
- Errors must be shown to the user before scheduling begins.
- Global structural errors block the complete run.
- Record-level errors quarantine only the affected requirements where isolation is safe.
- Quarantined requirements must never appear as valid scheduled rows.
- Valid fixed sessions must remain anchored exactly.
- Invalid fixed sessions must not be moved, guessed or silently corrected.
- Genuine fixed-to-fixed conflicts quarantine the conflicting assignments.
- Unaffected fixed and non-fixed assignments may continue to scheduling.
- Scheduled assignments must have zero hard-constraint violations.
- A programme-year affected by unresolved demand must be marked incomplete.
- Only complete programme-year schedules count toward the minimum of `20`.
- The proposed timetable may contain valid schedules from both complete and incomplete programme-years.
- Submission-ready Template 2 must contain only valid complete rows and clearly report programme completeness.
- All original source values and source-row references must remain traceable.
- Raw institutional workbooks must remain unchanged.
- The optimiser must never move fixed assignments.
- Timetable visualisation is a later output phase and must not be implemented yet.

## Timetable Visualisation Export

- Visualisation is an output function, not a scheduling function.
- Visual exports must use the final validated scheduled assignments.
- Visualisation must not independently reinterpret or modify schedule data.
- Quarantined and unscheduled requirements must not appear as scheduled blocks.
- Incomplete programme-years must be labelled clearly.
- Fixed and generated sessions must be visually distinguishable.
- Physical, online and external sessions must be distinguishable.
- Shared sessions must not be duplicated incorrectly.
- Programme views may show the shared session for each participating programme.
- Tutor and room views must show one physical assignment per shared session.
- Template 2 must remain unchanged.
- Visual workbook failure must not corrupt or delete the valid proposed timetable.
- Every visual block must retain a traceable assignment ID.
- Excel sheet names must remain within `31` characters.
- Generated visual workbooks remain ignored release outputs unless intentionally packaged.
- Current visualisation validation:
  - Tests: `314 passed`
  - Programme visual sheets: `86`
  - Tutor visual sheets: `235`
  - Room visual sheets: `48`
  - Visual export status: `PASS`
  - Scheduled hard violations remain `0`
  - Microsoft Excel desktop open check: `PASS`

## Final Integration and Release v1.1

- This section is superseded by the stricter Template 2 completeness-gate evidence recorded above.
- The validated visualisation branch includes the fixed-session compliance implementation.
- Final scheduling metrics must not change during documentation and release work.
- Scheduled hard violations must remain zero.
- Template 2 readiness is currently `PASS` under the completeness gate because `23` qualifying programme-years are submission-ready.
- At least `20` submission-ready programme-year schedules are required for release, and the current evidence satisfies this gate.
- Visual exports are supplementary outputs and must not change the official Template 2 workbook.
- Quarantined input demand and scheduler search failures must remain reported separately.
- Generated output workbooks remain ignored from source control.
- A separate assessment-evidence package may contain validated generated outputs.
- AI must be described as implementation, testing and documentation support under Group 5's review.
- All project ownership and decisions must be presented as team-based.
- Do not present one student as the sole project owner.
- Do not delete existing branches or tags.
- Current completeness-gate metrics:
  - Total teaching occurrences: `3562`
  - Schedulable occurrences: `3323`
  - Quarantined input occurrences: `239`
  - Scheduled occurrences: `3214`
  - Scheduler search failures: `109`
  - Scheduled hard-constraint violations: `0`
  - Coverage of schedulable demand: `96.72%`
  - Coverage of total recorded demand: `90.23%`
  - Proposed timetable rows: `3006`
  - All-valid scheduled Template 2 rows: `2980`
  - Submission-ready Template 2 populated rows: `212`
  - Qualifying submission-ready programme-years: `23`
  - Template 2 readiness: `PASS`
  - Visual export status: `PASS`
  - Fixed-session integrity status: `PASS`
  - Microsoft Excel desktop open check: `PASS`

## Coding Rules

Follow these rules for all future code changes:

- Use Python with type hints.
- Keep functions small and single-purpose.
- Add short docstrings for new functions.
- Use existing dataclasses from `data/models.py`.
- Do not redefine `Course`, `Room`, `TimeSlot`, or `Assignment`.
- Use constants from `config.py`; do not hardcode timetable rules.
- Do not change Excel timetable output formats unless explicitly requested or required for report clarity.
- Do not rename existing public functions unless tests and call sites are updated.
- Avoid broad rewrites. Make small, reviewable changes.

## Hard Constraint Rule

Hard constraints must never be weakened.

The scheduler and optimiser must never accept scheduled assignments with hard violations.

If a class cannot be scheduled safely, leave it unscheduled and report the reason. Do not force invalid assignments into the timetable.

This framing is important for the final presentation:

> The prototype prioritises feasibility. It schedules only assignments that satisfy all hard constraints and leaves the remaining classes unscheduled instead of hiding conflicts.

## Engineering Readiness Rules

For Engineering scope:

- `--scope eng` must include the Engineering cluster and DSC data/modules when present in the Engineering input folder.
- Hard violations on scheduled assignments must remain `0`.
- Unscheduled assignments must not be hidden.
- If full scheduling is not possible, reports must clearly explain what remains unscheduled and why.
- Improve coverage only through safe ordering, filtering, reporting, and retry controls that preserve hard constraints.

## Engineering Final Validation

- The final deliverable is Engineering scope, not DSC-only.
- `--scope eng` must include DSC.
- Scheduled assignments must have `0` hard violations.
- Unscheduled assignments must remain visible.
- Results must be numerically consistent: total assignments = scheduled assignments + unscheduled assignments.
- If result totals change between runs, the report must explain why.
- Do not claim improvement using scheduled count alone unless the total assignment pool is the same.
- Preserve `preflight_report.xlsx` and `run_summary.xlsx`.
- Scenario comparison is still on hold.

## Template 2 All-Years Completeness Hotfix

- Template 2 must contain all valid scheduled programme-year rows, not only Year 1.
- One unresolved requirement must not silently remove all other valid rows from that programme-year.
- Programme-year readiness and row export are separate decisions.
- The actual saved `Timetable` sheet is the source of truth for programme-year counts.
- Validation must not count programme-years from proposed timetable data, visual sheets, support sheets or internal records.
- Year formats must be normalised consistently.
- Template 2 readiness cannot pass unless the actual saved workbook contains at least `20` valid programme-year schedules.
- No release is allowed until the saved workbook is inspected directly.

## Template 2 Programme-Year Completeness Gate

- The actual saved `Template2_Submission_Ready.xlsx` is the source of truth for exported rows.
- Saved rows alone do not prove that a programme-year schedule is complete.
- Programme-year identity must be normalised once and reused throughout the pipeline.
- A programme-year counts toward the minimum `20` only when it is complete and has valid saved submission rows.
- Quarantined input occurrences and scheduler search failures must be attributed to the same canonical programme-year identity.
- Incomplete programme-years may appear in the all-valid workbook but must not count toward the strict submission minimum.
- Reports must distinguish:
  - represented in saved workbook;
  - complete schedule;
  - submission-ready and counts toward minimum `20`.
- The validator must fail when fewer than `20` qualifying programme-years exist.
- No hard constraints may be weakened to increase the count.
- Do not hard-code a count of `22`, `20`, `13` or `11`.
- Current audited result: `23` qualifying submission-ready programme-years from `212` strict saved rows, so release readiness is `PASS`.

## Targeted Programme-Year Recovery Phase

- This historical phase started from `17` qualifying submission-ready programme-years.
- The minimum required is `20` qualifying programme-years.
- The current validated release evidence reaches `23` qualifying programme-years through evidence-based corrections.
- Hard constraints must remain unchanged.
- Fixed sessions must remain unchanged.
- Required demand must not be removed from completeness calculations.
- Missing data must not be invented.
- Programme-years must remain incomplete when unresolved required demand exists.
- Any improvement must show the exact blocker removed and the evidence supporting the correction.
- Changes must be small, isolated and regression-tested.
- Stop further scheduler changes now that the minimum `20` is truthfully achieved and all release gates pass.

## Final Programme-Year Completion Policy

### Official fixed sessions are authoritative

- When a session comes from the official fixed-session workbook `Requirements Template_Lab (ENG) - AY25 Tri 1.xlsx`, its supplied day, start time, end time, duration, teaching weeks, room or venue, staff and group must be treated as authoritative.
- The scheduler must anchor an official fixed session exactly when the source data is internally valid.

### Generic operating-hour and lunch rules must not invalidate an official fixed session

- An official fixed session must not be quarantined solely because it spans the normal lunch period, starts before a preferred operating window, ends after `18:00`, or runs for a long continuous duration such as `09:00-18:00`.
- These are permitted exceptions only for authoritative fixed sessions.
- Official fixed sessions must still satisfy no tutor clash, no group clash, no room clash, valid teaching weeks, valid academic-calendar day, valid delivery mode and exact fixed-session placement.

### Non-fixed sessions retain normal scheduling policies

- Non-fixed classes must still obey the configured normal operating window, lunch policy, duration rules, candidate-slot rules and hard constraints.
- Do not extend the general scheduler operating day merely to improve coverage.

### Explicit remarks are not automatically fixed sessions

- A free-text instruction such as `9AM-6PM` must retain its full duration.
- If a timing instruction is not backed by the official fixed-session workbook, do not shorten it, do not silently move it, schedule it only where valid, and otherwise leave it unresolved for review.

### Venue and exam-seating mappings must be authoritative

- A missing venue or exam-seating room may be recovered only when an exact, unambiguous mapping exists in the official Template 2 support sheets, the venue workbook, the fixed-session source, or another authoritative supplied data file.
- Do not create a location host key.
- Do not use fuzzy matching for submission-critical room identities.
- If an exact mapping does not exist, keep the requirement quarantined.

### Completeness remains strict

- A programme-year counts only when recorded required occurrences are greater than `0`, quarantined occurrences are `0`, scheduler search failures are `0`, scheduled occurrences equal recorded required occurrences, scheduled hard violations are `0`, all required Template 2 mappings are valid, and strict saved Template 2 rows exist.

## Explainable Remarks Interpretation

- Remarks are free-text scheduling requests from programme submissions.
- The system should interpret only clear and supported patterns.
- Every interpretation must preserve the original remark.
- Every interpreted rule must show what was detected and how it was applied.
- Explicit requirements may become hard constraints.
- Words such as `prefer`, `preferred`, or `if possible` should normally become soft preferences.
- Ambiguous or unsupported remarks must be sent for manual review.
- The system must never silently guess the meaning of unclear text.
- Remarks processing must be deterministic and testable.
- The UI must not use the terms Template 1 or Template 2.
- User-facing terminology should be:
  - Consolidated Schedule
  - Proposed Timetable
- Internal code and technical documentation may retain the confirmed workbook roles.
- DSC remains part of Engineering and must not appear as a separate UI option.
- Existing scheduling rules must not be weakened.

## Remarks Refinement and Coverage Attribution

- Ambiguous remarks must not automatically block otherwise feasible scheduling.
- Unsupported remarks should normally be scheduled using structured fields and flagged for review.
- Only explicit, supported, high-confidence requirements may become hard constraints.
- Preferences must remain soft constraints.
- Low-confidence interpretations must never become hard constraints.
- Every additional unscheduled occurrence caused by remarks must be attributed to a specific enforced rule.
- The system must distinguish:
  - automatically applied
  - preference considered
  - scheduled but needs confirmation
  - unscheduled because of explicit request
  - unsupported but non-blocking
  - no scheduling action required
- Zero scheduled hard violations must remain the primary safety requirement.
- Do not change the existing timetable output structure.
- Do not add Template 1 or Template 2 wording back into the UI.

## Baseline Restoration and Deterministic Remarks Comparison

- Disabling remarks interpretation must restore the original non-remarks scheduling behaviour.
- Remarks-related dataclass fields must have neutral defaults.
- Source metadata and audit fields must not change candidate ordering or feasibility.
- The baseline and enhanced runs must use identical input, consolidation, room data, scheduler limits and optimisation settings.
- Comparison runs must be deterministic.
- Search displacement must not be labelled as a remark-caused failure without evidence.
- Every enhanced-only scheduling difference must be classified precisely.
- Suspected false positives are not acceptable final classifications.
- Zero scheduled hard violations remains mandatory.
- Timetable output structure must remain unchanged.
- User-facing UI must continue to avoid template-number terminology.
- Historical restored disabled baseline:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2747`
  - Unscheduled teaching occurrences: `30`
  - Coverage rate: `98.92%`
  - Scheduled hard violations: `0`
- Historical enhanced remarks run:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2715`
  - Unscheduled teaching occurrences: `62`
  - Coverage rate: `97.77%`
  - Scheduled hard violations: `0`
- Historical attribution reconciliation:
  - Direct explicit remark effects: `13`
  - Indirect enhanced-run displacements: `19`
  - Unchanged unscheduled occurrences: `30`
  - Enhanced recoveries: `0`
  - Unexplained or suspected categories: `0`

## Engineering Coverage and Bottleneck Resolution

- Historical Engineering result for that phase:
  - Total assignments: `2593`
  - Scheduled assignments: `2119`
  - Unscheduled assignments: `474`
  - Hard violations on scheduled assignments: `0`
- Historical phase tests: `61 passed`
- The next goal is to reduce unscheduled assignments safely.
- Never reduce the unscheduled count by accepting hard violations.
- Preserve `preflight_report.xlsx`, `run_summary.xlsx`, `Validation Checks`, `Run Metadata`, `Programme Breakdown`, and DSC evidence.
- Before changing scheduling behaviour, produce a reason and bottleneck breakdown.
- Scenario comparison remains on hold.
- Any scheduling improvement must be measured against the same input dataset and command.
- Total assignments must remain comparable between baseline and improved runs.

## Evidence-Driven Coverage Improvement

- Historical comparable baseline:
  - Total assignments: `2593`
  - Scheduled assignments: `2119`
  - Unscheduled assignments: `474`
  - Hard violations on scheduled assignments: `0`
  - Tests: `67 passed`
- All future comparisons must use the same input dataset and total assignment count of `2593`.
- Update only one scheduling behaviour per iteration.
- Select the behaviour based on the largest category in `Unscheduled Breakdown`.
- Do not claim an improvement if the total assignment pool changes.
- Do not reduce unscheduled assignments by accepting hard violations.
- Preserve original unscheduled reasons and all reporting sheets.
- Scenario comparison remains on hold.

## Demand Metric Integrity and Coverage Audit

- Historical phase tests: `68 passed`.
- Historical Engineering result:
  - Reported scheduled assignments: `2119`
  - Reported unscheduled assignments: `474`
  - Reported total: `2593`
  - Hard violations on scheduled assignments: `0`
- A virtual-room resource experiment changed the reported total to `2753`.
- Input teaching demand must not change when room availability changes.
- Before further scheduler optimisation, define invariant demand metrics.
- Do not compare scheduling improvements using raw `Assignment` object counts if scheduled and unscheduled objects represent different units.
- Preserve all existing hard-safety and DSC-inclusion checks.
- Scenario comparison remains on hold.

## Virtual Room Semantics and Resource Capacity Validation

- Historical phase tests: `78 passed`.
- Historical stable Engineering demand baseline:
  - Input course records: `507`
  - Consolidated requirements: `465`
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2119`
  - Unscheduled teaching occurrences: `658`
  - Coverage rate: `76.31%`
  - Hard violations on scheduled assignments: `0`
- The dominant bottleneck is incomplete multi-week placement, especially for online synchronous two-hour lectures.
- Before adding or changing virtual-room capacity, verify how virtual rooms are represented in the source data and loader.
- Required teaching occurrences must remain `2777` for all comparable runs.
- Do not weaken room-conflict constraints unless the project requirements clearly show that virtual rooms are non-exclusive.
- Do not automatically create virtual rooms without evidence.
- Scenario comparison remains on hold.

## Online Delivery Resource Semantics

- Historical phase tests: `85 passed`.
- Historical stable Engineering teaching demand:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2119`
  - Unscheduled teaching occurrences: `658`
  - Coverage rate: `76.31%`
  - Hard violations on scheduled assignments: `0`
- Resource audit:
  - Raw venue rows: `169`
  - Loaded physical rooms: `169`
  - Loaded virtual rooms: `1`
  - Virtual room ID: `ONLINE_ROOM`
  - Required online occurrences: `813`
  - Scheduled online occurrences: `196`
  - Unscheduled online occurrences: `617`
  - Online coverage: `24.11%`
- `ONLINE_ROOM` is created by the loader and is not one of the raw venue rows.
- The supplied TTConstraints workbook states that fully online lectures require no physical venue allocation.
- `ONLINE_ROOM` should be treated as a delivery-mode placeholder, not as one exclusive physical resource.
- Online classes must still respect tutor, student-group, time, calendar, duration, and week-pattern constraints.
- Physical room clashes must remain unchanged.
- Required teaching occurrences must remain `2777`.
- Do not add artificial virtual rooms.
- Scenario comparison remains on hold.

## Residual F2F Completion and Final Scheduler Acceptance

- Historical phase tests: `91 passed`.
- Historical stable Engineering demand:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2747`
  - Unscheduled teaching occurrences: `30`
  - Coverage rate: `98.92%`
  - Hard violations on scheduled assignments: `0`
- Online demand is fully scheduled:
  - Required online occurrences: `813`
  - Scheduled online occurrences: `813`
  - Unscheduled online occurrences: `0`
- Remaining unscheduled demand is F2F:
  - `24` no complete multi-week placement
  - `4` blocked or unavailable timeslot
  - `2` candidate-pattern limit
- The next goal is to resolve or conclusively explain the remaining `30` F2F occurrences.
- Never force assignments that violate hard constraints.
- Do not change online shared-placeholder semantics.
- Required teaching occurrences must remain `2777`.
- Update only one scheduling behaviour per evidence-supported iteration.
- After this phase, scheduler behaviour should be frozen unless a clear correctness bug is found.

## Final Pipeline and Optimiser Acceptance

- Historical phase tests: `94 passed`.
- Historical expected stable Engineering baseline, pending final rerun:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2747`
  - Unscheduled teaching occurrences: `30`
  - Coverage rate: `98.92%`
  - Online coverage: `813 / 813`
  - Hard violations on scheduled assignments: `0`
- Remaining demand is F2F, primarily very large `ENG1001` common-module requirements with enrolments of approximately `1035` and `1110`.
- These should be treated as operational physical-room capacity exceptions unless source requirements support another delivery arrangement.
- Scheduler behaviour is now frozen.
- Do not weaken capacity, room-clash, tutor-clash, student-group, calendar, duration, or recurring-week constraints.
- The next objective is to validate the optimiser and final end-to-end pipeline.
- Teaching demand and scheduled coverage must not change during optimisation.
- Optimisation must never introduce hard violations.
- Scenario comparison and unrelated innovation remain on hold.

## Historical v1.0 Artefact Freeze and Submission Readiness

- Historical phase test count has been superseded by the final release test count recorded above.
- Earlier pre-fixed-session Engineering demand:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2747`
  - Unscheduled teaching occurrences: `30`
  - Coverage rate: `98.92%`
  - Scheduled hard violations: `0`
- Online demand:
  - Required: `813`
  - Scheduled: `813`
  - Unscheduled: `0`
- Remaining demand is F2F and primarily caused by physical-room capacity pressure for very large `ENG1001` common-module requirements.
- Controlled optimiser result:
  - Initial soft violations: `3030`
  - Final soft violations: `3019`
  - Improvement: `11`
  - Runtime: approximately `1047` seconds
  - Coverage and hard safety preserved
- Use the non-optimised Engineering command for the live demo because the optimiser runtime is too long for a live presentation.
- Keep the optimiser output as pre-generated evidence.
- Scheduler and optimiser behaviour are frozen.
- Generated outputs remain ignored by Git.
- Scenario comparison and additional innovation remain out of scope.

## Report and Presentation Phase

- Prototype feature development is complete.
- Historical phase metrics have been superseded by the completeness-gate result recorded above.
- Release validator: `PASS` under the strict Template 2 completeness gate.
- Current Engineering scheduling result:
  - Total teaching occurrences: `3562`
  - Schedulable occurrences: `3323`
  - Quarantined input occurrences: `239`
  - Scheduled occurrences: `3214`
  - Scheduler search failures: `109`
  - Coverage of schedulable demand: `96.72%`
  - Coverage of total recorded demand: `90.23%`
  - Scheduled hard-constraint violations: `0`
  - Template 2 readiness: `PASS`
  - Visual export status: `PASS`
  - Fixed-session integrity status: `PASS`
  - Microsoft Excel desktop open check: `PASS`
- DSC inclusion: `PASS`.
- Quarantined input records and scheduler search failures must remain visible.
- Controlled optimiser evidence:
  - Initial soft violations: `3030`
  - Final soft violations: `3019`
  - Improvement: `11`
  - Runtime: approximately `1047` seconds
- Use the non-optimised command for the live demo.
- Do not change validated figures unless a new full release run proves different results.
- Report and presentation work must frame this branch as release-ready under the current evidence because the Template 2 minimum is satisfied without weakening hard constraints.

## Repository Reconciliation Before Final Submission

Initial pre-reconciliation findings recorded for that task:

- The checkout contained report and presentation evidence documents.
- The checkout reported only `61` passing tests.
- The previously validated release-ready state had `112` passing tests.
- `FINAL_RESULTS.md` and `RELEASE_CHECKLIST.md` were missing before reconciliation.
- `DEMO.md` contained a superseded Engineering command before reconciliation.
- Final report and presentation work must not proceed until the repository is reconciled.
- Do not invent or manually alter verified metrics.
- Preserve the verified final Engineering figures:
  - Required teaching occurrences: `2777`
  - Scheduled teaching occurrences: `2747`
  - Unscheduled teaching occurrences: `30`
  - Coverage: `98.92%`
  - Scheduled hard violations: `0`
  - Online coverage: `813 / 813`
  - DSC inclusion: `PASS`

## Prototype Requirements Acceptance

- DSC was only the smaller pilot dataset used to test the algorithm before scaling.
- DSC is part of the Engineering cluster.
- The final prototype scope is the full Engineering cluster, including DSC.
- Template 1 is the bulk scheduling input submitted before consolidation.
- Template 2 is the proposed timetable produced by the timetabling team before submission into SIT's internal system.
- The prototype operates between consolidated Template 1 input and proposed Template 2 output.
- Report and presentation work is paused until prototype acceptance is complete.
- Preserve the existing Template 2 workbook structure.
- Never weaken hard constraints to increase coverage.
- Unresolved requirements must remain visible and explained.
- Do not add scenario comparison, a web application, OR-Tools, machine learning, or unrelated innovation.
- Update `AGENTS.md` before every future prototype phase.

## Minimal Desktop UI

- DSC was only the small pilot dataset.
- The final scope is the Engineering cluster, including DSC.
- Template 1 is the bulk scheduling input before consolidation.
- Template 2 is the proposed timetable produced before submission to the internal system.
- The UI is a thin layer over the existing tested pipeline.
- Scheduling and constraint logic must not be duplicated inside the UI.
- The UI should be minimal, neat, local, and suitable for Windows.
- Use only the Python standard library where practical.
- Do not build a web application.
- Do not add login, database, cloud hosting, drag-and-drop timetable editing, or real-time collaboration.
- Command-line operation must continue to work.
- Existing generated Excel outputs remain the official prototype outputs.

## Simplified Desktop UI and Repository Cleanup

- The final scope is the Engineering cluster.
- DSC is part of the Engineering cluster and must not be presented as a separate inclusion feature.
- DSC was previously used only as a smaller pilot dataset.
- The UI should accept one file labelled `Consolidated Schedule`.
- Venue information, common-module data, Template 2 and other supporting resources are internal bundled resources and should not be selected by the user.
- The UI should not expose scheduling configuration.
- The UI should use fixed validated Engineering defaults.
- The UI should be dark, minimal and suitable for non-technical timetabling staff.
- Detailed technical outputs remain available through Excel reports.
- Do not remove required inputs, tests or deliverable documentation without confirming that they are obsolete.
- Do not delete `.git` from the working repository.
- `.git`, virtual environments, caches and generated outputs must be excluded from distributable ZIP files.
- Report and presentation development remains paused during this task.

## Confirmed Template Roles

- Template 1 is the scheduling-requirements input.
- Template 1 uses a `Module` worksheet containing programme, module, activity, class size, delivery mode, teaching weeks and staff information.
- Template 2 is the proposed timetable output used for the internal-system upload process.
- Template 2 uses a `Timetable` worksheet containing day, start, end, room, staff, group and activity-output fields.
- The filenames `Template 1.xlsx` and `Template 2.xlsx` are already correct.
- Workbook roles must be detected from worksheet structure and headers rather than filenames.
- A workbook renamed to `Template 1.xlsx` must not be accepted if it has Template 2 structure.
- A workbook renamed to `Template 2.xlsx` must still be accepted as input if it has valid Template 1 structure.
- Correct pipeline: Template 1 requirements -> validation and loading -> consolidation and normalisation -> schedule generation -> bounded optimisation -> Template 2 proposed timetable.
- The Engineering timetabling dataset is under `Data/Requirements_ENG`.
- DSC is one Engineering programme and is not a separate UI option.
- Do not alter scheduling rules, hard constraints, optimiser logic, demand metrics, virtual-room semantics or Template 2 structure.

## Final Release and AI Collaboration

- Group 5 defined the problem, requirements, architecture, validation criteria and final project decisions.
- AI tools supported implementation, testing, debugging and documentation.
- AI-generated suggestions were reviewed, corrected and validated by the team.
- The repository must not claim that AI independently designed the system.
- The repository must not hide or minimise AI involvement.
- Final claims must be supported by tests, deterministic runs and generated evidence.
- The final UI uses:
  - `Consolidated Schedule`
  - `Proposed Timetable`
- The UI must not display Template 1 or Template 2 terminology.
- The final scope is the Engineering cluster.
- DSC is part of Engineering.
- The final innovative feature is deterministic and explainable remarks interpretation.
- Existing hard constraints must not be weakened.
- The timetable output structure must not be changed.
- Generated outputs, virtual environments, caches and temporary files must not be committed.
- The final release must come from `main`.
- The final release tag should be `v1.1.0` unless that tag already exists.

## UI Scope, Output Integrity and Run Isolation Hotfix

- The selected consolidated schedule defines the scope of a UI run.
- Selecting one requirements workbook must not silently schedule the entire bundled Engineering dataset.
- Fixed sessions may be included only when they belong to the selected scope.
- The UI and CLI must use identical pipeline options and scope rules.
- No hidden fallback to the full Engineering folder is allowed when a valid file was selected.
- Coverage displayed by the UI must be calculated from the selected run only.
- Proposed Timetable and Submission-Ready Template 2 are separate outputs.
- Each UI button must open the exact path returned by the current pipeline run.
- The UI must never use stale files found through broad filename searches.
- Every run must have a unique run ID and isolated output directory.
- Workbooks must be written atomically and reopened successfully before being reported as created.
- An open or locked workbook must not cause a partially written or corrupted file.
- Visual timetable exports must be limited to the current selected run.
- Requirements and output workbooks must be detected structurally, not by filename.
- The workbook with a `Module` requirements sheet is input.
- The workbook with `Timetable`, `Course Code`, `Location`, `Staff`, and `Group` sheets is the Template 2 output template.
- Do not mark a run successful until all reported output files pass integrity validation.

## Final Output Quality and Scheduling Instruction Accuracy

- Recurring teaching occurrences with identical placement must be aggregated before visual layout.
- Teaching weeks should be displayed inside one visual block rather than one lane per week.
- Visual lanes are only for genuinely simultaneous, overlapping assignments.
- Explicit day and time instructions must be parsed conservatively and enforced when complete.
- A recognised explicit timing instruction must not be treated only as a soft remark.
- Duration ranges must be preserved where representable.
- Unresolved input rows must be reported even when they represent zero parsed teaching occurrences.
- UI review counts must distinguish requirement rows from teaching occurrences.
- Scheduled hard violations must remain zero.
- Template 2 structure and selected-workbook scope isolation must remain unchanged.

## Final Metric Semantics and Instruction Conflict Handling

- Input course records, scheduling assignments and teaching occurrences are different units.
- UI labels must never use these units interchangeably.
- Explicit timing remarks that conflict with structured fields must not be silently ignored.
- Authoritative fixed-session placements take precedence over free-text remarks.
- Any such precedence decision must be visible in the audit.
- A recognised explicit duration must either be enforced or produce a review issue.
- Scheduled output must never contradict a recognised hard instruction without explanation.

## Final Engineering Validation and Release Freeze

- The final assessment result must come from the full Engineering dataset.
- The selected DSC workbook is a functional smoke test, not the primary project result.
- Full Engineering validation must use the latest remark, duration and fixed-session logic.
- Old Engineering metrics must not be assumed unchanged.
- Fixed sessions must remain at their authoritative day, time, duration, weeks, room and staff.
- Free-text remarks cannot override official structured fixed sessions.
- Any fixed-session override must remain visible in audit evidence.
- Scheduled hard violations must remain zero.
- Quarantined input, unresolved requirement rows and scheduler placement failures must remain separate metrics.
- Template 2 must preserve its official workbook structure.
- At least `20` submission-ready programme-year schedules are mandatory.
- Visual outputs are supplementary and must reconcile with the final scheduled assignments.
- No release is permitted until the final workbooks open successfully in Microsoft Excel.
- After this phase, freeze scheduler behaviour and move to academic deliverables.

## Final Code Freeze and Finishing-Touch Policy

- Core scheduler behaviour is frozen.
- No coverage-chasing changes are permitted.
- Only validation, evidence, documentation, packaging and demonstration reliability changes are allowed.
- Any change affecting scheduled occurrences, quarantine, search failures, hard violations or qualifying programme-years must be treated as a regression and investigated.
- Final metrics must come from one isolated Engineering run.
- Report, presentation and demonstration materials must use the same frozen evidence.
- AI-generated claims must be checked against actual workbooks and test output.

## Important Commands

Run tests from inside the `timetable_scheduler` folder:

```powershell
cd C:\Users\Admin\Documents\GitHub\itp_group5\timetable_scheduler
py -m pytest -q
```

Expected result:

```text
314 passed
```

Run DSC demo:

```powershell
py main.py --scope dsc --max-iterations 2
```

Expected key result:

```text
Final hard violations on scheduled assignments: 0
```

Run Engineering remarks-aware final test:

```powershell
python main.py --scope eng --skip-optimisation --max-candidate-patterns 300 --max-retry-assignments 50 --skip-unscheduled-diagnostics --progress-interval 25 --audit-demand-metrics
```

Expected key result for the current completeness-gate run:

```text
Total teaching occurrences: 3562
Schedulable occurrences: 3323
Quarantined input occurrences: 239
Scheduled occurrences: 3214
Scheduler search failures: 109
Scheduled hard-constraint violations: 0
Template 2 readiness: PASS
Visual export status: PASS
Fixed-session integrity status: PASS
Microsoft Excel desktop open check: PASS
```

These v1.1 metrics must remain stable during release documentation and packaging. If a new full validation run changes them, stop and explain the evidence before updating any report.

## Generated Files

Running the prototype may create:

```text
timetable_scheduler/generated/
timetable_scheduler/output_files/
```

These folders are generated outputs and must not be committed unless explicitly requested.

Also do not commit:

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
```

Input Excel files required by the prototype should not be ignored or deleted.

## Workflow Rules

Before merging any branch:

1. Run `py -m pytest -q`
2. Run the DSC demo command
3. Run the Engineering final test command
4. Confirm scheduled hard violations are `0`
5. Check `git status --short`
6. Ensure generated output folders are not staged
7. Review `git diff`

Do not merge if tests fail or scheduled hard violations are introduced.

## Report and Presentation Framing

Use this framing in documentation and presentation:

- The problem is a real-world academic timetabling problem.
- The system models rooms, tutors, student groups, time slots, and course requirements.
- Hard constraints are treated as non-negotiable.
- Soft constraints are treated as quality improvements.
- The prototype is transparent: unresolved classes remain unscheduled and visible.
- Engineering mode is controlled with demo safety limits to avoid excessive search time.
- Unscheduled classes are not hidden; they represent cases requiring more search time, better input data, more rooms, or manual review.

Important phrasing:

> In Engineering controlled demo mode, the system schedules as many assignments as it can while keeping 0 hard violations on scheduled assignments. Remaining assignments are intentionally left unscheduled because the system refuses to force invalid allocations into the timetable.

## Do Not Do Unless Explicitly Requested

Do not:

- Replace the greedy scheduler with a completely new algorithm.
- Add OR-Tools or other heavy solver dependencies.
- Change the dataclasses.
- Change Template 2 output structure.
- Commit generated Excel outputs.
- Hide unscheduled assignments.
- Count unscheduled assignments as successful scheduled classes.
- Add scenario comparison or what-if analysis.
