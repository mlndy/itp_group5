# Report Evidence

## Cross-Check Note

This repository has been reconciled with the release-ready prototype state. `FINAL_RESULTS.md`, `RELEASE_CHECKLIST.md`, and the Engineering validation commands are present. Baseline and remarks-aware figures are reported separately because the enhanced run enforces additional interpreted requirements.

## Problem Definition

The project addresses academic timetabling for the SIT Engineering Cluster, including DSC. The operational problem is to assign teaching activities to rooms and times while respecting hard feasibility rules.

Relevant implementation evidence:

- `timetable_scheduler/main.py::main` runs the end-to-end pipeline.
- `timetable_scheduler/data/models.py::Course`, `Room`, `TimeSlot`, and `Assignment` define the planning objects.
- `timetable_scheduler/engine/constraint_checker.py::check_hard_constraints` defines hard feasibility checks.

The final result does not claim complete Engineering coverage. The verified core baseline schedules `2747` teaching occurrences out of `2777`, leaving `30` unscheduled teaching occurrences visible for review.

## Current Manual Process

The current manual process is a spreadsheet-driven planning workflow. Staff collect requirement files, venue data, teaching weeks, class sizes, and staffing information, then manually check for room capacity, tutor clashes, cohort clashes, blocked periods, and timetable quality.

Relevant implementation evidence:

- `timetable_scheduler/data/loader.py::load_courses_from_requirements` reads requirement workbooks.
- `timetable_scheduler/data/loader.py::load_courses_from_folder` loads the Engineering input folder.
- `timetable_scheduler/data/loader.py::load_rooms_from_csv` loads venue data.

The prototype supports this manual workflow by turning input spreadsheets into structured scheduling requirements and transparent output workbooks.

## Operations and Supply-Chain Relevance

This is a resource allocation problem. Teaching demand must be matched to limited room supply, time windows, tutor availability, and student group availability.

Operations concepts represented in the prototype:

- Demand: course requirements and teaching occurrences.
- Capacity: room capacity and available teaching windows.
- Allocation: room/day/start/week assignments.
- Bottlenecks: large common-module F2F sessions and physical-room capacity.
- Exception management: unscheduled occurrences remain visible instead of being hidden.

Relevant implementation evidence:

- `timetable_scheduler/generator/scheduler.py::get_candidate_rooms` filters rooms by delivery mode and capacity.
- `timetable_scheduler/generator/scheduler.py::generate_schedule` performs the allocation.
- `timetable_scheduler/output/report_exporter.py::export_run_summary` creates stakeholder reports.

## Project Objectives

The prototype objectives are:

- Load Engineering and DSC input data.
- Model course, room, timeslot, and assignment data.
- Generate a hard-feasible timetable where possible.
- Keep scheduled hard violations at `0`.
- Leave unresolved assignments unscheduled and visible.
- Provide Excel evidence for stakeholder review.
- Demonstrate that the final Engineering scope includes DSC.

Relevant implementation evidence:

- `timetable_scheduler/main.py::load_courses` selects DSC-only or Engineering scope.
- `timetable_scheduler/generator/scheduler.py::prepare_courses_for_scheduling` consolidates common modules.
- `timetable_scheduler/output/exporter.py::export_schedule` creates the Template 2 timetable workbook.

## Data Modelling

The system uses four primary dataclasses:

- `Course`: module, activity, programme/year, class size, delivery mode, teaching weeks, staff, duration, common-module flag, and group IDs.
- `Room`: room ID, capacity, room type, resource type, and recording capability.
- `TimeSlot`: day, start time, and teaching week.
- `Assignment`: one course-room-timeslot decision plus hard and soft violations.

Relevant implementation evidence:

- `timetable_scheduler/data/models.py::Course`
- `timetable_scheduler/data/models.py::Room`
- `timetable_scheduler/data/models.py::TimeSlot`
- `timetable_scheduler/data/models.py::Assignment`

## Constraint Engine

Hard constraints define feasibility. Scheduled assignments must not violate hard constraints.

Hard constraints include:

- Room capacity.
- Delivery-mode compatibility.
- Teaching-week pattern.
- Valid day and time window.
- Blocked weeks and blocked times.
- Room clashes.
- Tutor clashes.
- Student-group clashes.
- Student lunch break rule.

Relevant implementation evidence:

- `timetable_scheduler/engine/constraint_checker.py::check_room_capacity`
- `timetable_scheduler/engine/constraint_checker.py::check_delivery_mode_room`
- `timetable_scheduler/engine/constraint_checker.py::check_week_pattern`
- `timetable_scheduler/engine/constraint_checker.py::check_time_window`
- `timetable_scheduler/engine/constraint_checker.py::check_blocked_time`
- `timetable_scheduler/engine/constraint_checker.py::check_room_clash`
- `timetable_scheduler/engine/constraint_checker.py::check_staff_clash`
- `timetable_scheduler/engine/constraint_checker.py::check_group_clash`
- `timetable_scheduler/engine/constraint_checker.py::check_hard_constraints`

Soft constraints support quality improvement. They do not define feasibility.

Relevant soft-constraint evidence:

- `timetable_scheduler/engine/constraint_checker.py::check_room_utilisation`
- `timetable_scheduler/engine/constraint_checker.py::check_first_or_last_slot`
- `timetable_scheduler/engine/constraint_checker.py::check_online_f2f_switch`
- `timetable_scheduler/engine/constraint_checker.py::check_long_idle_gaps`
- `timetable_scheduler/engine/constraint_checker.py::check_consecutive_hours`

## Greedy Schedule Generation

The greedy scheduler prioritises hard-constraint feasibility. It searches compatible room, day, and start-time patterns, then checks all candidate assignments before accepting them.

Relevant implementation evidence:

- `timetable_scheduler/generator/scheduler.py::get_candidate_rooms` filters candidate rooms.
- `timetable_scheduler/generator/scheduler.py::_course_difficulty` orders more constrained courses earlier.
- `timetable_scheduler/generator/scheduler.py::schedule_course` searches a consistent weekly room/day/start pattern.
- `timetable_scheduler/generator/scheduler.py::schedule_course_for_weeks` retries unresolved weeks.
- `timetable_scheduler/generator/scheduler.py::generate_schedule` orchestrates the full greedy schedule.
- `timetable_scheduler/generator/scheduler.py::retry_unscheduled_assignments` retries unresolved assignments while preserving hard safety.

If a safe placement cannot be found, the course remains unscheduled with a reason. This is why unresolved demand appears in reports rather than being forced into invalid timetable slots.

## Shared Online Delivery-Resource Policy

The verified final result treats `ONLINE_ROOM` as a synthetic delivery-mode placeholder for fully online teaching, not as a scarce physical venue. Online classes may share this placeholder when they do not share tutors or student groups.

This does not weaken hard constraints. Tutor clashes, student-group clashes, calendar blocks, duration checks, teaching-week checks, and physical room clashes remain prohibited.

Relevant source evidence in this checkout:

- `timetable_scheduler/config.py::VIRTUAL_ROOM_ID` defines `ONLINE_ROOM`.
- `timetable_scheduler/config.py::VIRTUAL_ROOM_CAPACITY` defines virtual room capacity.
- `timetable_scheduler/data/loader.py` creates the virtual room from those constants.
- `timetable_scheduler/engine/constraint_checker.py::check_delivery_mode_room` enforces online-to-virtual and F2F-to-physical compatibility.

Validated online result:

- Online required occurrences: `813`
- Online scheduled occurrences: `813`
- Online unscheduled occurrences: `0`

## Local-Search Optimisation

The local-search optimiser is used to improve soft-constraint quality after a feasible schedule is generated. It must not change teaching demand, coverage, or hard feasibility.

Relevant implementation evidence:

- `timetable_scheduler/optimiser/local_search.py::score_schedule` scores hard violations, unscheduled assignments, and soft violations.
- `timetable_scheduler/optimiser/local_search.py::try_move_assignment` evaluates candidate moves.
- `timetable_scheduler/optimiser/local_search.py::optimise_schedule` accepts improvements only when hard violations remain absent.
- `timetable_scheduler/optimiser/local_search.py::optimisation_summary` reports before/after hard and soft counts.

Verified optimiser evidence:

- Initial soft violations: `3030`
- Final soft violations: `3019`
- Improvement: `11`
- Runtime: approximately `1047` seconds

The improvement is useful but small. The optimiser should be shown as pre-generated evidence, not run live during presentation.

## Excel Outputs and Stakeholder Reports

The prototype creates timetable and evidence workbooks for review.

Relevant implementation evidence:

- `timetable_scheduler/output/exporter.py::export_schedule` exports the Template 2 timetable workbook.
- `timetable_scheduler/output/exporter.py::export_violations` exports violation reports.
- `timetable_scheduler/output/report_exporter.py::export_preflight_report` exports preflight issues.
- `timetable_scheduler/output/report_exporter.py::export_run_summary` exports run-summary evidence.

Key stakeholder sheets include:

- Summary
- Validation Checks
- Run Metadata
- Programme Breakdown
- Unscheduled Reasons
- Room Utilisation

The verified final artefact set also includes Resource Audit, Virtual Room Detail, Residual F2F Analysis and Optimisation Summary sheets for stakeholder review.

## Preflight Validation

Preflight validation checks input data before scheduling. It reports issues but does not block scheduling.

Relevant implementation evidence:

- `timetable_scheduler/engine/preflight_validator.py::validate_courses`
- `timetable_scheduler/engine/preflight_validator.py::validate_rooms`
- `timetable_scheduler/engine/preflight_validator.py::run_preflight_checks`
- `timetable_scheduler/output/report_exporter.py::export_preflight_report`

Preflight checks include missing fields, invalid class size or duration, empty teaching weeks, invalid delivery mode, missing suitable room, invalid room capacity, and invalid room type.

## Engineering Demand Metrics

The verified final demand denominator is teaching occurrences, not raw `Assignment` rows.

Core baseline metrics:

- Input course records: `507`
- Consolidated scheduling requirements: `465`
- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`

Remarks-aware enhanced metrics:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2715`
- Unscheduled teaching occurrences: `62`
- Coverage rate: `97.77%`
- Scheduled hard violations: `0`

This distinction is important because one unscheduled placeholder can represent multiple missing teaching weeks, while scheduled assignments are week-level occurrences.

## Final Engineering Results

Core baseline Engineering result:

- Required teaching occurrences: `2777`
- Scheduled teaching occurrences: `2747`
- Unscheduled teaching occurrences: `30`
- Coverage rate: `98.92%`
- Scheduled hard violations: `0`
- DSC inclusion: `PASS`
- Online coverage: `813 / 813`

This is a feasible partial Engineering timetable. It does not claim 100% coverage.

Remarks-aware attribution:

- Unchanged baseline exceptions: `30`
- Direct explicit remark effects: `13`
- Indirect displacements: `19`
- Unexplained occurrences: `0`

## Remaining Operational Exceptions

The remaining unscheduled demand is F2F and mainly involves large `ENG1001` common-module requirements affected by physical-room capacity.

These are operational exceptions, not hidden scheduler successes. The correct response is to review the delivery arrangement or room supply, not to force invalid assignments.

## Limitations

- The prototype does not schedule every Engineering teaching occurrence.
- Remaining large F2F common-module demand needs operational review.
- The optimiser improves soft violations only slightly and takes too long for a live demo.
- Scenario comparison is out of scope.
- Remarks-aware enforcement can reduce coverage when explicit supported requests add valid restrictions.

## Recommended Operational Improvements

- Review whether very large common-module sessions should be online, hybrid, split, or assigned to external venues.
- Confirm room availability for very large F2F sessions.
- Review skipped loader rows before final operational use.
- Use the preflight report and run summary to drive manual review.
- Treat unscheduled demand as an exception list for programme-level decision-making.

## Conclusion

The prototype demonstrates a transparent, hard-constraint-safe Engineering timetabling workflow. It schedules `2747` of `2777` required teaching occurrences, keeps scheduled hard violations at `0`, fully schedules online demand, includes DSC, and leaves the remaining `30` F2F occurrences visible for operational decision-making.
